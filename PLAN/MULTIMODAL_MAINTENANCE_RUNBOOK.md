# Multimodal Maintenance Runbook

Last updated: 2026-07-07

## Purpose

This runbook is the maintainer-facing operating manual for AstraBridge multimodal
support. It is the final handoff artifact for:

- `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`

Use it when a future agent or maintainer needs to:

- understand the current multimodal architecture
- classify a provider/model/capability lane
- refresh provider documentation and model metadata
- run dry-run or live-smoke verification
- decide whether a lane may be promoted
- roll back exposure safely when verification regresses

## In-Scope Capability Lanes

This slice governs only:

- `image.generate`
- `vision.analyze`
- `speech.transcribe`
- `speech.synthesize`

Current priority provider set:

- `yunwu`
- `qwen`
- `kimi`
- `glm`
- `deepseek`
- `openai` as protocol-reference rows only unless the user later authorizes official live verification

## Governing Artifacts

Read these in order before changing behavior:

1. `PLAN/MULTIMODAL_CAPABILITY_SCOPE_AND_INVARIANTS.md`
2. `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`
3. `PLAN/MULTIMODAL_ADAPTER_FAMILY_CONTRACT.md`
4. `PLAN/MULTIMODAL_EXPOSURE_GATE_RULES.md`
5. `PLAN/MULTIMODAL_PROVIDER_OFFICIAL_SOURCE_PACK.md`
6. `PLAN/MULTIMODAL_ROLLOUT_AND_ROLLBACK_POLICY.md`
7. `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/SKILL.md`

## Runtime Surface Map

Primary code ownership surfaces:

- capability contracts:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`
- candidate eligibility and exposure logic:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`
- capability runtime dispatch:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`
- provider/model catalog seed state:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`
- provider documentation registry:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`
- capability dry-run and verification:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate.py`

## Current Adapter Families

Current family targets:

- `openai_compatible_image`
- `dashscope_image`
- `chat_multimodal_vision`
- `dashscope_asr`
- `dashscope_tts`

Current concrete family-facing implementation files:

- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/dashscope_image_generate_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/vision_analyze_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_transcribe_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py`

Interpretation rule:

- add metadata only when a new model fits an existing family contract
- add a new family when request envelope, artifact semantics, validation rules, or verification bar materially differ

## Support-State Semantics

Keep these distinctions explicit:

- `documented`: provider-owned or reviewed source proves the lane exists
- `wired`: AstraBridge has a concrete adapter-family path and model-level eligibility
- `verified`: current dry-run, validation, and required smoke evidence pass
- `exposed`: the lane is allowed into normal runtime surfaces

Exposure-state normalization is governed by:

- `documented_unwired`
- `wired_unverified`
- `verified_runnable`
- `blocked`
- `deprecated`
- `hidden`
- `unknown`

Never treat docs presence or catalog presence as proof of exposure eligibility.

## Standard Maintenance Workflow

### 1. Refresh docs baseline

Use:

- `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/sync_multimodal_source_index.py`

Write under:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/doc-sync/**`

### 2. Reconcile matrix state

Use:

- `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_matrix_reconcile.py`

Minimum expected outputs:

- matrix summary
- dry-run summary
- dry-run matrix
- verification-gate summary when requested

### 3. Run bounded provider-backed smoke when authorized

Use:

- `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_live_smoke.py`

Minimum expected outputs:

- `preflight.json`
- `case-pack.json`
- `lane-index.json`
- `summary.json`
- linked provider smoke report

### 4. Run rollout gate

Use:

- `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_rollout_gate.py`

Required decision inputs:

- run scope
- version policy
- apply mode
- matrix summary when exposure is in scope
- live-smoke summary when provider-backed evidence is required

Current decision outputs:

- `run-contract.json`
- `rollout-gate/summary.json`
- `rollback/rollout-gate-summary.json`
- `rollback/multimodal-rollout-decision.json`
- `rollback/linked-evidence.json`
- `rollback/rollback-manifest.json`

### 5. Repair only the failing surface

Use:

- `apps/astrabridge-sidecar/skills/provider-capability-repair/SKILL.md`
- `apps/astrabridge-sidecar/skills/provider-capability-repair/scripts/diagnose_capability_case.py`

Then re-run only:

- focused unit tests
- affected dry-run lane
- affected live-smoke lane
- rollout gate if exposure semantics changed

## Promotion Rules

A lane is promotable only when all of these are true:

1. documentation is model-level and current enough for rollout
2. the lane is wired through a concrete adapter family
3. dry-run reconcile and verification gate pass
4. required live smoke passes or accepted blockers are explicitly listed
5. rollout decision is `candidate_verified` or `eligible_for_manual_promotion`
6. human review still approves the promotion

Current safety rule:

- even a passing technical decision bundle does not auto-promote exposure

## Rollback Rules

Rollback must preserve evidence and revert exposure in this order:

1. hide or block the regressed runtime lane in `capability_registry.py`
2. revert promoted catalog or seed visibility in `generated_catalog.py`
3. downgrade any overclaimed documentation-backed support state
4. rerun matrix reconcile and rollout gate to prove the downgrade

The canonical rollback decision surface is:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/rollback/rollback-manifest.json`

## Known Evidence Packs

Useful baseline artifacts already in the repository:

- Step 11 dry-run matrix baseline:
  - `PRIVATE/agentic-update-pipeline/runs/multimodal-step11-dry-run-20260707/`
- Step 12 provider-backed live smoke:
  - `PRIVATE/agentic-update-pipeline/runs/multimodal-step12-live-smoke-20260707/summary.json`
- Step 13 skill-package self-check:
  - `PRIVATE/agentic-update-pipeline/runs/step13-skill-check/`
- Step 14 rollout-safety check:
  - `PRIVATE/agentic-update-pipeline/runs/step14-rollout-safety-check/`

## Remaining Risks And Deferred Work

These are not hidden. A future agent should treat them as active backlog:

1. `qwen/qwen-image-plus:image.generate` still has preserved runtime mismatch evidence from Step 12. The local adapter family and dry-run path exist, but the active sidecar runtime could not resolve an eligible explicit candidate in that live batch.
2. Live smoke remains representative coverage, not exhaustive provider/model/capability enumeration. The repository now has the mechanism to scale this up, but not a completed full-grid provider-backed run.
3. OpenAI official direct multimodal live verification is still intentionally deferred. Current evidence is docs-backed plus compatible-provider behavior, not official direct live proof.
4. Provider-specific reasoning, thinking, and non-chat multimodal protocols still evolve independently. New realtime ASR/TTS or non-chat image workflows may require new families rather than metadata-only extension.
5. Some providers remain stronger in docs and dry-run evidence than in stable provider-backed runtime evidence.

## Exact Entry Points For Future Work

Choose one of these instead of reconstructing context:

- provider docs changed:
  - start with doc sync, then matrix reconcile
- one lane failed smoke:
  - start with provider-capability-repair on the failing case JSON
- a model should be added:
  - test whether it fits an existing family contract, then update metadata and rerun dry-run
- a model should be promoted:
  - run matrix reconcile, required live smoke, then rollout gate with scoped filters
- a promoted lane regressed:
  - open the rollback manifest for the affected run and apply the recorded revert sequence

## Operator Rules

- preserve `PRIVATE/**`
- never persist secrets
- keep web search separate from multimodal model routing
- prefer unknown or blocked over optimistic inheritance
- change the smallest correct ownership surface

## Completion State

The multimodal capability adapter and update handoff plan is complete when this
runbook, the governing contracts, the maintenance skill, and the evidence packs are
all present and consistent. That state is now the baseline for future work.
