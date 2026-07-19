# Verification Matrix

Last updated: 2026-07-17

## Quick Gate

Use before handoff after repository governance, documentation, or narrow script changes.

```powershell
python scripts/run_local_gate.py --quick
```

The quick gate runs:

- `python scripts/repo_governance_check.py --repo .`
- `python scripts/app_hardening_secret_scan.py --repo .`
- `python scripts/contract_boundary_audit.py`
- `python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_repo_governance_check.py`
- `python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_app_hardening_secret_scan.py`

Expected result: no governance or secret-scan errors and passing focused checker tests. The governance pass includes canonical document-registry coverage, replacement-chain validation, current-guidance local-link checks, mojibake checks, and retired-path guardrails.

## Focused Gate

Use when a change touches a product subsystem. Run the quick gate plus the nearest targeted tests.

Examples:

```powershell
python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_web_lane.py

python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_protocol_schema.py
python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_protocol_persistence.py
python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_durable_run_store.py

cd apps/astrabridge-desktop
npm.cmd test -- src/features/i18n/catalog.test.ts
npm.cmd test -- src/astrabridge_protocol/generated/v1.test.ts
npm.cmd test -- src/features/ui/uiSystem.test.ts src/features/navigation/SetupLandingPanel.test.tsx
```

Expected result: quick gate passes and the touched subsystem's regression tests pass.

For shared UI density, tooltips, or surface hierarchy changes, also capture a desktop and a `900x760` in-app-browser screenshot. Include one keyboard-focus, hover-tooltip, or disabled-control state when the browser control channel is available.

## Full Local Gate

Use before release preparation or broad cross-subsystem handoff.

```powershell
python scripts/run_local_gate.py --full
```

The full gate runs:

- governance check
- governance-script tests
- sidecar unittest discovery
- desktop test suite
- desktop build

The desktop build may emit the existing Vite chunk-size warning. Treat new TypeScript, Vite, or test failures as blockers.

## Release Gate

Use the promotion gate for CI-bound PR, nightly, and release decisions:

```powershell
python scripts/run_promotion_gate.py --mode pr --expected-commit <sha>
python scripts/run_promotion_gate.py --mode nightly --expected-commit <sha>
python scripts/run_promotion_gate.py --mode release --expected-commit <sha>
```

Expected result: required checks cannot promote if the worktree is dirty, the evaluated commit differs from the expected commit, a required summary or report is missing, or any required status resolves to `skipped`, `missing`, `unknown`, or another unevaluated state.

Use the release-readiness gate when package identity, staging contents, or release-bound source inventory changes:

```powershell
python scripts/run_release_readiness_gate.py --run-id local-readiness
```

Expected result: one canonical release identity matches Desktop, Sidecar, Tauri, MCP metadata, and protocol compatibility consumers; two clean staging runs produce identical inventories and hashes; and the staged workspace excludes forbidden local and development paths.

Use `docs/RELEASE_CHECKLIST.md` for release-specific validation. Release validation should include:

- full local gate
- release promotion gate
- release readiness gate
- secret scan over staged or release-bound changes
- browser UI screenshot QA for changed screens
- provider-key smoke only when explicitly authorized
- artifact provenance review for any newly committed visual assets

## Failure Handling

- Fix `error` governance findings before handoff.
- Review `warning` findings and either fix them or document why they are intentional.
- Keep raw evidence and logs unless the user explicitly names cleanup targets.
- If a validation command cannot run, record the command, blocker, and next entry point in the final handoff.
