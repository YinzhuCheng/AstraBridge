# Provider Capability And Reasoning Runbook

Last updated: 2026-07-06

This runbook is the maintenance contract for AstraBridge provider, model, capability, and reasoning-effort updates. Use it when a model is upgraded, a new provider is added, a modality claim changes, or reasoning normalization needs adjustment.

Primary execution contract:

- `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`

Supporting contracts and evidence shapes:

- `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`
- `PLAN/PROVIDER_MODEL_COVERAGE_REASONING_AUDIT_HANDOFF_PLAN.md`
- `PRIVATE/agentic-update-pipeline/reports/`
- `PRIVATE/agentic-update-pipeline/runs/`
- `PRIVATE/provider-compatibility/runs/`

## Scope

This runbook governs:

- provider profile updates
- effective model catalog changes
- capability-route truthfulness
- reasoning-effort and thinking normalization
- static validation, dry-run evidence, and optional managed-key live smoke
- user-visible capability status surfaces

This runbook does not permit:

- official OpenAI account-login reintroduction
- raw secret persistence in docs, logs, reports, or git
- treating provider-wide flags as proof that every model under that provider supports the same modality or tool surface
- provider-backed live smoke without explicit user authorization for the current turn

## Safety Boundaries

Always follow these rules:

1. Official provider docs are the primary source for modality, tool, streaming, context, and reasoning claims.
2. OpenRouter may be used only as a secondary design reference for reasoning abstraction, not as proof of provider behavior.
3. Preserve `PRIVATE/**`, sanitized raw artifacts, dry-run outputs, smoke reports, screenshots, and validation logs by default.
4. Never save API keys, bearer tokens, cookies, auth headers, admin-session tokens, vault passwords, or desktop plaintext key-file contents.
5. Keep web search as a standalone web lane unless the product boundary is explicitly changed.
6. If evidence is incomplete, downgrade the claim to `partial`, `unverified`, `unsupported`, `blocked`, or `unknown` instead of keeping an optimistic default.

## Current Source Of Truth

Treat these layers separately:

| Layer | Meaning | Primary files |
| --- | --- | --- |
| Declared capability | What AstraBridge says a provider/model should support. | `apps/astrabridge-sidecar/astrabridge_sidecar/providers/profile.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py` |
| Runtime-normalized contract | What the runtime exposes after normalization. | `apps/astrabridge-sidecar/astrabridge_sidecar/provider_model_compatibility_matrix.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py` |
| Validated evidence | What tests, dry-run outputs, smoke reports, and UI checks prove. | `PRIVATE/agentic-update-pipeline/reports/`, `PRIVATE/agentic-update-pipeline/runs/`, `PRIVATE/provider-compatibility/runs/`, `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.test.tsx` |

Do not promote a capability lane to verified using only the first two layers.

## Current Evidence Pack

The current 2026-07-06 maintenance baseline now has two distinct evidence tracks:

Docs-backed capability and reasoning audit:

- `PRIVATE/agentic-update-pipeline/reports/step1-provider-model-capability-surface-inventory-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step3-official-provider-source-registry-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step4-qwen-capability-audit-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step5-openai-yunwu-capability-audit-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step6-deepseek-kimi-glm-capability-audit-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step7-reasoning-effort-audit-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step8-runtime-gap-report-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step11-provider-capability-dry-run-matrix-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step12-bounded-live-smoke-policy-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step14-failure-taxonomy-and-fallback-behavior-20260706.md`

Current exhaustive provider-backed smoke and maintained compatibility surfaces:

- `PRIVATE/provider-compatibility/reports/step1-exhaustive-scope-inventory-20260706.md`
- `PRIVATE/provider-compatibility/reports/step5-exhaustive-runner-preflight-batching-resume-20260706.md`
- `PRIVATE/provider-compatibility/reports/step6-exhaustive-batch-a-general-model-20260706-r8.md`
- `PRIVATE/provider-compatibility/reports/step7-exhaustive-batch-b-vision-analyze-20260706.md`
- `PRIVATE/provider-compatibility/reports/step8-exhaustive-batch-c-speech-transcribe-20260706.md`
- `PRIVATE/provider-compatibility/reports/step9-exhaustive-batch-d-speech-synthesize-20260706.md`
- `PRIVATE/provider-compatibility/reports/step10-exhaustive-batch-e-image-generate-20260706.md`
- `PRIVATE/provider-compatibility/reports/step11-exhaustive-batch-f-continuation-20260706.md`
- `PRIVATE/provider-compatibility/runs/step12-exhaustive-compatibility-matrix-20260706/matrix.json`
- `PRIVATE/provider-compatibility/runs/step12-exhaustive-compatibility-matrix-20260706/summary.json`
- `PRIVATE/provider-compatibility/reports/step12-exhaustive-final-readiness-20260706.md`

Current exact exhaustive totals:

- total classified lanes: `185`
- outcomes: `pass=36`, `partial=38`, `fail=19`, `reduced-authority=6`, `skipped=28`, `unsupported=58`
- model promotion totals from the maintained matrix: `verified=1`, `partial=13`, `blocked=8`, `unknown=1`
- official OpenAI direct provider-backed verification remains explicitly deferred by scope

Use the Step 12 exhaustive matrix summary and final readiness report before creating new provider-backed compatibility claims or re-running broad live validation.

## Artifact And Evidence Conventions

Write new evidence to one of these roots:

- `PRIVATE/agentic-update-pipeline/reports/` for human-readable audit and policy notes
- `PRIVATE/agentic-update-pipeline/runs/<run_id>/` for dry-run matrix and generated validation outputs
- `PRIVATE/provider-compatibility/runs/<run_id>/` for provider-backed smoke runs
- `PRIVATE/provider-compatibility/screenshots/` for UI or browser evidence

Minimum evidence to preserve for each meaningful change:

- what changed
- provider and model ids
- capability ids or reasoning fields affected
- exact validation commands run
- pass/fail/partial outcome
- sanitized failure class when something did not pass
- next fix target if the lane remains non-verified

## Maintenance Workflow

Follow these steps in order.

### 1. Read The Active Contract

Before touching code:

1. Read `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
2. Read `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`.
3. Read the latest relevant report under `PRIVATE/agentic-update-pipeline/reports/`.
4. Decide whether the change is:
   - metadata-only
   - transport or reasoning mapping
   - capability-route truthfulness
   - request-shape validation
   - user-visible status/observability

If working under the numbered execution plan, complete exactly one numbered step and update the plan before stopping.

### 2. Refresh Official Sources First

For any provider/model behavior change:

1. Check official docs for:
   - model list and deprecation status
   - supported input/output modalities
   - tool-calling and streaming behavior
   - context or token limits
   - reasoning/thinking controls
2. Update the source registry when the docs set changed:
   - `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`
3. Record the new source in a report under `PRIVATE/agentic-update-pipeline/reports/` if the drift is meaningful.

Primary-source-first rule:

- provider docs: authoritative
- preserved live evidence: authoritative for actual runtime behavior
- OpenRouter: secondary abstraction reference only

### 3. Update Declared Capability Surfaces

Change the smallest correct surface:

- provider defaults or protocol rules: `providers/profile.py`
- model-level metadata: catalog sources or generated catalog
- capability-route eligibility: `capabilities/capability_registry.py`
- transport-specific normalization: `providers/transports/*.py`
- runtime/provider contract shaping: `model_catalog/catalog.py`

If a model under a provider differs from siblings, prefer model-level metadata over provider-wide booleans.

### 4. Update Reasoning And Thinking Normalization

When reasoning controls change:

1. Confirm the provider's official field names and allowed values.
2. Update normalization code and contract metadata.
3. Keep four states explicit:
   - documented mapping
   - inferred mapping
   - unsupported mapping
   - noop or pass-through mapping

Primary files:

- `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/*.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`
- `apps/astrabridge-sidecar/tests/test_reasoning_policy_normalization.py`
- `apps/astrabridge-sidecar/tests/test_model_catalog_contract.py`

### 5. Add Or Tighten Static Validation

If docs reveal provider-specific request restrictions, add local validation before provider call where possible.

Typical cases:

- image dimension or image-source restrictions
- audio-only content requirements
- parameters that must be omitted rather than set to zero
- fixed-temperature or non-thinking restrictions
- tool schema incompatibilities

Typical files:

- `apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/*.py`
- `apps/astrabridge-sidecar/tests/*`

### 6. Refresh The Matrix And Dry-Run Evidence

After code changes:

1. Re-run the relevant unit tests.
2. Re-run the dry-run matrix when capability truth, reasoning mapping, or route eligibility changed.
3. Keep unsupported, unverified, and blocked outcomes visible; do not filter them out.

Current dry-run generator:

- `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py`

Expected outputs:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/`
- `PRIVATE/provider-compatibility/runs/<run_id>-capability-smoke/`

### 7. Run Managed-Key Live Smoke Only When Authorized

Managed-key live smoke is optional and bounded.

Requirements before live smoke:

1. The user explicitly authorizes provider-backed calls for the current turn.
2. The target case is justified by risk or uncertainty.
3. The run stays within the current bounded smoke policy.
4. New artifacts remain secret-free.

Current policy reference:

- `PRIVATE/agentic-update-pipeline/reports/step12-bounded-live-smoke-policy-20260706.md`

Current live-smoke runner:

- `POST /api/runtime/provider-compatibility-smoke`

### 8. Check User-Facing Status Surfaces

If capability truth changed, verify the desktop UI does not overstate support.

Primary surface:

- `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.tsx`

Current guardrails:

- route header shows model-level status
- candidate list shows per-model status
- unsupported or unverified lanes are not presented as fully available
- partial smoke evidence remains visibly partial

### 9. Scan Secrets And Define Rollback

Before finishing:

1. Run a focused secret scan over changed code, docs, and new evidence paths.
2. Confirm no raw secrets were staged or persisted.
3. Record rollback scope:
   - profile/catalog entries
   - transport mapping changes
   - validator changes
   - UI status changes
   - generated evidence paths

Rollback means reverting compatibility claims and code paths, not deleting preserved evidence unless the user explicitly requests cleanup.

## Current Validation Commands

Use the smallest relevant set for the change. Start with the consolidated no-live verification gate, then rerun exhaustive provider-backed smoke only when the current change actually affects managed live behavior.

### Single Verification Gate

Default no-live-provider gate:

```powershell
cd D:\AstraBridge
python scripts\run_provider_capability_verification_gate.py --run-id provider-capability-gate-YYYYMMDD
```

What it does:

- runs the focused static request-shape, matrix-contract, reasoning-mapping, and dry-run-gate unittest groups
- runs the provider capability dry-run matrix with no live provider calls
- compares current dry-run blockers against the tracked baseline in `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate_baseline.json`
- writes a gate summary and report under `PRIVATE/agentic-update-pipeline/runs/<run_id>/`

Default behavior:

- live provider calls: disabled
- managed keys: not required
- failure conditions: unittest failure, unexpected preview blocker, or unexpected conflicting capability case

### Sidecar Catalog And Matrix

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest tests.test_provider_source_registry tests.test_provider_catalog_contract tests.test_model_catalog_contract tests.test_provider_model_compatibility_matrix
```

### Reasoning And Transport Normalization

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest tests.test_reasoning_policy_normalization
```

Add focused transport or sidecar tests when relevant, for example:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_provider_profiles_seed_reasoning_and_temperature_defaults tests.test_sidecar_services.AstraBridgeServiceTests.test_profile_service_defaults_reasoning_effort_from_provider_profile_when_missing tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_config_service_defaults_reasoning_effort_from_provider_profile_when_missing
```

### Capability Routing And Dry-Run Matrix

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest tests.test_capability_registry tests.test_capability_smoke tests.test_provider_capability_dry_run_matrix tests.test_provider_compatibility_smoke
```

### Frontend Observability

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
npm.cmd test -- --run src/features/capabilities/CapabilityRoutesPanel.test.tsx
node .\node_modules\typescript\bin\tsc --noEmit
```

### Diff Hygiene

```powershell
cd D:\AstraBridge
git diff --check --
```

## Change Playbooks

### Example A: Add A New Qwen Multimodal Model

Goal: add a new Qwen model that supports text plus one or more multimodal lanes.

1. Verify official Qwen or DashScope docs for:
   - exact model id
   - input modalities
   - reasoning/thinking behavior
   - any request-shape limits
2. Update source registry if the new official doc source is not already recorded.
3. Add or update the model record in the catalog/generation path.
4. Ensure `input_modalities` are model-specific, not provider-wide.
5. Update capability routing only for the lanes the model truly supports.
6. Add tests for:
   - capability registry eligibility
   - reasoning normalization if thinking behavior differs
   - request-shape validation if the lane has Qwen-specific restrictions
7. Re-run dry-run matrix generation.
8. If the user authorizes live smoke, run one representative provider-backed lane only, such as `vision.analyze` or `speech.transcribe`.
9. If a different Qwen lane still fails, keep the new lane partial or scoped instead of promoting all Qwen multimodal capability together.

Minimum validation:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest tests.test_capability_registry tests.test_vision_analyze_adapter tests.test_speech_transcribe_adapter tests.test_speech_synthesize_adapter tests.test_reasoning_policy_normalization
```

### Example B: Change An OpenAI Reasoning-Effort Mapping

Goal: adjust how AstraBridge maps OpenAI or OpenAI-compatible reasoning controls into runtime-safe values.

1. Check current official OpenAI docs for supported reasoning-effort semantics and allowed values.
2. Decide whether the mapping is:
   - official and documented
   - compatible-provider-only
   - inferred fallback
3. Update normalization code and contract metadata.
4. Keep official OpenAI claims separate from Yunwu/OpenAI-compatible live evidence.
5. Update or add unit tests that cover:
   - contract output
   - transport payload shape
   - default selection behavior
6. Update the reasoning audit report if the change is material.
7. Re-run dry-run matrix or focused reasoning checks.

Minimum validation:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest tests.test_reasoning_policy_normalization tests.test_model_catalog_contract tests.test_provider_catalog_contract
```

### Example C: Add A New Provider

Goal: onboard a new provider without disturbing existing provider truthfulness.

1. Record official source URLs and update `source_registry.py`.
2. Create or update the provider profile:
   - protocol
   - base URL
   - auth env vars
   - default model
   - fallback models
   - context policy
   - reasoning mode
   - tool/edit/web policy
3. Add transport support if the wire protocol is not already covered.
4. Seed conservative model metadata first; do not mark multimodal or advanced tools verified by default.
5. Add capability routing only for lanes justified by model-level metadata.
6. Add focused tests for catalog contract, reasoning normalization, and capability routing.
7. Generate a dry-run matrix slice for the provider.
8. Only after user authorization, run one text baseline and at most one representative advanced lane.
9. Update UI surfaces if the provider introduces new warning semantics or capability states.

Minimum validation:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest tests.test_provider_source_registry tests.test_provider_catalog_contract tests.test_model_catalog_contract tests.test_capability_registry tests.test_reasoning_policy_normalization
```

## Promotion Rules

A provider/model/capability lane can be promoted only when:

- declared capability and runtime-normalized contract agree
- model-level modality truth is explicit
- relevant static validation exists for known request-shape pitfalls
- focused tests pass
- dry-run evidence is current
- optional live smoke, if used, is authorized and preserved
- UI status surfaces reflect the result honestly
- secret scan passes

If any of those are missing, keep the lane non-verified and record the exact next repair target.

## Handoff Expectations

Every future maintenance turn should end with:

- files changed
- validation commands run
- evidence paths produced or refreshed
- residual risks
- exact next step entry point

When this runbook and the execution plan disagree, the numbered execution plan wins for current-step sequencing, and this runbook supplies the reusable operating procedure.
