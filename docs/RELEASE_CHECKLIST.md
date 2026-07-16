# AstraBridge Release Checklist

Last updated: 2026-07-06

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
cmd /c npm run test
cmd /c npm run build
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
python -m astrabridge_sidecar.server --serve --port 8826 --seed-root D:\AstraBridge
```

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
cmd /c npm run preview -- --host 127.0.0.1 --port 4181
```

Preview/dev URL pattern:

```text
http://127.0.0.1:<port>/?astrabridge_launch=dogfood&sidecar=http://127.0.0.1:8826
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
- Open an existing project and confirm task and execution-lane state is readable after reload.
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
- Create a branch task and continue one follow-up turn.
- Reload the page and confirm visible task state still matches persisted state.
- Open Setup -> Runtime and confirm:
  - the kernel status panel shows binary path, version, compatibility status, isolated Codex home, app-server status, MCP status, plugin status, and skill status
  - warnings are actionable and secret-safe
  - if the binary locator or observed version changed, the operator preserved evidence and followed `docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md` instead of treating the change as an untracked local tweak
- Run `python .\scripts\run_automation_smoke.py` and confirm:
  - one manual automation yields `no_signal` plus archived inbox item
  - one manual automation yields `finding` plus promoted inbox item
  - sanitized evidence is written under `PRIVATE\demo-runs\automation-smoke-<timestamp>\`
- Open Setup -> Capabilities and confirm:
  - model-backed capabilities show route mode, resolved candidate, credential state, safety warnings, smoke status, and artifact policy
  - `web.search` is shown as a standalone lane and is not treated as a model-backed route
  - `astrabridge_capabilities` preset health and runtime visibility are visible
  - install/reapply preset is idempotent
  - dry-run smoke runs without provider credentials
  - recent capability artifacts render from `.astrabridge\capabilities\` when fixtures or prior outputs exist
- Run `python -m astrabridge_sidecar.codex_plugin_skill_smoke` and confirm:
  - the smoke report passes
  - sanitized evidence is written under `PRIVATE\demo-runs\plugin-skill-smoke-<timestamp>\`
  - evidence includes plugin probe, skill probe, registry snapshot, and structured UI assertions
- Open Setup -> Extensions and confirm:
  - source catalog, provenance, icon provenance, declared MCP/apps/skills, and effective enablement are visible
  - user-visible warnings stay visible for generated fallback icons, malformed manifests, blocked owners, or pending approval states when such fixtures are present
  - plugin-owned skills are not silently auto-enabled by inventory alone
  - install-plan preview shows planned writes, rollback metadata, and declared side effects before apply

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

## Agentic Update Pipeline Gate

This gate is required when a release candidate changes provider metadata, provider adapters, capability routes, Codex kernel candidate handling, plugin/skill update behavior, automation scheduling, or update review UI.

- Public update workflow docs are current:
  - [AGENTIC_UPDATE_PIPELINE_RUNBOOK.md](/D:/AstraBridge/docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md)
  - [CODEX_KERNEL_UPGRADE_RUNBOOK.md](/D:/AstraBridge/docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md)
  - [PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md](/D:/AstraBridge/docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md)
- The release evidence records the user-selected update scope:
  - `scope`
  - `providers`
  - `models` when applicable
  - `version_policy`
  - `target_version` when pinned
  - `apply_mode`
  - `allow_network`
  - `allow_provider_calls`
  - `allow_install`
  - `allow_code_changes`
- The updater never silently performs any of these actions:
  - provider API calls
  - Codex candidate install or binary switching
  - metadata apply
  - source-code mutation
  - plugin/skill installation
  - external writeback, merge, push, or release publication
- A proposal-only or discovery run preserves:
  - `run-contract.json`
  - `sources/source-index.json`
  - `sources/source-pack.jsonl`
  - `parsed/parser-output.json` or `parsed/codex-kernel-candidates.json`
  - `proposals/proposal.json`
  - `diffs/proposal-diff.json`
  - `validation/validation-report.json`
  - `rollback/rollback-manifest.json`
  - `secret-scan/secret-scan-report.json`
  - `summary.json`
- If metadata apply is used:
  - proposal risk is `metadata_only` or lower
  - manual approval is recorded
  - apply manifest lists changed paths
  - rollback manifest validates
  - rollback has been tested in an isolated state root or equivalent release rehearsal
- If provider-backed smoke is used:
  - `allow_provider_calls=true` is recorded in the run contract
  - credential availability is recorded only as redacted status
  - smoke artifacts are preserved under `PRIVATE/agentic-update-pipeline/`
  - no API keys, bearer tokens, cookies, authorization headers, vault passwords, desktop key contents, or raw provider secrets appear in durable artifacts
- If Codex kernel verification is used:
  - candidate version and release source are recorded
  - probe evidence is preserved
  - smoke evidence is preserved before any `verified` claim
  - no official Codex config or product `.codex*` project state is written
- If code-change planning is used:
  - branch/worktree boundary is recorded
  - main-worktree mutation is not used unless explicitly authorized
  - rollback instructions avoid destructive git commands without user approval
- Required commands for updater-adjacent changes:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_contract tests.test_agentic_update_artifacts tests.test_agentic_update_discovery tests.test_agentic_update_parsers tests.test_agentic_update_diffing tests.test_agentic_update_service
```

For release candidates that touch the desktop update review panel:

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
cmd /c npm run test -- AgenticUpdateReviewPanel.test.tsx
cmd /c npm run build
```

For release candidates that touch automation update checks:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_automation tests.test_automation_api tests.test_agentic_update_service
```

Required updater secret scan:

```powershell
cd D:\AstraBridge
rg -n -i "api[_-]?key\s*[:=]|authorization\s*:|bearer\s+[A-Za-z0-9._~+/=-]{12,}|password\s*[:=]|cookie\s*:|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{20,}|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY" docs PLAN apps/astrabridge-sidecar/skills/agentic-update-pipeline apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates apps/astrabridge-sidecar/tests/test_agentic_update_*.py scripts/agentic_update_fixture_dogfood.py
```

Expected updater status language:

- `discovered`: sources fetched or replayed, no promotion claim
- `proposed`: proposal/diff generated, not applied
- `applied`: permitted metadata-only apply completed with rollback evidence
- `verified`: required validation and smoke evidence passed
- `partial`: usable but warning-gated or incomplete
- `blocked`: promotion/apply refused until recorded blockers are resolved
- `deprecated`: source-backed deprecation warning or catalog change
- `recommended`: verified and manually reviewed enough to suggest

Do not call a provider/model/kernel `recommended` or `verified` when the latest update run is only `proposed`, `partial`, or `blocked`.

## Runtime Recovery Gate

- Missing or archived current execution lane reprojects visible task focus.
- Compact/branch-task/reload flows do not cross-leak provider/model/profile state.
- Checkpoint restore leaves project/task/execution-lane pointers consistent.
- Runtime/supervisor status shows actionable recovery guidance rather than raw transport confusion.
- Browser-visible task output matches sidecar task conversation truth without a forced reload trick.

## Security And Isolation Gate

- Official Codex config timestamp is unchanged.
- No project `.codex*` file is created during normal AstraBridge use.
- OpenAI official account login is unavailable as a product path.
- Runtime config writes only under isolated AstraBridge state.
- Capability artifact previews read only from workspace-local `.astrabridge\capabilities\` or local demo evidence paths.
- Capability dry-run smoke does not require keys or call providers.
- Provider-backed capability smoke is explicit and user-approved.
- Capability credential states are redacted and never reveal raw values.
- Plugin and skill discovery treats manifests, catalogs, and `SKILL.md` files as untrusted metadata until reviewed.
- Remote or curated catalogs do not auto-install, auto-update, or silently bypass approval.
- Plugin install/apply writes stay inside isolated AstraBridge runtime roots only:
  - `ASTRABRIDGE_CODEX_HOME\plugins\`
  - `ASTRABRIDGE_CODEX_HOME\plugin-staging\`
  - `ASTRABRIDGE_CODEX_HOME\plugin-rollbacks\`
- Generated fallback or unvalidated plugin/skill icons remain visibly marked as untrusted branding.
- Plugin-declared MCP servers, apps, hooks, and skills are disclosed before apply because they may introduce side effects.
- Skill enablement requires explicit approval flow and does not bypass sandbox, approval, or secret policy.
- Plugin/skill smoke evidence remains under `PRIVATE\demo-runs\plugin-skill-smoke-*\` and contains only sanitized metadata plus structured UI assertions.
- Automation defaults do not silently bypass sandbox or approval policy.
- Any `full-access` automation is an explicit opt-in and uses dedicated worktree isolation.
- Automation retry/backoff and daily run limits are bounded and test-covered.
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
$secretPattern = ('Author' + 'ization: Bear' + 'er|api[_-]?' + 'key|sk-' + '[A-Za-z0-9]|vault' + '\.abvault')
rg -n --hidden --glob '!PRIVATE/**' --glob '!node_modules/**' --glob '!dist/**' --glob '!output/**' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.webp' $secretPattern .
```

If the run changed app-hardening evidence or the docs that describe it:

```powershell
cd D:\AstraBridge
python .\scripts\app_hardening_secret_scan.py --repo .
```

Expected result:

- redacted examples may appear in docs
- real secret material must not appear
- changed-file scan for plugin/skill trust-review edits should also return no real secret material
- `PRIVATE/app-hardening/**` stays untracked, bucketed under `raw/`, `reports/`,
  `screenshots/`, and `validations/`, and contains no leaked desktop key paths
  or secret-bearing companion text

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
- [HANDOFF.md](/D:/AstraBridge/docs/HANDOFF.md)
- [PROJECT_SUMMARY.md](/D:/AstraBridge/docs/PROJECT_SUMMARY.md)
- [PROJECT_LOG.md](/D:/AstraBridge/docs/PROJECT_LOG.md)
- [ASSET_SOURCES.md](/D:/AstraBridge/docs/ASSET_SOURCES.md)
- [DEMO_RUNBOOK.md](/D:/AstraBridge/docs/DEMO_RUNBOOK.md)
- [SECURITY_AND_ISOLATION.md](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)
- [CODEX_KERNEL_UPGRADE_RUNBOOK.md](/D:/AstraBridge/docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md)
- [AGENTIC_UPDATE_PIPELINE_RUNBOOK.md](/D:/AstraBridge/docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md)

Required content coverage:

- setup commands
- first project workflow
- provider key workflow
- no-key demo mode
- key-backed health mode
- capability route and MCP preset management
- capability dry-run smoke and artifact preview policy
- runtime kernel compatibility workflow and compatibility-matrix update path
- agentic update scope/version policy workflow, validation, rollback, and promotion policy
- plugin/skill inventory, smoke, and install-plan/apply review path
- browser smoke workflow
- automation smoke workflow
- checkpoint/restore workflow
- compact/branch-task recovery workflow
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
