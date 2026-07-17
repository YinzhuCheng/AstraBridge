# Runtime Rollout And Maintenance Runbook

Last updated: 2026-07-17

## Purpose

This runbook defines the final rollout, migration, rollback-readback, and maintenance boundary for the AstraBridge stability plan.

Use it when you need to prove that the current durability spine can be rolled out, compared in shadow mode, migrated from legacy task JSON, and inspected after rollback rehearsal without deleting durable state.

The rollout gate owner is:

- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`
- wrapper: `scripts/run_runtime_rollout_gate.py`

## What The Rollout Gate Must Prove

The gate is not just another test runner. It must prove all of the following in one preserved evidence bundle:

1. Feature-flag and compatibility-window state is explicit for:
   - runtime client pool / lane isolation
   - protocol v1 schemas and generated types
   - durable scheduler and durable store
   - agent envelope / delivery ledger
   - MCP shared core and broker boundary
2. Shadow comparison reuses one executed run per case and compares projections only:
   - legacy run manifest
   - compact task `graph_run_ref`
   - durable run-store projection
3. Legacy migration is exercised twice:
   - a controlled fixture workspace
   - a bounded dogfood workspace copy
4. Active legacy runs are classified as:
   - `terminal`
   - `recoverable`
   - `needs_review`
5. Rollback-readback proves that:
   - new durable evidence remains readable from a copied workspace
   - the durable store is not deleted
   - the durable store is not mutated by readback alone
6. The nested runtime stability release gate passes.
7. Desktop build and screenshot-based visual QA pass.
8. A secret scan over rollout artifacts passes.

## Normal Command

```powershell
python scripts/run_runtime_rollout_gate.py --run-id final-rollout
```

Artifacts are written under:

- `PRIVATE/runtime-rollout/<run-id>/raw/`
- `PRIVATE/runtime-rollout/<run-id>/reports/`
- `PRIVATE/runtime-rollout/<run-id>/screenshots/`
- `PRIVATE/runtime-rollout/<run-id>/validations/`

The nested runtime stability release gate is preserved under:

- `PRIVATE/runtime-rollout/<run-id>/runtime-stability/`

## Shadow Comparison Policy

Shadow comparison must not execute the same side effect twice.

Allowed pattern:

1. execute one fixture run
2. derive legacy/compact/durable projections from that single run
3. compare stable fields only
4. record any explained extra projections such as `run-export.json`

Forbidden pattern:

1. execute one "old" run
2. execute another "new" run
3. compare those two runs as if they were the same side effect

## Legacy Migration Policy

The migration lane must preserve source files.

- Never delete or overwrite source `tasks.json`.
- Never auto-resume a legacy active run.
- Terminal runs may import as terminal evidence.
- Recoverable active runs may be marked recoverable, but still require explicit operator recovery/requeue.
- Unsafe paths or ambiguous active states must become `needs_review`.

## Rollback-Readback Policy

Rollback in this scope means compatibility readback, not destructive reset.

Required properties:

- a copied workspace can load a new durable run
- a copied workspace can rebuild a durable projection
- the original durable SQLite file hash is unchanged by readback
- no rollback proof may delete `durable_runs.sqlite3`, ordered events, artifacts, or diagnostics

Do not solve rollback by removing durable artifacts. Rollback here is an inspectability guarantee.

## Maintenance Boundary

When maintaining the rollout gate:

1. keep `runtime_rollout_feature_flags()` aligned with the current always-on runtime contract
2. keep the shadow comparison state matrix aligned with real terminal/approval/retry/cancel/artifact cases
3. keep the dogfood migration lane bounded to a copied workspace
4. keep the rollout secret scan enabled
5. keep the nested runtime stability release gate in `release` mode for close-out runs

## Close-Out Rule

The stability plan may only be marked complete when:

- the rollout gate passes
- the nested runtime stability release gate passes
- the plan file marks Step 22 complete
- no numbered plan step remains incomplete
