# AstraBridge Demo Runbook

Last updated: 2026-06-23

## Purpose

This runbook defines the repeatable AstraBridge product demo path for browser-based acceptance. It is designed so that a follow-up operator can run the same flow without relying on undocumented local context.

## Supported Demo Modes

### 1. No-key demo

Use this when the goal is to verify product workflow, routing surfaces, thread state, checkpoint/compact/fork behavior, and browser usability without spending provider quota.

Expected focus:

- project creation/open
- provider catalog visibility
- runtime workflow visibility
- browser and dogfood automation
- artifact locations

### 2. Key-backed demo

Use this when approved provider credentials are already available through:

- the AstraBridge encrypted vault
- or short-lived process environment variables

Expected focus:

- safe provider readiness
- model catalog and health state
- one real coding turn
- checkpoint/compact/fork continuation

Never print, paste, screenshot, or commit plaintext keys.

## Preconditions

- Sidecar is healthy at `http://127.0.0.1:8826/health`
- Web app is reachable at either:
  - `http://127.0.0.1:<preview-port>/?sidecar=http://127.0.0.1:8826`
  - `http://127.0.0.1:<dev-port>/?sidecar=http://127.0.0.1:8826`
- Current project uses `.abproj` and `.astrabridge/`
- Generated catalog is active
- At least one primary lane is healthy for a key-backed run

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
npm run build
cmd /c npm run preview -- --host 127.0.0.1 --port 4181
```

### Optional isolated demo roots

```powershell
$env:ASTRABRIDGE_APPDATA='D:\AstraBridge\PRIVATE\demo-runs\current\AppData'
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
2. Open the coding thread surface.
3. Create a thread if none exists.
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
11. Fork the thread.
12. Continue with one follow-up turn.
13. Reload the page and confirm visible task/thread state still matches the persisted session.

## Expected Visible Behaviors

- Provider/model picker stays internally consistent.
- No legacy `.lcr`, `.lcrproj`, `.codexproj`, `.codex-shell`, or `lcr-models` product path appears.
- Runtime or provider errors, if any, are categorized and actionable.
- Checkpoint activity writes under `.astrabridge/`.
- Fork/compact flow does not cross-leak model or profile state.
- Browser-visible thread output matches the sidecar's thread truth.

## Browser Smoke Workflow

Use both human-visible and API-visible smoke where possible.

### In-app browser acceptance

Confirm all of the following:

- app opens without connection refusal
- bundle is fresh and not stale
- project loads
- provider panel opens
- catalog is visible
- thread surface is usable
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

## Checkpoint And Recovery Workflow

During the demo, confirm:

- checkpoint create works
- checkpoint preview or dirty-state warning appears when relevant
- checkpoint restore does not corrupt project/task/thread pointers
- compact and fork leave the session usable
- reload does not lose the visible state

If runtime status becomes degraded, follow `docs/SECURITY_AND_ISOLATION.md` and `docs/RELEASE_CHECKLIST.md` sections for recovery and reset checks.

## Artifact Locations

Typical artifact locations:

- Project state: `<workspace>\.astrabridge\`
- Captures: `<workspace>\.astrabridge\captures\`
- Checkpoints: `<workspace>\.astrabridge\checkpoints\`
- Demo artifacts: `D:\AstraBridge\PRIVATE\demo-runs\<timestamp>\`
- Private credential policy: [PRIVATE/README.md](/D:/AstraBridge/PRIVATE/README.md)

Preferred local artifact root:

- `D:\AstraBridge\PRIVATE\demo-runs\`

## Known Limitations

- Packaging and installer validation may still lag behind preview-based product validation.
- Some provider health and metadata refresh behavior may depend on current upstream availability.
- A no-key demo proves workflow readiness, not provider correctness.
- A key-backed demo proves only the lanes actually exercised in that run.

## Troubleshooting

### App shows connection refused

- confirm sidecar is running on the URL in the query string
- confirm preview or dev server is still serving
- rebuild preview if the bundle is stale

### App opens but thread output does not update

- inspect runtime status and current thread state
- confirm event stream and thread API are in sync
- reload once to distinguish stale UI from missing persistence

### Provider lane looks unavailable

- confirm key status is loaded safely
- confirm generated catalog contains the target model
- run metadata refresh if the model list looks stale
- inspect health summary rather than raw provider output

### Checkpoint or fork flow looks wrong

- confirm current task/thread pointers are still aligned
- inspect supervisor recovery hints
- use the documented recovery checks in `docs/RELEASE_CHECKLIST.md` rather than hand-editing project state

## Acceptance Checklist

- App opens in the in-app browser
- Current project is valid and uses `.abproj` plus `.astrabridge/`
- Provider panel loads and shows safe status
- Generated catalog is visible
- A coding turn completes end to end
- Review renders
- Checkpoint works
- Compact works when applicable
- Fork works
- Follow-up turn works
- No secret-like value is visible in UI or artifacts
