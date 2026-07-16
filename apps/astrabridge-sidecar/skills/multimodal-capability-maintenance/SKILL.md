---
name: multimodal-capability-maintenance
description: Maintain AstraBridge multimodal provider/model/capability support across doc sync, dry-run matrix reconcile, provider-backed smoke, rollout gating, and bounded adapter repair handoff. Use when AstraBridge needs a repeatable workflow for `image.generate`, `vision.analyze`, `speech.transcribe`, or `speech.synthesize` compatibility updates, evidence refresh, route/exposure reconciliation, or safe rollout decisions without reconstructing chat history.
---

# Multimodal Capability Maintenance

Use this skill for multimodal maintenance runs under
`PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`.

Use the existing repository surfaces first. This skill is an orchestrator, not a
parallel implementation of routing or smoke logic.

## Preserve First

1. Preserve `PRIVATE/**`, smoke runs, dry-run reports, request/response artifacts, and validation logs by default.
2. Never persist API keys, auth headers, cookies, vault contents, desktop plaintext key contents, or provider raw secrets.
3. Only run provider-backed smoke when the user explicitly authorizes provider calls or a managed-key session is already in scope for the task.

## Read Before Acting

1. Read [references/maintenance-surfaces.md](references/maintenance-surfaces.md).
2. If the task is lane repair, also read:
   - `apps/astrabridge-sidecar/skills/provider-capability-repair/SKILL.md`
3. If the task is broad update discovery or promotion scope control, also read:
   - `apps/astrabridge-sidecar/skills/agentic-update-pipeline/SKILL.md`
   - `apps/astrabridge-sidecar/skills/model-metadata-curator/SKILL.md`

## Workflow

### 1. Doc Sync Index

Build the canonical multimodal source index before claiming anything about provider support:

```powershell
.\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/sync_multimodal_source_index.py --workspace-root . --out PRIVATE/agentic-update-pipeline/runs/<run_id>/doc-sync/source-index.json
```

Use this output to decide which provider-owned URLs are authoritative, promotable,
and stale enough to re-check.

If the task includes network discovery, then use the source index together with
`model-metadata-curator/scripts/collect_metadata.py`; keep fetched results under the
current run directory and keep capability claims conservative until later gates pass.

### 2. Matrix Reconcile

Run the dry-run multimodal matrix and, when requested, the verification gate:

```powershell
.\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_matrix_reconcile.py --workspace-root .
```

This script wraps:

- `astrabridge_sidecar.provider_capability_dry_run_matrix.run_provider_capability_dry_run_matrix`
- `astrabridge_sidecar.provider_capability_verification_gate.run_provider_capability_verification_gate`

Use the dry-run output to classify `documented`, `wired`, `verified`, and `exposed`
states before spending provider credits.

### 3. Provider-Backed Smoke

Run bounded multimodal live smoke through the sidecar runtime instead of ad hoc
requests:

```powershell
.\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_live_smoke.py --sidecar http://127.0.0.1:8791 --workspace-root .
```

Use the default representative set unless the task needs explicit lanes:

- `image.generate`
- `vision.analyze`
- `speech.transcribe`
- `speech.synthesize`

The script writes a secret-free wrapper bundle with:

- `preflight.json`
- `case-pack.json`
- `lane-index.json`
- `summary.json`

and links back to the sidecar-generated provider smoke report.

### 4. Rollout Gate

Run the rollout gate after dry-run reconcile and any required live smoke:

```powershell
.\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/multimodal-capability-maintenance/scripts/run_multimodal_rollout_gate.py --workspace-root . --artifact-root PRIVATE/agentic-update-pipeline/runs/<run_id>/rollout-gate --run-id <run_id> --require-matrix-summary PRIVATE/agentic-update-pipeline/runs/<run_id>/matrix/summary.json --require-live-smoke-summary PRIVATE/agentic-update-pipeline/runs/<run_id>/live-smoke/summary.json
```

Use `--allow-nonpass-lane <lane_id>` only for already-classified blockers that are
explicitly accepted for the current decision.

Use scope controls to keep promotion bounded:

- `--provider <provider_id>`
- `--model <provider/model>`
- `--model-family <family_id>`
- `--version-policy stable|pinned|latest|deprecated_check|security_fix_only`
- `--target-version <version>` when `--version-policy pinned`
- `--apply-mode proposal_only|verify_candidate|promote_after_smoke`

The rollout gate is the decision point for:

- keep blocked/hidden lanes blocked
- allow metadata-only refresh without exposure
- allow exposure changes only when dry-run, tests, and required live smoke all align

The rollout gate also writes:

- a normalized run contract
- a rollout decision bundle
- linked evidence pointers
- a rollback manifest that preserves artifacts and identifies the revert surfaces

### 5. Lane Repair

When a lane fails or drifts, hand off to the repair skill instead of patching blind:

1. Identify the failing case JSON from the smoke run.
2. Run:

```powershell
.\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/provider-capability-repair/scripts/diagnose_capability_case.py --case <case.json>
```

3. Patch the smallest correct surface.
4. Re-run focused unit tests.
5. Re-run only the affected dry-run or provider-backed smoke lane.

## Owned Scripts

- [scripts/sync_multimodal_source_index.py](scripts/sync_multimodal_source_index.py)
- [scripts/run_multimodal_matrix_reconcile.py](scripts/run_multimodal_matrix_reconcile.py)
- [scripts/run_multimodal_live_smoke.py](scripts/run_multimodal_live_smoke.py)
- [scripts/run_multimodal_rollout_gate.py](scripts/run_multimodal_rollout_gate.py)

Do not duplicate logic already implemented in `astrabridge_sidecar/**` unless the
current task is explicitly to change that core behavior.

## Artifact Policy

Allowed durable writes for this skill:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/**`
- linked sidecar smoke or dry-run artifact paths created by existing runtime modules

Do not write git-tracked documentation or metadata as part of a discovery-only or
verification-only run unless the user explicitly asks for repository changes.

## Handoff

Always record:

- exact run id
- artifact root
- source index path
- dry-run matrix summary path
- live smoke summary path if executed
- rollout gate summary path if executed
- rollback manifest path if executed
- known blocked lanes and whether they were accepted or still actionable
