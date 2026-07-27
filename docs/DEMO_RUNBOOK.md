# AstraBridge Demo Runbook

Last updated: 2026-07-27

## Purpose

This runbook defines the repeatable AstraBridge product demo path for browser-based acceptance. It is designed so that a follow-up operator can run the same flow without relying on undocumented local context.

## Supported Demo Modes

### 1. No-key demo

Use this when the goal is to verify product workflow, routing surfaces, task and execution-lane state, checkpoint/compact/branch-task behavior, and browser usability without spending provider quota.

Expected focus:

- project creation/open
- provider catalog visibility
- runtime kernel compatibility visibility
- plugin/skill inventory and warning visibility
- capability route, dry-run smoke, artifact preview, and MCP preset visibility
- runtime workflow visibility
- browser and dogfood automation
- artifact locations

For the documented no-key path, use
[No-Key First Ten Minutes](NO_KEY_FIRST_TEN_MINUTES.md). It has deterministic
project, task-graph, and fixture evidence but makes no provider-backed or
release-ready clean-clone claim until its sidecar dependency-manifest gate is
published.

### 2. Key-backed demo

Use this when approved provider credentials are already available through:

- the AstraBridge encrypted vault
- or short-lived process environment variables

Expected focus:

- safe provider readiness
- model catalog and health state
- redacted capability credential readiness
- one real coding turn
- checkpoint/compact/branch-task continuation

Never print, paste, screenshot, or commit plaintext keys.

## Preconditions

- Sidecar is healthy at `http://127.0.0.1:8826/health`
- Web app is reachable at either:
  - `http://127.0.0.1:<preview-port>/?astrabridge_launch=dogfood&sidecar=http://127.0.0.1:8826`
  - `http://127.0.0.1:<dev-port>/?astrabridge_launch=dogfood&sidecar=http://127.0.0.1:8826`
- Current project uses `.abproj` and `.astrabridge/`
- Generated catalog is active
- At least one primary lane is healthy for a key-backed run

The verified no-key browser path specifically uses Desktop `127.0.0.1:4181`
with sidecar `127.0.0.1:8826`. A custom browser origin needs matching CORS
configuration and is outside that no-key path.

Recommended lanes:

- Primary: `deepseek/deepseek-v4-pro`
- Alternate: `qwen/qwen3.7-plus`
- Additional coding lanes when available:
  - `kimi/kimi-k2.7-code`
  - `glm/glm-5.2`

## Recommended Launch Sequence

### Sidecar

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
$env:PYTHONDONTWRITEBYTECODE='1'
python -m astrabridge_sidecar.server --serve --port 8826 --seed-root D:\AstraBridge
```

### Preview

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 4181
```

### Optional isolated demo roots

```powershell
$env:ASTRABRIDGE_APPDATA='D:\AstraBridge\PRIVATE\demo-runs\current\AppData'
$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\PRIVATE\demo-runs\current\Runtime'
$env:ASTRABRIDGE_CODEX_HOME='D:\AstraBridge\PRIVATE\demo-runs\current\CodexHome'
```

Use isolated roots when you want a clean operator-facing run without contaminating your normal local state.

## Operator Rules

- Never paste raw API keys into chat, screenshots, logs, or git-tracked files.
- Never save raw `Authorization` headers or cookies into reports.
- Prefer provider status, supervisor status, browser captures, review diff, and project summaries over raw transport logs.
- Preserve artifacts by default, but keep them secret-safe.

Primary operator entry points:

- [README.md](/D:/AstraBridge/README.md)
- [HANDOFF.md](/D:/AstraBridge/docs/HANDOFF.md)
- [Project Summary](/D:/AstraBridge/docs/PROJECT_SUMMARY.md)
- [Project Log](/D:/AstraBridge/docs/PROJECT_LOG.md)

## First Project Workflow

1. Open the app.
2. Create or open an AstraBridge project.
3. Confirm the product path is `.abproj` plus `.astrabridge/`.
4. Confirm no project `.codex*` files are created during the flow.
5. Confirm the main coding surface is available without navigating through a marketing screen.

## Provider Key Workflow

For key-backed runs:

1. Open Provider/API Manager.
2. Confirm the provider panel shows safe key status only.
3. Confirm generated catalog entries include defaults, recommendations, deprecations, and health markers.
4. If metadata refresh is available, run it and wait for source-level completion or partial success.
5. Confirm no raw secret value appears anywhere in the UI.

## Main Demo Flow

1. Open the app and confirm the current project is loaded.
2. Open the task coding surface.
3. Create a task if none exists.
4. Select the provider/model lane for the run.
5. Send one bounded coding request, for example:
   - `Scan the current workspace, identify one concrete bug or missing edge case, explain the plan briefly, then make the fix and summarize the changed files.`
6. Watch for:
   - plan card or activity summary
   - assistant output
   - command or tool activity
   - file change rendering or explicit no-change explanation
   - supervisor status remaining actionable
7. Open Review and confirm changed files or diff summary render.
8. Create a checkpoint.
9. Preview checkpoint load if the UI offers a preview path.
10. Run compact if context guard recommends it.
11. Create a branch task.
12. Continue with one follow-up turn.
13. Reload the page and confirm visible task and execution-lane state still matches the persisted task.

## Expected Visible Behaviors

- Provider/model picker stays internally consistent.
- No legacy `.lcr`, `.lcrproj`, `.codexproj`, `.codex-shell`, or `lcr-models` product path appears.
- Runtime or provider errors, if any, are categorized and actionable.
- Checkpoint activity writes under `.astrabridge/`.
- Branch/compact flow does not cross-leak model or profile state.
- Browser-visible task output matches the sidecar's task conversation truth.

## Browser Smoke Workflow

Use both human-visible and API-visible smoke where possible.

### In-app browser acceptance

Confirm all of the following:

- app opens without connection refusal
- bundle is fresh and not stale
- project loads
- provider panel opens
- catalog is visible
- task surface is usable
- review surface is usable
- checkpoint controls are usable
- diagnostics or runtime status is readable

### API smoke

Use `/api/dogfood/browser-smoke` for a repeatable acceptance slice.

Recommended action set:

1. open project
2. open provider manager
3. inspect catalog
4. select provider/model
5. run coding prompt
6. inspect review
7. checkpoint
8. compact
9. fork
10. continue follow-up turn

Expected result:

- pass/fail result
- screenshot path
- sanitized console or status summary

## Runtime Kernel Workflow

Use this when validating the current Codex kernel line or when comparing a candidate binary against the existing baseline.

### Runtime panel check

1. Open Setup -> Runtime.
2. Confirm the runtime kernel panel shows:
   - binary path
   - version
   - compatibility status
   - isolated Codex home
   - app-server status
   - MCP status
   - plugin status
   - skill status
3. Confirm warnings are readable without exposing raw secrets or account state.
4. If the observed version or binary locator changed from the expected baseline, stop treating the run as "just a demo" and move to the upgrade workflow below.

### Kernel upgrade and matrix workflow

When the binary or lane changes:

1. Follow [CODEX_KERNEL_UPGRADE_RUNBOOK.md](/D:/AstraBridge/docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md).
2. Preserve evidence under `PRIVATE\demo-runs\codex-kernel-upgrade-<timestamp>\` or `PRIVATE\demo-runs\codex-kernel-smoke-<timestamp>\`.
3. Compare the result against [CODEX_KERNEL_COMPATIBILITY_MATRIX.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md).
4. Do not mark a lane `verified` without exact probe and smoke evidence for the exact binary locator and execution lane.

## Capability Management Workflow

Use this when validating MCP-style capabilities from the desktop without raw JSON editing.

### No-key capability check

1. Open Setup -> Capabilities.
2. Confirm each capability row shows lane type, route mode, resolved candidate or unavailable state, adapter count, smoke status, and artifact policy.
3. Confirm `web.search` appears as a standalone lane and is not editable as a model-backed route.
4. Confirm `astrabridge_capabilities` preset status is visible.
5. Install or reapply the preset from the Capabilities tab.
6. Select a runtime profile when available and confirm runtime visibility is shown without exposing secrets.
7. Run dry-run smoke for model-backed capabilities:
   - `image.generate`
   - `vision.analyze`
   - `speech.transcribe`
   - `speech.synthesize`
8. Confirm no provider-backed call is made by the dry-run path.
9. Confirm the panel shows paid-provider and artifact-retention warnings for model-backed artifact-producing capabilities.
10. Confirm credential states are redacted, for example configured, missing, env ref, session required, or disabled.

### Artifact preview check

1. Open Setup -> Capabilities.
2. Confirm recent artifacts render from `<workspace>\.astrabridge\capabilities\`.
3. Confirm image previews, audio playback controls, text summaries, timestamps, provider/model labels, and relative paths appear when fixtures or prior runs exist.
4. Confirm raw authorization headers, cookies, bearer tokens, and provider secrets do not appear.

### Automation handoff check

1. Open Setup -> Automations.
2. Create or edit an automation.
3. Confirm MCP presets are selectable as chips rather than raw comma-separated text.
4. Confirm `AstraBridge Capability Runtime` maps to stored `runtime.mcp_preset_ids: ["astrabridge_capabilities"]`.
5. Confirm unknown existing preset ids remain preserved as custom chips.

Provider-backed capability smoke is not part of the no-key demo. Only run it after the user explicitly approves the exact credential source for that run.

## Extensions Workflow

Use this when validating plugin/skill discovery, warnings, enablement, presets, and install-plan/apply behavior from the desktop.

### Inventory and warning check

1. Open Setup -> Extensions.
2. Confirm plugin and skill inventory loads from the isolated runtime.
3. Confirm source catalog, provenance, icon provenance, install status, enablement, compatibility warnings, and notes are visible.
4. Confirm generated fallback icon, malformed manifest, blocked owner, or pending-approval warning states remain visible when such fixtures or local records are present.
5. Confirm plugin-owned skills are not silently active just because the inventory exists.

### Project preset and enablement check

1. In Setup -> Extensions, add one plugin or skill to the project preset when a safe local fixture is available.
2. Confirm the active project preset updates without creating project `.codex*` files.
3. Confirm skill enablement actions stay explicit:
   - enable globally
   - disable globally
   - enable for project
   - disable for project
   - use global setting
4. Confirm blocked or pending-approval states remain visible instead of silently becoming enabled.

### Install-plan and fixture rehearsal

Use isolated roots before rehearsing install/apply or smoke:

```powershell
$env:ASTRABRIDGE_APPDATA='D:\AstraBridge\PRIVATE\demo-runs\current\AppData'
$env:ASTRABRIDGE_CODEX_HOME='D:\AstraBridge\PRIVATE\demo-runs\current\CodexHome'
```

Inventory/UI smoke:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m astrabridge_sidecar.codex_plugin_skill_smoke
```

Install/update/rollback fixture smoke:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m astrabridge_sidecar.codex_plugin_install_smoke
```

Expected result:

- smoke output points to `PRIVATE\demo-runs\plugin-skill-smoke-<timestamp>\` or `PRIVATE\demo-runs\plugin-install-smoke-<timestamp>\`
- evidence is secret-safe and preserved by default
- inventory smoke includes plugin probe, skill probe, registry snapshot, and structured UI assertions
- install smoke includes install, update, already-current, malformed, rollback, and secret-scan cases

### Desktop install/apply review

When a safe local plugin record is present in Extensions:

1. Open the plugin details.
2. Preview the install plan before any mutation.
3. Review declared MCP servers, apps, skills, planned writes, rollback snapshot metadata, and warnings.
4. Only then run apply if the fixture and isolated roots are the intended target.
5. Confirm result evidence stays under `PRIVATE\demo-runs\plugin-install-*`.

## Automation Smoke Workflow

Use this when validating the local automation layer without spending provider quota. This is the required Step 10 release-gate smoke.

### Deterministic sidecar smoke

```powershell
cd D:\AstraBridge
python .\scripts\run_automation_smoke.py
```

Expected result:

- script prints a local summary path under `PRIVATE\demo-runs\automation-smoke-<timestamp>\`
- two manual automations are created
- one `run-now` ends as `no_signal` and produces an archived inbox item
- one `run-now` ends as `finding` and produces a promoted inbox item
- `.astrabridge\automations\automations.json`, `runs\index.json`, and `inbox\index.json` are created in the smoke workspace
- runtime manifests are written under the isolated runtime root

Saved evidence:

- `PRIVATE\demo-runs\automation-smoke-<timestamp>\automation-smoke-report.json`
- `PRIVATE\demo-runs\automation-smoke-<timestamp>\automation-smoke-summary.md`

### Desktop operator check

When the preview app is already up, also confirm the visible automation surface:

1. Open Setup -> Automations.
2. Confirm automation list, form, inbox, and runs panels render.
3. Confirm scheduler summary is visible.
4. Confirm a promoted inbox item leaves a visible `promotion_ref`.

The deterministic script is the required reproducible gate. The desktop pass is the matching operator-visible check.

## Checkpoint And Recovery Workflow

During the demo, confirm:

- checkpoint create works
- checkpoint preview or dirty-state warning appears when relevant
- checkpoint restore does not corrupt project/task/execution-lane pointers
- compact and branch-task flows leave the task usable
- reload does not lose the visible state

If runtime status becomes degraded, follow `docs/SECURITY_AND_ISOLATION.md` and `docs/RELEASE_CHECKLIST.md` sections for recovery and reset checks.

## Artifact Locations

Typical artifact locations:

- Project state: `<workspace>\.astrabridge\`
- Captures: `<workspace>\.astrabridge\captures\`
- Checkpoints: `<workspace>\.astrabridge\checkpoints\`
- Demo artifacts: `D:\AstraBridge\PRIVATE\demo-runs\<timestamp>\`
- Kernel upgrade/smoke artifacts: `D:\AstraBridge\PRIVATE\demo-runs\codex-kernel-*\`
- Plugin/skill smoke artifacts: `D:\AstraBridge\PRIVATE\demo-runs\plugin-skill-smoke-*\`
- Plugin install/apply artifacts: `D:\AstraBridge\PRIVATE\demo-runs\plugin-install-*\`
- Private credential policy: [PRIVATE/README.md](/D:/AstraBridge/PRIVATE/README.md)

Preferred local artifact root:

- `D:\AstraBridge\PRIVATE\demo-runs\`

## Known Limitations

- Packaging and installer validation may still lag behind preview-based product validation.
- Some provider health and metadata refresh behavior may depend on current upstream availability.
- A no-key demo proves workflow readiness, not provider correctness.
- A key-backed demo proves only the lanes actually exercised in that run.
- The verified no-key route uses the standard `4181` Desktop origin and `8826`
  sidecar port; custom origins require an explicit CORS configuration.

## Troubleshooting

### App shows connection refused

- confirm sidecar is running on the URL in the query string
- confirm preview or dev server is still serving
- rebuild preview if the bundle is stale

### App opens but task output does not update

- inspect runtime status and current task/execution-lane state
- confirm event stream and task display API are in sync
- reload once to distinguish stale UI from missing persistence

### Provider lane looks unavailable

- confirm key status is loaded safely
- confirm generated catalog contains the target model
- run metadata refresh if the model list looks stale
- inspect health summary rather than raw provider output

### Runtime kernel panel looks degraded

- inspect Setup -> Runtime before assuming the UI is wrong
- capture `/api/runtime/kernel-probe` evidence or follow `docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md`
- compare the observed lane against `PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md`
- preserve evidence instead of rewriting the matrix from memory

### Extensions inventory or install flow looks wrong

- run `python -m astrabridge_sidecar.codex_plugin_skill_smoke`
- if install/apply is involved, run `python -m astrabridge_sidecar.codex_plugin_install_smoke`
- confirm isolated `ASTRABRIDGE_CODEX_HOME` roots are active
- inspect warnings, source catalog, and rollback metadata before assuming the plugin is trustworthy

### Checkpoint or branch-task flow looks wrong

- confirm current task/execution-lane pointers are still aligned
- inspect supervisor recovery hints
- use the documented recovery checks in `docs/RELEASE_CHECKLIST.md` rather than hand-editing project state

## Acceptance Checklist

- App opens in the in-app browser
- Current project is valid and uses `.abproj` plus `.astrabridge/`
- Provider panel loads and shows safe status
- Generated catalog is visible
- Runtime kernel panel shows a believable binary/version/compatibility snapshot
- A coding turn completes end to end
- Automation smoke completes and saves a sanitized report
- Capability no-key smoke and artifact preview checks pass
- Extensions inventory and plugin/skill smoke checks pass
- Review renders
- Checkpoint works
- Compact works when applicable
- Fork works
- Follow-up turn works
- No secret-like value is visible in UI or artifacts
