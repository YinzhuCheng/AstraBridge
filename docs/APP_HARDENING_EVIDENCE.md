# AstraBridge App Hardening Evidence

This document is the public summary for the first AstraBridge app-hardening round driven by `PLAN/ASTRABRIDGE_APP_HARDENING_EXECUTION_PLAN.md`.

The private evidence remains under `PRIVATE/app-hardening/`. This public document exists so later agents can quickly see what was hardened, where the evidence lives, what risks remain, and where the next round should start.

## Round 1 Outcome

- Execution status: complete
- Plan progress: 20/20
- Completed window: 2026-06-27 to 2026-07-03
- Private round reports: 19 (`step2` through `step20`)
- Validation artifacts: 20 (`step1` through `step20`)
- Referenced screenshots in round reports: 42
- Real provider token consumption: 0

## What Was Hardened

### Execution Evidence Lane

- Established the app-hardening artifact structure and report templates.
- Captured the baseline UI/state surface.
- Added the screenshot QA checklist and retention/redaction guardrails.
- Added this public evidence index so future agents have a clean entrypoint.

### State and Runtime Correctness

- Documented state invariants for project/task/thread/provider-thread/runtime/automation/artifact boundaries.
- Hardened restore paths, conversation empty/error/renderable states, provider/runtime capability metadata, usage signals, and sidecar provenance.

### Product UI and Operator Surfaces

- Hardened runtime/browser/review/files inspector density and evidence readability.
- Hardened attachment diagnostics, artifact preview safety, web-lane evidence, plugin/skill registry state, MCP diagnostics, and cross-surface browser polish.

### Automation Reliability

- Hardened success-path finalization.
- Hardened stuck/interrupted watchdog recovery and operator-facing diagnostics.

### Security and Evidence Retention

- Added dedicated secret scanning for `PRIVATE/app-hardening/**`.
- Redacted desktop `Desktop\\key.txt` style leaks in shared security helpers.
- Normalized retained artifacts into the documented four-bucket layout.

## Step Map

| Step | Focus | Evidence |
| --- | --- | --- |
| 1 | Artifact/reporting scaffold | Execution plan completion record |
| 2 | Baseline UI/state capture | `PRIVATE/app-hardening/reports/step2-baseline-ui-state.json` |
| 3 | State invariants | `PRIVATE/app-hardening/reports/step3-state-invariants.json` |
| 4 | Restore hardening | `PRIVATE/app-hardening/reports/step4-restore-hardening.json` |
| 5 | Conversation state hardening | `PRIVATE/app-hardening/reports/step5-conversation-states.json` |
| 6 | Runtime/provider contract | `PRIVATE/app-hardening/reports/step6-runtime-provider-contract.json` |
| 7 | Usage signal | `PRIVATE/app-hardening/reports/step7-usage-signal.json` |
| 8 | Sidecar provenance and headless capture | `PRIVATE/app-hardening/reports/step8-sidecar-provenance-and-capture.json` |
| 9 | Screenshot QA checklist | `PRIVATE/app-hardening/reports/step9-ui-screenshot-qa.json` |
| 10 | Inspector evidence UI | `PRIVATE/app-hardening/reports/step10-runtime-browser-inspector-evidence.json` |
| 11 | Attachment diagnostics | `PRIVATE/app-hardening/reports/step11-chat-attachment-diagnostics.json` |
| 12 | Artifact/media preview | `PRIVATE/app-hardening/reports/step12-artifact-media-preview.json` |
| 13 | Web lane evidence | `PRIVATE/app-hardening/reports/step13-web-lane-evidence.json` |
| 14 | Plugin/skill registry | `PRIVATE/app-hardening/reports/step14-plugin-skill-registry.json` |
| 15 | MCP diagnostics | `PRIVATE/app-hardening/reports/step15-mcp-tool-diagnostics.json` |
| 16 | Automation finalization | `PRIVATE/app-hardening/reports/step16-automation-finalization.json` |
| 17 | Automation watchdog | `PRIVATE/app-hardening/reports/step17-automation-watchdog-hardening.json` |
| 18 | Redaction and retention audit | `PRIVATE/app-hardening/reports/step18-redaction-retention-audit.json` |
| 19 | Cross-surface UI/UX polish | `PRIVATE/app-hardening/reports/step19-ui-polish-sweep.json` |
| 20 | Round summary and next entry | `PRIVATE/app-hardening/reports/step20-hardening-round-summary.json` |

## Verification Summary

Round 1 did not rely on external provider smoke to declare success. The round stayed local-first and evidence-driven:

- targeted desktop tests
- sidecar `unittest` and `pytest` coverage
- repeated `npm run build` checks on UI-affecting steps
- `python .\scripts\app_hardening_secret_scan.py --repo .`
- `python .\scripts\run_local_gate.py --quick`
- `git diff --check`
- repeated in-app/browser screenshot QA on UI-affecting steps

## Screenshot Index

The most important screenshot groups are:

- Baseline and early QA:
  - `PRIVATE/app-hardening/screenshots/step2-baseline/`
  - `PRIVATE/app-hardening/screenshots/step9-ui-screenshot-qa-20260627/`
- Inspector and browser evidence surfaces:
  - `PRIVATE/app-hardening/screenshots/inspector-canvas-density-interrupt-20260628/`
  - `PRIVATE/app-hardening/screenshots/step19-ui-polish-20260703/`
- Automation:
  - `PRIVATE/app-hardening/screenshots/step16-automation-finalization-20260703/`
  - `PRIVATE/app-hardening/screenshots/step17-automation-watchdog-20260703/`
- Multimodal, artifact, web, registry, and MCP:
  - `PRIVATE/app-hardening/screenshots/step11-chat-attachments-20260628/`
  - `PRIVATE/app-hardening/screenshots/step12-artifact-media-preview-20260628/`
  - `PRIVATE/app-hardening/screenshots/step13-web-lane-evidence-20260628/`
  - `PRIVATE/app-hardening/screenshots/step14-plugin-skill-registry-20260628/`
  - `PRIVATE/app-hardening/screenshots/step15-mcp-tool-diagnostics-20260703/`

## Remaining Risk

- Managed-user login and settings-side credential onboarding still need a dedicated hardening pass.
- Browser workbench session lifecycle and deterministic public-site acceptance remain the highest-value browser follow-up after the chrome-density fix.
- Runtime warning density and prioritization still deserve a product pass so the main task window carries less persistent noise.
- The local quick gate is established, but it is still not promoted to CI or a release-enforced gate.

## Next-Round Entry

Future agents should start the follow-on round in this order unless the user explicitly redirects:

1. Settings credential and managed-user login hardening.
2. Browser workbench session lifecycle, stable public-web acceptance targets, and mobile-entry strategy cleanup.
3. Runtime warning-density and status prioritization cleanup.
4. Promotion of the local quick gate and artifact checks into a release-oriented engineering gate.
