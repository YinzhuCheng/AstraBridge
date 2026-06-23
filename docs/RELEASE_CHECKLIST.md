# AstraBridge Release Checklist

Last updated: 2026-06-21

This checklist is the product-ready gate for a local AstraBridge preview build. It is written as an operator checklist, not just a developer reminder list.

## Scope

This checklist is considered complete only when the following are all true:

- build/test commands pass from documented commands
- the browser demo path is repeatable
- new project state stays on `.abproj` plus `.astrabridge/`
- provider and runtime artifacts remain secret-safe
- another operator can use the docs without hidden handoff knowledge

## Canonical Commands

### Sidecar regression

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m unittest discover -s tests -p test_sidecar_services.py
```

Bundled Python fallback:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -m unittest discover -s tests -p test_sidecar_services.py
```

### Desktop test, typecheck, and build

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
npm test
npm run build
```

Bundled Node fallback:

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" .\node_modules\vitest\vitest.mjs run
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" .\node_modules\typescript\bin\tsc
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" .\node_modules\vite\bin\vite.js build
```

### Sidecar and preview launch

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m astrabridge_sidecar.server --serve --port 8790 --seed-root D:\AstraBridge
```

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
npm run preview
```

Preview URL pattern:

```text
http://127.0.0.1:<preview-port>/?sidecar=http://127.0.0.1:8790
```

## Build Gate

- Sidecar regression passes.
- Desktop unit tests pass.
- Desktop typecheck passes as part of `npm run build`.
- Desktop build passes.
- Preview server serves the current build instead of a stale bundle.
- If Tauri packaging is attempted, record the exact command and result in the release evidence note.

## Functional Smoke Gate

- Create project and confirm only `.abproj` and `.astrabridge/` are created as the normal product path.
- Open an existing project and confirm task/thread state is readable after reload.
- Inspect provider/API manager and confirm generated catalog is visible.
- Confirm one primary lane is healthy enough to run:
  - `deepseek/deepseek-v4-pro`
  - or `qwen/qwen3.7-plus`
- Run one coding turn and confirm:
  - plan or activity appears
  - assistant output completes
  - file change or explicit no-change summary appears
- Open Review and confirm changed files or summary render.
- Create a checkpoint.
- Preview checkpoint load if available, then confirm load behavior is safe.
- Run compact when recommended or available in-context.
- Fork the thread and continue one follow-up turn.
- Reload the page and confirm visible thread state still matches persisted state.

## Browser And Dogfood Gate

- Preview or dev URL opens in the in-app browser without connection refusal.
- No stale bundle confusion is present after rebuilding.
- `/api/dogfood/browser-smoke` returns pass/fail with a screenshot path and sanitized status.
- Captures are written only under:
  - `<workspace>\.astrabridge\captures\`
  - `PRIVATE\demo-runs\<timestamp>\`
- Captures show product UI, not blank/error pages.

## Provider And Catalog Gate

- Generated catalog is the effective provider/model source.
- Provider/model selector shows defaults, recommendations, deprecations, and health status.
- Metadata refresh can partially fail without blocking the app.
- Health results expose only safe fields:
  - provider id
  - model id
  - key fingerprint
  - secret source
  - status
  - sanitized summary
  - timestamp
- Deprecated models show warnings rather than silently disappearing.

## Runtime Recovery Gate

- Missing or archived current thread reprojects visible task focus.
- Compact/fork/reload flows do not cross-leak provider/model/profile state.
- Checkpoint restore leaves project/task/thread pointers consistent.
- Runtime/supervisor status shows actionable recovery guidance rather than raw transport confusion.
- Browser-visible thread output matches sidecar thread truth without a forced reload trick.

## Security And Isolation Gate

- Official Codex config timestamp is unchanged.
- No project `.codex*` file is created during normal AstraBridge use.
- OpenAI official account login is unavailable as a product path.
- Runtime config writes only under isolated AstraBridge state.
- No plaintext secrets appear in:
  - git-tracked files
  - project state
  - reports
  - screenshots
  - logs
  - checkpoint manifests
  - health artifacts
- Vault import/logout preserves or restores preexisting environment state where required.

## Secret Scan Gate

Run focused scans before a release candidate or public push.

Example repo scan:

```powershell
cd D:\AstraBridge
rg -n --hidden --glob '!PRIVATE/**' --glob '!node_modules/**' --glob '!dist/**' --glob '!output/**' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.webp' "Authorization: Bearer|api[_-]?key|sk-[A-Za-z0-9]|vault\\.abvault" .
```

Expected result:

- redacted examples may appear in docs
- real secret material must not appear

## Legacy Scan Gate

Check that legacy project/state paths are not still presented as normal product behavior.

```powershell
cd D:\AstraBridge
rg -n --glob '!docs/**' --glob '!PLAN/**' --glob '!PRIVATE/**' "\.lcrproj|\.codexproj|\.codex-shell|lcr-models|official OpenAI account login|Use OpenAI official" .
```

Expected result:

- no user-visible product surfaces should advertise legacy project paths or official-login behavior
- explicit negative tests and migration-history docs are allowed

## Clean-User Smoke Gate

Use isolated state roots:

```powershell
$env:ASTRABRIDGE_APPDATA='D:\AstraBridge\PRIVATE\demo-runs\clean-user\AppData'
$env:ASTRABRIDGE_CODEX_HOME='D:\AstraBridge\PRIVATE\demo-runs\clean-user\CodexHome'
```

Required results:

- app can launch from fresh state
- user can create a first project
- provider panel loads without secret leakage
- coding workflow opens
- official Codex config remains untouched

## Packaging Gate

This gate is required for release-candidate level work, not for every development demo.

- Packaging target is explicitly named:
  - development preview
  - portable local bundle
  - installer candidate
- Launch path is documented for that target.
- Clean-user launch path is documented.
- Any packaging-specific blocker is recorded in the release evidence note.

## Documentation Gate

The following docs must be aligned with the current product path:

- [README.md](/D:/AstraBridge/README.md)
- [HANDOFF.md](/D:/AstraBridge/HANDOFF.md)
- [DEMO_RUNBOOK.md](/D:/AstraBridge/docs/DEMO_RUNBOOK.md)
- [SECURITY_AND_ISOLATION.md](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)
- [Security and Isolation Runbook](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)

Required content coverage:

- setup commands
- first project workflow
- provider key workflow
- no-key demo mode
- key-backed health mode
- browser smoke workflow
- checkpoint/restore workflow
- compact/fork recovery workflow
- known limitations
- troubleshooting
- artifact locations

## Rollback Gate

If a release candidate or local preview proves unstable:

- stop the preview and sidecar
- preserve secret-safe diagnostics and browser captures
- restore workspace state from the latest valid checkpoint under `.astrabridge\checkpoints\`
- return to the last known green preview/build artifact or last known green commit outside any private credential material
- record the failure mode and recovery path in the release evidence note

Do not solve rollback by deleting artifacts blindly. Preserve enough redacted evidence to explain the failure later.

## Release Evidence Note

For each serious product-ready run, record:

- commands executed
- pass/fail result for each gate
- preview URL used
- sidecar URL used
- workspace used
- artifact paths
- known limitations or skipped gates

Without this note, a green-looking run is not considered fully reproducible.
