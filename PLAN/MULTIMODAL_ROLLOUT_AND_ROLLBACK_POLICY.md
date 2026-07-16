# Multimodal Rollout And Rollback Policy

Last updated: 2026-07-07

## Goal

Keep multimodal provider and model updates safe by default. A provider or model may be
documented, wired, or smoke-verified without being automatically exposed. Exposure
changes require explicit scope selection, evidence, and a reversible path.

## Scope Controls

Use the maintenance rollout gate as the narrow control plane:

- Script: `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_rollout_gate.py`
- Required base scope: `provider_metadata` and/or `capability_routes`
- Optional scope filters:
  - provider-specific: `--provider <provider_id>`
  - model-specific: `--model <provider/model>`
  - model-family-specific: `--model-family <family_id>`
  - stable-only updates: `--version-policy stable`
  - pinned-version updates: `--version-policy pinned --target-version <version>`
- Promotion intent:
  - `proposal_only`: gather evidence only; never treat the run as promotion-ready
  - `verify_candidate`: candidate passed technical gates but still requires manual promotion review
  - `promote_after_smoke`: all required evidence is present and the candidate is eligible for manual promotion review

Default-safe behavior:

- `approval_policy=manual_review_required`
- `allow_code_changes=false`
- `allow_install=false`
- `allow_provider_calls=false` unless a live-smoke summary is explicitly required

## Required Gates Before Exposure

An exposure change is allowed only when all of the following are true for the
targeted scope:

1. The rollout run contract validates successfully.
2. Required matrix reconcile evidence exists and points to a valid dry-run summary.
3. The provider capability verification gate passes.
4. Required live smoke passes, or every non-pass lane is already classified and
   explicitly accepted through `--allow-nonpass-lane`.
5. The resulting rollout decision is either `candidate_verified` or
   `eligible_for_manual_promotion`.
6. A human review still approves the change.

If any gate fails, the run must end in a blocked state and the lane remains hidden,
blocked, or `wired_unverified`.

## Evidence Outputs

The rollout gate now writes a reusable decision bundle under the standard
agentic-update run root:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/run-contract.json`
- `PRIVATE/agentic-update-pipeline/runs/<run_id>/rollback/rollout-gate-summary.json`
- `PRIVATE/agentic-update-pipeline/runs/<run_id>/rollback/multimodal-rollout-decision.json`
- `PRIVATE/agentic-update-pipeline/runs/<run_id>/rollback/linked-evidence.json`
- `PRIVATE/agentic-update-pipeline/runs/<run_id>/rollback/rollback-manifest.json`

These artifacts are secret-free and must be preserved. They point to the linked
matrix summary, verification summary, and live-smoke summary without copying secrets.

## Rollback Rules

Rollback must revert exposure state without deleting evidence. The rollback path is:

1. Read `rollback/multimodal-rollout-decision.json` to identify the regressed lanes.
2. Hide or block the affected runtime lanes first in:
   - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`
3. Revert promoted catalog or seed visibility state in:
   - `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`
4. Downgrade any overclaimed documented support state when needed in:
   - `PLAN/MULTIMODAL_PROVIDER_OFFICIAL_SOURCE_PACK.md`
5. Re-run dry-run reconcile and the rollout gate to prove the downgrade is effective.

The rollback manifest is deliberately reviewable and conservative:

- it does not delete artifacts
- it does not overwrite without backup
- it describes manual or agent-driven revert steps rather than silently mutating runtime state

## Decision Semantics

- `blocked`: required evidence failed or is missing; no exposure change is allowed
- `verify_only`: technical evidence gathered under `proposal_only`; no exposure change is allowed
- `candidate_verified`: technical evidence passed under `verify_candidate`; manual promotion review may proceed
- `eligible_for_manual_promotion`: all technical evidence passed under `promote_after_smoke`; exposure change is still manual-review gated

## Implementation Ownership

- Contract normalization:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/contracts.py`
- Rollback manifest contract:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/artifacts.py`
- Generic validation gate behavior:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/validation.py`
- Multimodal rollout wrapper:
  - `apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_rollout_gate.py`

## Operator Rule

Never treat catalog presence, docs presence, or a single passing smoke lane as enough
for promotion. Promotion requires scoped evidence, a reviewable decision bundle, and a
rollback manifest that preserves the full trail.
