# Verification Matrix

Last updated: 2026-07-10

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

cd apps/astrabridge-desktop
npm.cmd test -- src/features/i18n/catalog.test.ts
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

Use `docs/RELEASE_CHECKLIST.md` for release-specific validation. Release validation should include:

- full local gate
- secret scan over staged or release-bound changes
- browser UI screenshot QA for changed screens
- provider-key smoke only when explicitly authorized
- artifact provenance review for any newly committed visual assets

## Failure Handling

- Fix `error` governance findings before handoff.
- Review `warning` findings and either fix them or document why they are intentional.
- Keep raw evidence and logs unless the user explicitly names cleanup targets.
- If a validation command cannot run, record the command, blocker, and next entry point in the final handoff.
