# Codex Kernel Upgrade Runbook

Last updated: 2026-06-25

## Purpose

This runbook defines the agent-assisted workflow for evaluating an official Codex CLI/kernel upgrade inside AstraBridge without relying on guesswork or undocumented local state.

Use it when you need to:

- point AstraBridge at a different Codex CLI binary
- capture before/after kernel probe evidence
- decide whether a candidate kernel should stay `blocked`, `partial`, `probed`, or `verified`
- preserve a rollback path when a candidate kernel regresses AstraBridge behavior

This runbook is written for the current repository state on 2026-06-25. At this point:

- the compatibility matrix exists in [PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md)
- the secret-free kernel probe contract exists in [PLAN/CODEX_KERNEL_PROBE_CONTRACT.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_PROBE_CONTRACT.md)
- the sidecar exposes `/api/runtime/kernel-probe`
- the Runtime tab shows the probe snapshot
- the deterministic kernel smoke suite and verified-status gate are not implemented yet

Because step 12 and step 13 are not complete yet, this runbook has two paths:

1. a `probe-only` path that is executable today and may promote a candidate only to `probed` or `partial`
2. a `full verification` path that becomes active after step 12 and step 13 land

## Hard Rules

Do all upgrade rehearsals under these rules:

- Do not write official Codex `~/.codex/config.toml`.
- Do not create or edit project `.codex/` or project `.codex*` files.
- Do not store API keys, bearer tokens, cookies, auth headers, refresh tokens, or provider raw secrets in git-tracked files, docs, logs, reports, screenshots, or matrix notes.
- Do not mark a kernel `verified` unless the compatibility matrix entry has both probe evidence and a preserved smoke artifact path.
- Do not treat UI visibility or a single successful `codex --version` call as proof of full compatibility.
- Preserve evidence by default under `PRIVATE/demo-runs/**`, but keep it secret-safe.

Reference policy:

- [docs/SECURITY_AND_ISOLATION.md](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)
- [PLAN/CODEX_KERNEL_PROBE_CONTRACT.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_PROBE_CONTRACT.md)
- [PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md)

## Current Baseline

As of 2026-06-25, the tracked baseline is:

- release anchor: `codex-cli 0.137.0` / `rust-v0.137.0` / released 2026-06-04
- known local Windows binary: `D:\Tools\OpenAI\Codex\bin\codex.EXE`
- current Windows matrix state: `probed`
- current WSL target-line state: `partial`

This means AstraBridge has evidence for the baseline version, but does not yet have the smoke evidence required for `verified`.

## Preconditions

Before changing anything:

1. Ensure the repo is on the intended branch/worktree.
2. Ensure an AstraBridge project is open so the Runtime APIs have a valid project context.
3. Decide which lane you are testing:
   - `windows`
   - `wsl`
4. Decide whether you are:
   - only pointing AstraBridge at an already-installed candidate binary
   - or installing a candidate binary outside the repo and then pointing AstraBridge at it
5. Record the current binary locator before changing it.

## Evidence Workspace

Use a fresh isolated workspace for each upgrade rehearsal.

Recommended PowerShell preflight:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$evidenceRoot = "D:\AstraBridge\PRIVATE\demo-runs\codex-kernel-upgrade-$stamp"
New-Item -ItemType Directory -Force -Path `
  $evidenceRoot, `
  "$evidenceRoot\api", `
  "$evidenceRoot\notes", `
  "$evidenceRoot\reports" | Out-Null

$env:ASTRABRIDGE_APPDATA = "$evidenceRoot\AppData"
$env:ASTRABRIDGE_CODEX_HOME = "$evidenceRoot\CodexHome"
```

Use isolated roots so the rehearsal does not contaminate your normal runtime state.

## Candidate Selection Rules

### Windows lane

Point AstraBridge at a candidate Windows binary with:

```powershell
$env:ASTRABRIDGE_CODEX_BIN = 'D:\Tools\OpenAI\Codex\bin\codex.EXE'
```

Replace the path with the exact candidate binary you are evaluating.

### WSL lane

Point AstraBridge at a Linux-native candidate binary with:

```powershell
$env:ASTRABRIDGE_WSL_CODEX_BIN = '$HOME/.local/share/astrabridge/bin/codex'
```

Additional WSL rules:

- the candidate must be Linux-native
- it must not resolve to WindowsApps inside WSL
- keep `CODEX_HOME` isolated under the AstraBridge-managed WSL path

## Start Or Restart The Sidecar

After setting the lane-specific environment variables, restart the sidecar process so the new binary locator is definitely active.

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m astrabridge_sidecar.server --serve --port 8826 --seed-root D:\AstraBridge
```

Optional preview launch when you want the Runtime UI visible during the rehearsal:

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
cmd /c npm run preview -- --host 127.0.0.1 --port 4181
```

## Probe-Only Upgrade Checklist

Use this path today. It is the executable workflow for the current repo state.

### 1. Capture the current probe snapshot

```powershell
Invoke-WebRequest 'http://127.0.0.1:8826/api/runtime/kernel-probe' |
  Select-Object -ExpandProperty Content |
  Set-Content "$evidenceRoot\api\kernel-probe-after-switch.json"
```

If you want a pre-change snapshot too, run the same call before changing the binary and save it as `kernel-probe-before-switch.json`.

### 2. Record the exact candidate facts

Write a short note under `notes\candidate.txt` that includes:

- lane: `windows` or `wsl`
- binary path or locator
- expected target version
- who initiated the rehearsal
- whether the candidate replaced the baseline or is only under evaluation

### 3. Read the probe result before making any judgement

Inspect these fields in the probe snapshot:

- `observed.binary.path`
- `observed.binary.version_semver`
- `observed.app_server.initialize_status`
- `observed.mcp_features.server_status_list_status`
- `observed.plugin_features.list_status`
- `observed.skill_features.list_status`
- `inferred.compatibility_status`
- `known_warnings`

Required interpretation rules:

- missing binary or failed version parse is a `blocked` outcome
- a successful probe without smoke evidence may be `partial` or `probed`
- `disabled_by_app` plugin state is expected today and is not by itself proof of kernel failure

### 4. Compare against the compatibility matrix

Open [PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md) and decide which case applies:

- exact version/platform row already exists and the candidate behaves the same
- exact version/platform row already exists and the candidate behaves worse
- exact version/platform row does not exist yet

Current matrix update rules:

- use `blocked` for clearly incompatible behavior
- use `partial` when only limited evidence exists
- use `probed` when the probe coverage is acceptable but smoke evidence is still missing
- do not use `verified` yet

### 5. Preserve a matrix update note

Create `reports\matrix-update-note.md` with:

- exact candidate version
- exact lane
- chosen matrix status
- summary of warnings
- links or relative paths to saved probe JSON
- whether rollback was required

### 6. Stop if the candidate is only `partial` or `probed`

For the current repo state, this is the normal stop point.

Until step 12 and step 13 are implemented:

- do not promote the candidate to `verified`
- do not rewrite the matrix to claim smoke success
- keep the evidence and note the missing follow-up as `kernel_smoke_suite`

## Full Verification Checklist

Use this path only after step 12 and step 13 are complete.

### 1. Run the canonical kernel smoke suite

Expected future behavior:

- one deterministic no-key command
- one preserved smoke artifact root under `PRIVATE/demo-runs/codex-kernel-smoke-*`
- explicit pass/fail for binary discovery, app-server start, minimal thread lifecycle, MCP visibility, plugin discovery, skill discovery, and other scoped checks

### 2. Confirm the smoke artifact is tied to the exact candidate

Before updating the matrix to `verified`, confirm all of these:

- the artifact path is preserved
- the artifact references the exact binary locator
- the artifact references the exact version
- the artifact references the exact lane
- the probe snapshot and smoke artifact do not contradict each other

### 3. Update the matrix only after the gate passes

Only then may a matrix row move to `verified`.

Required matrix fields:

- `codex_version`
- `platform`
- `binary_locator`
- `overall_status`
- `probe_result`
- `smoke_result`
- `known_breakages`
- `required_mitigations`
- `evidence_paths`

## Rollback Checklist

Run rollback immediately when the candidate becomes `blocked` or regresses a previously acceptable lane.

### 1. Restore the prior binary locator

For Windows:

```powershell
$env:ASTRABRIDGE_CODEX_BIN = 'D:\Tools\OpenAI\Codex\bin\codex.EXE'
```

For WSL:

```powershell
$env:ASTRABRIDGE_WSL_CODEX_BIN = '$HOME/.local/share/astrabridge/bin/codex'
```

If the prior value was different, restore that exact value instead.

### 2. Restart the sidecar

Restart the sidecar process after restoring the prior locator.

### 3. Capture the rollback probe snapshot

Save a fresh probe JSON, for example:

```powershell
Invoke-WebRequest 'http://127.0.0.1:8826/api/runtime/kernel-probe' |
  Select-Object -ExpandProperty Content |
  Set-Content "$evidenceRoot\api\kernel-probe-after-rollback.json"
```

### 4. Record the blocker clearly

Write `reports\rollback-note.md` with:

- candidate version and locator
- restored version and locator
- blocker summary
- whether the regression was Windows-only, WSL-only, or both
- whether the matrix needs a new `blocked` row or an updated warning

## Minimal Acceptance Decisions

Use this decision table after each rehearsal:

| Outcome | Meaning | Required action |
| --- | --- | --- |
| `blocked` | Candidate clearly breaks AstraBridge compatibility | Roll back immediately and preserve rollback evidence |
| `partial` | Candidate has some acceptable signals, but evidence is weak or incomplete | Keep evidence, do not promote baseline |
| `probed` | Candidate passes probe expectations, but smoke evidence is missing | Keep evidence, do not promote baseline |
| `verified` | Candidate has both probe and smoke evidence | Allowed only after step 12 and step 13 exist |

## Required Closeout

Before ending the rehearsal:

1. Confirm no official Codex user config was written.
2. Confirm no project `.codex*` files were created.
3. Confirm saved evidence contains no raw secrets.
4. Confirm the matrix note points to the probe JSON path.
5. Confirm rollback state is documented when rollback occurred.

Example changed-file secret scan:

```powershell
cd D:\AstraBridge
$paths = @(
  'docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md',
  'PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md'
)
git diff --unified=0 -- $paths |
  Select-String -Pattern '(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|api[_-]?key\s*[:=]\s*[^\s,]+' -AllMatches
```

Expected result:

- no real secrets
- redacted examples only when clearly documented as examples

## Current Stop Rule

For the repository state on 2026-06-25:

- use this runbook to capture isolated before/after probe evidence
- update the matrix only to `blocked`, `partial`, or `probed`
- preserve notes under `PRIVATE/demo-runs/codex-kernel-upgrade-*`
- wait for step 12 and step 13 before claiming `verified`
