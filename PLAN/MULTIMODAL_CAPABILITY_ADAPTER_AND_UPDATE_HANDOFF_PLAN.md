# Multimodal Capability Adapter And Update Handoff Plan

## Total Objective

Create a durable execution plan that future agents can use to turn AstraBridge's multimodal support into a stable, extensible, and update-friendly system. The target end state is not a pile of per-provider patches, but a capability-first runtime where multimodal support is governed by explicit contracts, adapter families, exposure gates, provider/model evidence, and automation skills that can safely discover, validate, roll out, and roll back updates.

## Deliverables

- A capability-first multimodal contract set for `image.generate`, `vision.analyze`, `speech.transcribe`, and `speech.synthesize`.
- A provider/model capability matrix that separates documented support, adapter wiring, route eligibility, and validated evidence.
- Adapter-family implementations and route gating rules for the highest-priority multimodal providers and models.
- A secret-safe dry-run and live-smoke verification pipeline with durable evidence outputs.
- A bounded skill and script package that lets future agents perform provider-doc sync, matrix reconciliation, adapter repair, smoke execution, and rollout gating without reconstructing chat history.

## Related Context Files

- `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md`
- `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`
- `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`
- `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`

## Constraints And Attention Notes

1. This plan complements the broader capability runtime plan and must not overwrite or erase its completed history.
2. Do not store API keys, bearer tokens, cookies, auth headers, provider raw secrets, or desktop plaintext key material in git, reports, logs, or generated artifacts.
3. Preserve `PRIVATE/**`, smoke artifacts, request and response traces, validation reports, screenshots, and matrix outputs by default unless the user explicitly names cleanup targets.
4. Official provider documentation is the primary source for capability, modality, and parameter-shape claims. Secondary sources may inform design, but must not be treated as proof of support.
5. A model name appearing in docs or catalog metadata does not mean AstraBridge may expose it as runnable. Exposure requires explicit adapter support and verification evidence.
6. Unknown or unsupported capability state is preferable to optimistic inheritance from provider-wide defaults.
7. Capability-facing interfaces must stay stable even when provider request or response shapes drift.
8. Web search remains a standalone web lane and must not be merged into multimodal model capability routing unless the user later asks for that change explicitly.
9. Updates must be safe by default: scoped, reviewable, evidence-backed, and reversible.

## Adjustment Policy

Agents may reasonably adjust substeps, filenames, commands, provider ordering, or sequencing when repository facts require it. Such adjustments must not change the total objective, weaken the evidence bar, blur the separation between documented and runnable support, remove secret-handling safeguards, or replace substantive compatibility work with cosmetic-only changes. If a provider lane cannot be verified inside the current repository boundary, the acceptable substitute is an explicit downgrade with durable evidence, a rollout block, and a clear next action for a later agent.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must begin by reading this plan and the related context files needed for the current step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all of its acceptance criteria are satisfied.
5. If blocked, record the concrete blocker, evidence, attempted paths, and exact next-step entry point.
6. Each turn must end with a concise handoff that states completed work, files changed, validation run, blockers, and next step.
7. When a step changes provider exposure or verification behavior, preserve before-and-after evidence in a durable artifact path.

## Current Progress

- Current status: Complete
- Completed steps: Step 0, Create Durable Plan; Step 1, Freeze Scope And Architectural Invariants; Step 2, Build The Multimodal Capability Matrix Contract; Step 3, Reconcile Existing Surface Maps Against The Matrix Contract; Step 4, Stabilize Capability Contracts For The Four Multimodal Lanes; Step 5, Define Adapter Families And Their Required Interfaces; Step 6, Add Exposure Gate Rules Between Catalog And Runtime; Step 7, Build The Official Documentation Source Pack For Multimodal Providers; Step 8, Implement DashScope Image Adapter Family; Step 9, Implement CosyVoice And Qwen TTS Family Normalization; Step 10, Normalize Vision And ASR Model-Level Eligibility; Step 11, Create Dry-Run Matrix Reconciliation Reports
- Current step: None
- Next step: None
- Last updated: 2026-07-07

## Execution Steps

### 0. Create Durable Plan

Goal: Create this handoff plan and make the next entry point clear.

Main actions:

- Define the total objective, constraints, execution rules, steps, and acceptance criteria.
- Record the related files that future agents must treat as baseline context.
- Set current progress and initial log entry.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, constraints, adjustment policy, current progress, execution steps, acceptance criteria, and progress log.
- Next step is clearly identified.

Status: completed

### 1. Freeze Scope And Architectural Invariants

Goal: Lock the intended boundaries so later agents do not drift into ad hoc provider patching.

Main actions:

- Read the broader capability runtime plan and surface-map files.
- Write a short scope note that fixes the in-scope capabilities, priority providers, and non-negotiable architectural invariants.
- Explicitly separate `documented`, `wired`, `verified`, and `exposed` support states.

Acceptance criteria:

- A written scope artifact exists under `PLAN/` or `PRIVATE/`.
- The artifact names the in-scope capabilities, priority providers, and deferred work.
- The artifact makes the `documented` versus `runnable` distinction explicit enough that a later agent cannot confuse catalog presence with runtime support.

Status: completed

### 2. Build The Multimodal Capability Matrix Contract

Goal: Define the single source of truth for provider/model/capability state.

Main actions:

- Design a matrix schema that records provider id, model id, capability id, input modalities, output modalities, route eligibility, adapter family, docs source, smoke status, exposure status, and last-verified metadata.
- Record which fields are authoritative for routing, which are informational for UI, and which are verification-only.
- Define status vocabularies such as `documented_unwired`, `wired_unverified`, `verified_runnable`, `blocked`, `deprecated`, and `hidden`.

Acceptance criteria:

- A matrix-contract artifact exists on disk.
- The contract distinguishes route-authoritative fields from UI-only hints.
- A future agent can determine whether a model should be exposed without reading chat history.

Status: completed

### 3. Reconcile Existing Surface Maps Against The Matrix Contract

Goal: Identify where current catalog, runtime, and UI surfaces drift from the intended contract.

Main actions:

- Audit current capability specs, registry resolution, router config, generated catalog, and visible UI/provider surfaces.
- Map each surface field to the new matrix contract.
- Record mismatches where current code exposes models without verified adapters, or hides models that are wired and verified.

Acceptance criteria:

- A drift report exists with file-level references.
- The report classifies mismatches by severity and ownership surface.
- The next implementation step is unambiguous.

Status: completed

### 4. Stabilize Capability Contracts For The Four Multimodal Lanes

Goal: Make capability-facing interfaces stable before expanding provider support.

Main actions:

- Review and tighten the input and output contracts for `image.generate`, `vision.analyze`, `speech.transcribe`, and `speech.synthesize`.
- Normalize artifact conventions, timeout semantics, stream behavior, and error taxonomy.
- Add or tighten tests for contract-level positive and negative cases.

Acceptance criteria:

- Each of the four multimodal capabilities has an explicit and stable contract.
- Contract tests cover representative success and failure cases.
- Provider-specific quirks are no longer encoded in capability-level schema semantics.

Status: completed

### 5. Define Adapter Families And Their Required Interfaces

Goal: Replace per-model patching with reusable provider-protocol families.

Main actions:

- Define adapter-family boundaries such as `openai_compatible_image`, `dashscope_image`, `dashscope_tts`, `dashscope_asr`, and `chat_multimodal_vision`.
- For each family, define request-builder, response-parser, artifact-persistence, validator, and error-normalization interfaces.
- Record which current providers and models should map to each family.

Acceptance criteria:

- An adapter-family design artifact exists with required interfaces.
- Current priority providers can be mapped to families without ambiguity.
- The design makes it clear when a new model only needs metadata versus a new family implementation.

Status: completed

### 6. Add Exposure Gate Rules Between Catalog And Runtime

Goal: Prevent non-runnable models from leaking into selectable runtime surfaces.

Main actions:

- Define the exact gate conditions required for a model to move from `documented` to `exposed`.
- Implement or specify route-level checks that require docs support, adapter support, and verification state before exposure.
- Add downgrade behavior for `documented_unwired` and `wired_unverified` lanes.

Acceptance criteria:

- A concrete exposure-gate rule set exists with file-level implementation ownership.
- There is a defined downgrade path for models that are known in docs but not safely runnable.
- Representative tests exist or are specified for positive and negative exposure decisions.

Status: completed

### 7. Build The Official Documentation Source Pack For Multimodal Providers

Goal: Create the primary-source baseline needed for current and future updates.

Main actions:

- Record official documentation URLs for priority providers covering model lists, modality support, image generation, vision, ASR, TTS, streaming, and documented limits.
- Store retrieval date, provider id, capability categories, stability notes, and whether the source is required for rollout decisions.
- Keep secondary references clearly separated from primary sources.

Acceptance criteria:

- A source-pack artifact exists and is secret-free.
- Each source entry has provider id, URL, retrieval date, and capability categories.
- The source pack is sufficient for a future doc-sync skill to run without reconstructing discovery logic.

Status: completed

### 8. Implement DashScope Image Adapter Family

Goal: Add a real runtime lane for Alibaba image-generation models instead of catalog-only declarations.

Main actions:

- Build a `dashscope_image` adapter family with validated request and response handling for the current official image APIs.
- Start with the highest-value official models such as the current Qwen/Wan image lines that are documented and stable enough for rollout.
- Add contract tests, request-shape validators, and artifact persistence.

Acceptance criteria:

- AstraBridge has a real adapter family for DashScope image generation.
- At least one priority official DashScope image model can be represented as `wired`.
- Tests cover success and representative request-shape failures.

Status: completed

### 9. Implement CosyVoice And Qwen TTS Family Normalization

Goal: Make Alibaba speech-synthesis support extensible beyond the currently hardcoded Qwen TTS pair.

Main actions:

- Extend the speech-synthesis adapter layer so CosyVoice and Qwen TTS variants can share a family-level contract where the protocol allows it.
- Record family-specific differences such as streaming mode, voice selection, audio format, and response assembly.
- Update matrix and route metadata so each model's status is explicit.

Acceptance criteria:

- The speech-synthesis layer can represent both current Qwen TTS and priority CosyVoice models without per-model ad hoc logic.
- Capability and matrix metadata distinguish family-shared behavior from model-specific limits.
- Tests cover voice, format, and stream assembly semantics for the family contract.

Status: completed

### 10. Normalize Vision And ASR Model-Level Eligibility

Goal: Stop provider-wide defaults from overstating multimodal input support.

Main actions:

- Tighten model-level eligibility rules for image and audio input lanes.
- Ensure route selection requires declared and validated modality support rather than optimistic provider defaults.
- Add representative negative tests for text-only models and unsupported modality combinations.

Acceptance criteria:

- Vision and ASR routing block text-only or otherwise ineligible models before live provider calls.
- Model-level modality differences are visible in matrix and route outputs.
- Tests cover both allowed and blocked routes.

Status: completed

### 11. Create Dry-Run Matrix Reconciliation Reports

Goal: Expand coverage and catch drift without consuming provider credits.

Main actions:

- Build or extend dry-run tooling that emits route choice, eligibility explanation, adapter family, request-shape validation result, and exposure state for all matrix entries.
- Save reports in a secret-free durable location.
- Ensure dry-run output highlights unknown, blocked, conflicting, and downgraded lanes instead of only success cases.

Acceptance criteria:

- A repeatable dry-run report exists for the in-scope providers and models.
- The report shows route eligibility and exposure-state reasoning for each matrix entry.
- The report can be rerun without live credentials.

Status: completed

### 12. Define And Execute The Minimal Live Smoke Set

Goal: Prove the highest-value lanes with real provider-backed evidence while keeping verification bounded.

Main actions:

- Define one representative live smoke case per priority adapter family and per priority modality lane.
- Use managed provider paths only when authorized for the turn.
- Preserve secret-free artifacts such as normalized requests, normalized responses, asset manifests, and classification summaries.

Acceptance criteria:

- A bounded live-smoke evidence pack exists for the chosen families and lanes.
- Evidence is secret-free and linked back to matrix entries.
- Any failure is classified into durable statuses rather than left as an ambiguous note.

Status: completed

### 13. Build Agent Skills For Doc Sync, Matrix Reconcile, Adapter Repair, And Smoke

Goal: Turn maintenance into reusable agent workflows instead of manual one-off knowledge.

Main actions:

- Create or extend skills and supporting scripts for provider-doc sync, matrix reconciliation, multimodal adapter repair, smoke execution, and rollout gating.
- Keep each skill scoped, explicit about inputs, safe by default, and evidence-preserving.
- Record which files each skill owns and what artifacts it is allowed to write.

Acceptance criteria:

- Skill definitions and helper scripts exist for the required maintenance flows.
- Each skill has a clear entry point, artifact policy, and secret-handling policy.
- A future agent can execute the maintenance workflow by following the skill instead of chat context.

Status: completed

### 14. Add Rollout Safety, Review Gates, And Rollback Paths

Goal: Ensure automated updates cannot silently expose broken multimodal support.

Main actions:

- Define update scopes such as provider-specific, model-family-specific, stable-only, or pinned-version updates.
- Add rollout gates that require contract pass, dry-run pass, and required live-smoke evidence before exposure changes.
- Define rollback behavior for matrix entries, route gating, and catalog exposure when verification regresses.

Acceptance criteria:

- A rollout and rollback policy exists on disk.
- Update automation has explicit scope controls and default-safe behavior.
- There is a documented path to revert exposure without deleting preserved evidence.

Status: completed

### 15. Finalize Runbook And Maintenance Handoff

Goal: Leave a complete operating manual for future agents and maintainers.

Main actions:

- Summarize architecture, matrix semantics, adapter families, verification workflow, and rollout rules in a maintainer-facing runbook.
- Link the runbook to the broader capability runtime plan and any new skills or scripts.
- Record remaining risks, deferred providers, and exact entry points for future work.

Acceptance criteria:

- A final runbook or handoff note exists and links to all relevant artifacts.
- Remaining risks and deferred work are explicit rather than implied.
- A new agent can continue maintenance from the runbook and this plan without reconstructing chat history.

Status: completed

## Progress Log

### 2026-07-06 - Step 0

- Completed: Created the durable handoff plan for multimodal capability adaptation, provider adapter families, exposure gating, verification, and update automation.
- Files changed: `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation: Read the durable handoff plan skill, its template, and aligned the plan with existing AstraBridge `PLAN/` conventions and current capability-runtime context files.
- Blockers: None.
- Next step: Step 1, Freeze Scope And Architectural Invariants.

### 2026-07-06 - Step 1

- Completed: Froze the multimodal execution scope, priority provider set, deferred work, architectural invariants, and support-state vocabulary in a dedicated scope note.
- Files changed: `PLAN/MULTIMODAL_CAPABILITY_SCOPE_AND_INVARIANTS.md`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation: Re-read the multimodal handoff plan plus `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md`, `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`, and `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`; confirmed the scope note explicitly distinguishes `documented`, `wired`, `verified`, and `exposed`.
- Blockers: None.
- Next step: Step 2, Build The Multimodal Capability Matrix Contract.

### 2026-07-06 - Step 2

- Completed: Defined the multimodal capability matrix contract as a dedicated artifact with route-authoritative, UI-informational, and verification-only field classes plus concrete row requirements for `provider/model/capability` lanes.
- Files changed: `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation: Re-read the multimodal scope note, broader provider/model matrix contract, and current routing/runtime code in `capabilities/capability_routes.py` and `capabilities/runtime.py`; confirmed the new contract names the authoritative routing fields, UI-only fields, verification-only fields, status vocabulary, and mapping to current repository surfaces.
- Blockers: None.
- Next step: Step 3, Reconcile Existing Surface Maps Against The Matrix Contract.

### 2026-07-06 - Step 3

- Completed: Reconciled current multimodal catalog, runtime, MCP, capability-management, and dry-run surfaces against the multimodal matrix contract and recorded the main drift items in a dedicated report.
- Files changed: `PLAN/MULTIMODAL_CAPABILITY_SURFACE_DRIFT_REPORT.md`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation: Re-read the multimodal matrix contract and current implementation surfaces in `capabilities/specs.py`, `capabilities/capability_registry.py`, `capabilities/capability_routes.py`, `capabilities/runtime.py`, `router_config_service.py`, `astrabridge_capabilities_mcp_server.py`, `model_catalog/generated_catalog.py`, `model_catalog/catalog.py`, `provider_capability_dry_run_matrix.py`, and `provider_capability_verification_gate_baseline.json`; confirmed the report names concrete mismatches, severity, ownership surfaces, and next-step implications.
- Blockers: None.
- Next step: Step 4, Stabilize Capability Contracts For The Four Multimodal Lanes.

### 2026-07-06 - Step 4

- Completed: Tightened the four multimodal capability contracts so the capability layer exposes stable abstract fields and required output metadata, while removing a provider-specific note from the transcription contract.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`, `apps/astrabridge-sidecar/tests/test_capability_specs.py`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation:
  - `python -m unittest tests.test_capability_specs -v`
  - `python -m unittest tests.test_image_generate_adapter tests.test_speech_transcribe_adapter tests.test_speech_synthesize_adapter tests.test_vision_analyze_adapter -v`
  - `python -m unittest tests.test_capability_smoke -v`
- Blockers: None.
- Next step: Step 5, Define Adapter Families And Their Required Interfaces.

### 2026-07-06 - Step 5

- Completed: Defined the multimodal adapter-family contract, required family interfaces, initial family boundaries, and the provider-to-family mapping needed to replace per-model patching with reusable protocol families.
- Files changed: `PLAN/MULTIMODAL_ADAPTER_FAMILY_CONTRACT.md`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation: Re-read the multimodal handoff plan, matrix contract, and current adapter/runtime surfaces in `capabilities/image_generate_adapter.py`, `capabilities/speech_transcribe_adapter.py`, `capabilities/speech_synthesize_adapter.py`, `capabilities/vision_analyze_adapter.py`, `capabilities/specs.py`, `capabilities/runtime.py`, and `model_catalog/generated_catalog.py`; confirmed the artifact names the required interfaces, defines stable family boundaries, maps current priority providers without ambiguity, and states when metadata-only onboarding is allowed versus when a new family is required.
- Blockers: None.
- Next step: Step 6, Add Exposure Gate Rules Between Catalog And Runtime.

### 2026-07-06 - Step 6

- Completed: Defined the multimodal exposure gate rule set between catalog discovery and runtime exposure, including exact gate conditions, downgrade behavior, route-mode policy, file-level implementation ownership, and representative test requirements.
- Files changed: `PLAN/MULTIMODAL_EXPOSURE_GATE_RULES.md`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation: Re-read the multimodal handoff plan, surface drift report, and current implementation surfaces in `capabilities/capability_registry.py`, `capabilities/capability_routes.py`, `router_config_service.py`, `model_catalog/catalog.py`, and `provider_capability_dry_run_matrix.py`; confirmed the new artifact defines the `documented / wired / verified / exposed` gate, specifies route-level checks and downgrade paths, assigns file-level implementation ownership, and names representative positive and negative tests.
- Blockers: None.
- Next step: Step 7, Build The Official Documentation Source Pack For Multimodal Providers.

### 2026-07-07 - Step 7

- Completed: Built the multimodal provider official source pack covering the priority providers, primary documentation URLs, secondary references, rollout-required pages, and provider-specific notes for later doc-sync and rollout work.
- Files changed: `PLAN/MULTIMODAL_PROVIDER_OFFICIAL_SOURCE_PACK.md`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation: Re-read the multimodal handoff plan, scope note, and current `source_urls` usage in `router_config_service.py`; then checked current official provider documentation through the provider-owned sites for Yunwu, Alibaba Model Studio, Kimi, BigModel, DeepSeek, and OpenAI. Confirmed the source-pack artifact records provider id, URL, retrieval date, capability categories, rollout relevance, and secondary-source separation sufficient for later doc-sync work.
- Blockers: None.
- Next step: Step 8, Implement DashScope Image Adapter Family.

### 2026-07-07 - Step 8

- Completed: Implemented the first DashScope image adapter family lane for `image.generate`, wired `qwen-image-plus` as an official Qwen image model, and added focused tests covering successful async task normalization plus representative request-shape failures.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/dashscope_image_generate_adapter.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`, `apps/astrabridge-sidecar/tests/test_image_generate_adapter.py`, `apps/astrabridge-sidecar/tests/test_capability_registry.py`, `apps/astrabridge-sidecar/tests/test_capability_specs.py`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation:
  - `python -m unittest tests.test_image_generate_adapter tests.test_capability_registry tests.test_capability_specs -v`
  - `python -m unittest tests.test_capability_routes tests.test_capability_mcp_server -v`
- Blockers: None.
- Next step: Step 9, Implement CosyVoice And Qwen TTS Family Normalization.

### 2026-07-07 - Step 9

- Completed: Reworked the speech-synthesis lane into a shared Alibaba TTS adapter family that now covers both Qwen TTS and priority CosyVoice HTTP SSE models without per-model hardcoding in the runtime. The adapter now chooses a family-specific protocol profile at request-build time, keeps Qwen on the existing multimodal-generation endpoint, adds CosyVoice support on the SpeechSynthesizer endpoint, requires explicit CosyVoice voice selection, and prefers the final audio URL when streamed chunk bytes do not match the requested output container. Catalog seeds now include priority CosyVoice models with model-specific TTS limits, the adapter contract advertises the combined family coverage, and capability candidate ordering keeps the default speech route on the existing Qwen pair while exposing CosyVoice for explicit selection.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`, `apps/astrabridge-sidecar/tests/test_speech_synthesize_adapter.py`, `apps/astrabridge-sidecar/tests/test_capability_registry.py`, `apps/astrabridge-sidecar/tests/test_capability_specs.py`, `apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation:
  - `python -m unittest tests.test_speech_synthesize_adapter tests.test_capability_registry tests.test_capability_specs tests.test_provider_catalog_contract -v`
  - `python -m unittest tests.test_provider_source_registry tests.test_capability_routes tests.test_capability_smoke -v`
  - `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`
- Blockers: None.
- Next step: Step 10, Normalize Vision And ASR Model-Level Eligibility.

### 2026-07-07 - Step 10

- Completed: Tightened model-level eligibility for the vision and ASR lanes so candidates now require declared model records with the required input modalities instead of inheriting support from adapter matches or provider defaults. Unknown vision/ASR models without effective catalog records are no longer exposed, text-only overrides remain blocked, and model-level modality differences are now visible through candidate and route runtime-provider-contract payloads. Added explicit modality-limit metadata for Qwen vision and ASR seeds, plus a generated-catalog seed-freshness check so updated seed modality fields propagate into runtime route outputs instead of staying hidden behind stale generated locks.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`, `apps/astrabridge-sidecar/tests/test_capability_registry.py`, `apps/astrabridge-sidecar/tests/test_capability_routes.py`, `apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation:
  - `python -m unittest tests.test_capability_registry tests.test_capability_routes tests.test_provider_catalog_contract tests.test_capability_smoke -v`
  - `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py apps/astrabridge-sidecar/tests/test_capability_registry.py apps/astrabridge-sidecar/tests/test_capability_routes.py apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`
- Blockers: None.
- Next step: Step 11, Create Dry-Run Matrix Reconciliation Reports.

### 2026-07-07 - Step 11

- Completed: Reworked the provider capability dry-run matrix into a lane-level multimodal reconciliation report so each `provider/model/capability` row now carries direct route-resolution status, adapter family, request-shape validation status, exposure-state projection, downgrade reasons, and expected artifact paths. The dry-run matrix now emits entry counts, exposure-state counts, route-eligibility counts, and a report section that surfaces blocked, hidden, and `wired_unverified` multimodal lanes explicitly instead of only aggregating by model. Also corrected TTS seed input-modality declarations from `text+audio` to `text` so dry-run reconciliation no longer reports false ASR conflicts for TTS-only families. Generated a durable dry-run evidence pack under `PRIVATE/agentic-update-pipeline/runs/multimodal-step11-dry-run-20260707/` plus the linked capability-smoke dry-run artifacts under `PRIVATE/provider-compatibility/runs/multimodal-step11-dry-run-20260707-capability-smoke/`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`, `apps/astrabridge-sidecar/tests/test_provider_capability_dry_run_matrix.py`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation:
  - `python -m unittest tests.test_provider_capability_dry_run_matrix tests.test_provider_capability_verification_gate tests.test_provider_catalog_contract tests.test_capability_registry -v`
  - `python -m unittest tests.test_provider_capability_dry_run_matrix tests.test_provider_capability_verification_gate tests.test_capability_routes tests.test_capability_smoke -v`
  - `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py apps/astrabridge-sidecar/tests/test_provider_capability_dry_run_matrix.py`
- Blockers: None.
- Next step: Step 12, Define And Execute The Minimal Live Smoke Set.

### 2026-07-07 - Step 12

- Completed: Defined and executed a bounded provider-backed live smoke set for the four in-scope multimodal capability lanes on managed Qwen credentials. The live batch covered `qwen/qwen-image-plus:image.generate`, `qwen/qwen3-vl-plus:vision.analyze`, `qwen/qwen3-asr-flash:speech.transcribe`, and `qwen/qwen3-tts-flash:speech.synthesize`. Three lanes passed with provider-backed evidence and persisted artifacts; the `image.generate` lane was classified as `blocked` because the active sidecar runtime could not resolve an eligible explicit candidate for `qwen/qwen-image-plus`, which is now preserved as a durable route/exposure blocker instead of an ambiguous note.
- Files changed: `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`, `PRIVATE/agentic-update-pipeline/runs/multimodal-step12-live-smoke-20260707/preflight.json`, `PRIVATE/agentic-update-pipeline/runs/multimodal-step12-live-smoke-20260707/case-pack.json`, `PRIVATE/agentic-update-pipeline/runs/multimodal-step12-live-smoke-20260707/lane-index.json`, `PRIVATE/agentic-update-pipeline/runs/multimodal-step12-live-smoke-20260707/summary.json`, `PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace/PRIVATE/provider-compatibility/runs/multimodal-step12-live-smoke-20260707/summary.json`, `PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace/PRIVATE/provider-compatibility/runs/multimodal-step12-live-smoke-20260707/report.md`
- Validation:
  - `GET http://127.0.0.1:8791/api/health`
  - `GET http://127.0.0.1:8791/api/llm-manager/session`
  - `GET http://127.0.0.1:8791/api/profiles`
  - `POST http://127.0.0.1:8791/api/runtime/provider-compatibility-smoke` with managed admin session token and a four-case provider-backed payload
- Blockers: `qwen/qwen-image-plus:image.generate` is still blocked in the active sidecar runtime because the explicit route cannot resolve an eligible candidate even though the local adapter family and dry-run matrix already recognize the lane. This is preserved in the live smoke evidence bundle as a runtime exposure/configuration mismatch to address in the next skill-building and repair step.
- Next step: Step 13, Build Agent Skills For Doc Sync, Matrix Reconcile, Adapter Repair, And Smoke.

### 2026-07-07 - Step 13

- Completed: Added a new repository-local maintenance skill, `multimodal-capability-maintenance`, that gives future agents one entry point for multimodal doc-sync indexing, dry-run matrix reconcile, provider-backed smoke execution, rollout gating, and bounded repair handoff. The skill reuses the existing sidecar modules and existing `provider-capability-repair` / `agentic-update-pipeline` / `model-metadata-curator` surfaces instead of duplicating runtime logic. Also added four helper scripts that future agents can run directly: `sync_multimodal_source_index.py`, `run_multimodal_matrix_reconcile.py`, `run_multimodal_live_smoke.py`, and `run_multimodal_rollout_gate.py`, plus a maintenance-surface reference file that fixes file ownership, write boundaries, and secret rules.
- Files changed: `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/SKILL.md`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/agents/openai.yaml`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/references/maintenance-surfaces.md`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/sync_multimodal_source_index.py`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_matrix_reconcile.py`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_live_smoke.py`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_rollout_gate.py`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`, `PRIVATE/agentic-update-pipeline/runs/step13-skill-check/doc-sync/source-index.json`, `PRIVATE/agentic-update-pipeline/runs/step13-skill-check/matrix/summary.json`, `PRIVATE/agentic-update-pipeline/runs/step13-skill-check/live-smoke/summary.json`, `PRIVATE/agentic-update-pipeline/runs/step13-skill-check/rollout-gate/summary.json`
- Validation:
  - `python C:\Users\cyz19\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance`
  - `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance\scripts\sync_multimodal_source_index.py D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance\scripts\run_multimodal_matrix_reconcile.py D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance\scripts\run_multimodal_live_smoke.py D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance\scripts\run_multimodal_rollout_gate.py`
  - `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/sync_multimodal_source_index.py --workspace-root D:\AstraBridge --out D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step13-skill-check\doc-sync\source-index.json`
  - `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_matrix_reconcile.py --workspace-root D:\AstraBridge --artifact-root D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step13-skill-check\matrix --run-id step13-skill-check --with-verification-gate`
  - `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_live_smoke.py --sidecar http://127.0.0.1:8791 --workspace-root D:\AstraBridge --artifact-root D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step13-skill-check\live-smoke --run-id step13-skill-check-live --provider qwen --vision-model qwen3-vl-plus --asr-model qwen3-asr-flash --tts-model qwen3-tts-flash`
  - `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_rollout_gate.py --workspace-root D:\AstraBridge --artifact-root D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step13-skill-check\rollout-gate --run-id step13-skill-check --require-live-smoke-summary D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step13-skill-check\live-smoke\summary.json`
- Blockers: None for the skill package itself. Known runtime blocker `qwen/qwen-image-plus:image.generate` remains preserved in Step 12 evidence and is now reachable through the new maintenance + repair workflow instead of requiring chat reconstruction.
- Next step: Step 14, Add Rollout Safety, Review Gates, And Rollback Paths.

### 2026-07-07 - Step 14

- Completed: Added a dedicated multimodal rollout and rollback policy artifact plus concrete rollout-gate safety outputs so future agents can drive narrow, reviewable promotion decisions instead of relying on ad hoc chat judgment. The rollout gate now accepts explicit scope controls (`scope`, provider, model, model-family, version policy, apply mode), validates required matrix and live-smoke evidence, writes a normalized run contract, emits a rollout decision bundle, and generates a reversible rollback manifest under the standard agentic-update run root. The maintenance skill and reference surfaces now point to these new safety outputs and the tracked rollback path.
- Files changed: `PLAN/MULTIMODAL_ROLLOUT_AND_ROLLBACK_POLICY.md`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_rollout_gate.py`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/SKILL.md`, `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/references/maintenance-surfaces.md`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`, `PRIVATE/agentic-update-pipeline/runs/step14-rollout-safety-check/run-contract.json`, `PRIVATE/agentic-update-pipeline/runs/step14-rollout-safety-check/rollout-gate/summary.json`, `PRIVATE/agentic-update-pipeline/runs/step14-rollout-safety-check/rollout-gate/report.md`, `PRIVATE/agentic-update-pipeline/runs/step14-rollout-safety-check/rollback/rollout-gate-summary.json`, `PRIVATE/agentic-update-pipeline/runs/step14-rollout-safety-check/rollback/multimodal-rollout-decision.json`, `PRIVATE/agentic-update-pipeline/runs/step14-rollout-safety-check/rollback/linked-evidence.json`, `PRIVATE/agentic-update-pipeline/runs/step14-rollout-safety-check/rollback/rollback-manifest.json`
- Validation:
  - `python C:\Users\cyz19\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance`
  - `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance\scripts\run_multimodal_rollout_gate.py`
  - `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance\scripts\run_multimodal_rollout_gate.py --workspace-root D:\AstraBridge --artifact-root D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step14-rollout-safety-check\rollout-gate --run-id step14-rollout-safety-check --provider qwen --model qwen/qwen3-vl-plus --model-family chat_multimodal_vision --version-policy stable --apply-mode verify_candidate --require-matrix-summary D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step13-skill-check\matrix\summary.json --require-live-smoke-summary D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step13-skill-check\live-smoke\summary.json`
- Blockers: None for the rollout-safety slice. Promotion remains intentionally manual-review gated even after a passing technical decision bundle; this is by design, not a blocker.
- Next step: Step 15, Finalize Runbook And Maintenance Handoff.

### 2026-07-07 - Step 15

- Completed: Added the final maintainer-facing runbook that ties together the multimodal contracts, adapter-family boundaries, rollout and rollback rules, maintenance skill workflow, baseline evidence packs, remaining risks, and exact future entry points. This closes the handoff objective by giving later agents one durable operating manual instead of requiring reconstruction from the numbered plan or prior chat history.
- Files changed: `PLAN/MULTIMODAL_MAINTENANCE_RUNBOOK.md`, `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- Validation:
  - `Get-Content D:\AstraBridge\PLAN\MULTIMODAL_MAINTENANCE_RUNBOOK.md`
  - `Test-Path D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\multimodal-step11-dry-run-20260707`
  - `Test-Path D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\multimodal-step12-live-smoke-20260707\summary.json`
  - `Test-Path D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step13-skill-check`
  - `Test-Path D:\AstraBridge\PRIVATE\agentic-update-pipeline\runs\step14-rollout-safety-check`
  - `python C:\Users\cyz19\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AstraBridge\apps\astrabridge-sidecar\skills\multimodal-capability-maintenance`
- Blockers: None. Remaining risks are now explicitly recorded in the runbook rather than left implicit.
- Next step: None. The multimodal capability adapter and update handoff plan is complete.
