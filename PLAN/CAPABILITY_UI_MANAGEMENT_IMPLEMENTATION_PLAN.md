# Capability UI Management Implementation Plan

Last updated: 2026-06-25

## Total Goal

Make AstraBridge's MCP-style capability runtime easy to discover, configure, smoke-test, and use from the desktop UI.

This plan focuses on the user-facing management surface. It does not replace `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md`; when a UI step exposes a backend/runtime gap, the executing agent should make the smallest backend contract addition needed for that step and keep the runtime plan aligned.

The final state should let a non-specialist user:

- see which capabilities exist and which provider/model candidates can satisfy them
- configure routing per capability without editing raw JSON
- install or verify the `astrabridge_capabilities` MCP preset
- run explicit, user-approved smoke tests for image, vision, speech-to-text, and text-to-speech
- inspect generated artifacts and safe diagnostics
- attach capability presets to automations without raw string editing

`web.search` remains a standalone web lane. It is intentionally separate from model-backed capabilities because the tool-using LLM should judge search results itself. Existing image generation and web search interfaces must be preserved.

## Notes And Constraints

- Do not store API keys, bearer tokens, cookies, authorization headers, or raw provider secrets in git, UI state, logs, reports, or artifacts.
- Do not read Desktop key files or other plaintext secret sources unless the user explicitly authorizes that exact action for the current task.
- Show credential status only as redacted provider state, such as configured/missing and a safe fingerprint when already available.
- Keep `.abproj` and workspace-local `.astrabridge/` as the only normal product project state paths.
- Do not reintroduce `.lcrproj`, `.lcr`, `.codexproj`, or `.codex-shell` as supported product state.
- Preserve diagnostics, validation reports, caches, logs, demo runs, raw request payloads, and raw responses by default, with secrets redacted before durable storage.
- Do not regress the completed automation UI.
- Follow the existing desktop design style: dense operational UI, predictable controls, no marketing hero layout, no nested cards.
- Each future execution round should complete exactly one numbered step from this plan, then stop.

## Current Surface Summary

As of 2026-06-25:

- The desktop setup flow already has a basic `Capabilities` tab for capability route mode, pinned candidate selection, and save/reset controls.
- The desktop MCP setup area already has an action to install the `astrabridge_capabilities` preset.
- The sidecar already contains capability registry, route configuration, provider adapters, artifact writing, and the `astrabridge_capabilities` MCP server.
- Automation UI exists, but capability/MCP preset attachment is still too raw for ordinary use.
- There is no complete user-facing console for capability health, model candidates, smoke tests, artifacts, credentials, cost hints, or automation handoff.

## Implementation Steps

- [x] 1. Inventory the current capability UI and define the user workflow gaps.
  - Deliverable: create or update a short gap report, preferably `PLAN/CAPABILITY_UI_SURFACE_GAP_REPORT.md`.
  - Scope: inspect desktop `App.tsx`, desktop API/types, i18n labels, sidecar route APIs, MCP preset APIs, automation preset fields, and `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`.
  - Verification: the report lists current entry points, missing user workflows, backend/API gaps, and the proposed UI navigation shape.

- [x] 2. Normalize the desktop capability data contract and API client surface.
  - Deliverable: typed desktop API/helpers for capability route state, candidate metadata, health/status, smoke-test summaries, artifact references, and MCP preset status.
  - Scope: add only the backend fields required by this step if the sidecar contract is incomplete.
  - Verification: desktop typecheck or focused tests pass; missing backend fields are either implemented or recorded as explicit blockers in this plan.

- [x] 3. Turn the basic capability route page into a clear management panel.
  - Deliverable: UI can list capabilities, show available candidates, switch route mode between auto/pinned/unavailable, pin a candidate, reset local edits, save changes, and show errors inline.
  - Scope: keep existing image and web interfaces; do not merge `web.search` into model-backed capability routing.
  - Verification: focused UI test or manual smoke confirms route changes render correctly and save through the existing API.

- [x] 4. Add capability-specific manual smoke panels.
  - Deliverable: controlled smoke UI for `image.generate`, `vision.analyze`, `speech.transcribe`, and `speech.synthesize`.
  - Scope: default to dry-run, fixture, or no-cost checks when possible; provider-backed smoke must be explicit and user-approved.
  - Verification: no-key smoke path is deterministic; provider-backed smoke records sanitized request metadata, sanitized response metadata, and artifact references only when authorized.

- [x] 5. Add artifact preview and history UI.
  - Deliverable: UI shows recent capability artifacts by capability, including image previews, audio playback/download links, text/JSON summaries, timestamps, provider/model labels, and safe error state.
  - Scope: read from workspace-local `.astrabridge/capabilities/` artifacts only; redact secrets and raw authorization data.
  - Verification: artifact previews work for at least one image, one audio/text output, and one structured diagnostic fixture.

- [x] 6. Add MCP preset install, visibility, and health checks to the capability UI.
  - Deliverable: user can see whether `astrabridge_capabilities` is installed/configured, install or reapply the preset, and run a visibility/health check from the same capability area.
  - Scope: retain existing MCP setup controls; this step may link to them or reuse their API action.
  - Verification: installing/reapplying the preset is idempotent, and health status is visible without exposing secrets.

- [x] 7. Improve automation integration for capability presets.
  - Deliverable: automation creation/editing uses controlled selectors or chips for MCP/capability presets instead of raw text fields where possible.
  - Scope: make `astrabridge_capabilities` discoverable for automation authors while preserving existing automation behavior and stored data compatibility.
  - Verification: automation UI tests or manual smoke confirm create/edit flows preserve selected presets and do not break schedules/triggers.

- [x] 8. Add safety, cost, and credential UX.
  - Deliverable: user sees missing-key states, disabled provider actions, explicit paid-provider warnings, large-artifact warnings, and redacted credential status.
  - Scope: never display or persist raw keys; do not read plaintext key files unless the user authorizes that exact action.
  - Verification: secret scan over changed files passes; UI states cover missing credentials, configured credentials, provider error, and unavailable candidate.

- [x] 9. Align documentation and handoff material.
  - Deliverable: update the relevant docs and maps so future agents understand the capability UI, runtime boundary, standalone web lane, automation handoff, artifact paths, and smoke-test policy.
  - Scope: likely docs include `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`, demo/runbook/security/release notes, and this plan's progress block.
  - Verification: documentation links are valid and do not contain secrets or obsolete product paths.

- [x] 10. Run end-to-end UI smoke and close the plan.
  - Deliverable: deterministic no-key UI smoke evidence plus any authorized provider smoke evidence, all sanitized and preserved under an appropriate validation/report path.
  - Scope: run desktop tests/typecheck and sidecar tests only where touched; do not delete intermediate diagnostics.
  - Verification: mark all steps complete, set progress to `10 / 10`, set next entry point to `complete`, and add a final completion record.

## Current Progress

- Current stage: `step_10_completed`
- Completed steps: `10 / 10`
- Next entry point: `complete`

Future agents must start from the next unchecked numbered step above. Each round should complete one full numbered step, update the checkbox and this progress block, append a dated completion record, and then stop.

## Completion Record

- 2026-06-25: Created this UI/management execution plan. No product code changed. Next entry point is step 1.
- 2026-06-25: Completed step 1. Added `PLAN/CAPABILITY_UI_SURFACE_GAP_REPORT.md` with current entry points, user workflow gaps, backend/API gaps, and the proposed UI navigation shape. Next entry point is step 2.
- 2026-06-25: Completed step 2. Added normalized capability management contract types/API on desktop and a read-only `/api/runtime/capability-management` sidecar snapshot with route, contract, adapter, availability, smoke, artifact, and MCP preset status fields. Verified with `python -m unittest apps.astrabridge-sidecar.tests.test_capability_routes` and `node .\node_modules\typescript\bin\tsc --noEmit` from `apps/astrabridge-desktop`. Next entry point is step 3.
- 2026-06-25: Completed step 3. Replaced the basic inline capability route form with a focused `CapabilityRoutesPanel` management component that shows MCP preset status, route availability, candidate counts, adapter/smoke/artifact summaries, candidate details, reset/save controls, and standalone web-lane messaging while preserving existing route save behavior. Verified with `node .\node_modules\vitest\vitest.mjs run src\features\capabilities\CapabilityRoutesPanel.test.tsx`, `node .\node_modules\typescript\bin\tsc --noEmit`, and `python -m unittest apps.astrabridge-sidecar.tests.test_capability_routes`. Next entry point is step 4.
- 2026-06-25: Completed step 4. Added deterministic no-key `/api/runtime/capability-smoke` dry-run support for `image.generate`, `vision.analyze`, `speech.transcribe`, and `speech.synthesize`, with sanitized request/response metadata and explicit provider-backed authorization guard. Added typed desktop API support and per-capability dry-run smoke controls/results in `CapabilityRoutesPanel`. Verified with `python -m unittest apps.astrabridge-sidecar.tests.test_capability_smoke apps.astrabridge-sidecar.tests.test_capability_routes`, `node .\node_modules\vitest\vitest.mjs run src\features\capabilities\CapabilityRoutesPanel.test.tsx`, and `node .\node_modules\typescript\bin\tsc --noEmit`. Next entry point is step 5.
- 2026-06-25: Completed step 5. Added a sanitized read-only `/api/runtime/capability-artifacts` snapshot for workspace-local capability artifacts, including text previews, audio/image references, relative paths, safe metadata, and image asset registry entries. Added desktop types/API and recent artifact previews inside `CapabilityRoutesPanel` for image, audio, text, and structured summaries. Verified with `python -m unittest apps.astrabridge-sidecar.tests.test_capability_artifacts apps.astrabridge-sidecar.tests.test_capability_smoke apps.astrabridge-sidecar.tests.test_capability_routes`, `node .\node_modules\vitest\vitest.mjs run src\features\capabilities\CapabilityRoutesPanel.test.tsx`, and `node .\node_modules\typescript\bin\tsc --noEmit`. Next entry point is step 6.
- 2026-06-25: Completed step 6. Added safe MCP preset health fields for `astrabridge_capabilities`, including expected tools, missing tools, configured tool count, and health status. Extended the Capabilities UI to show preset health, runtime visibility, runtime tool count, and an idempotent install/reapply action that reuses the existing MCP preset API and refreshes capability/MCP status. Verified with `python -m unittest apps.astrabridge-sidecar.tests.test_capability_routes`, `node .\node_modules\vitest\vitest.mjs run src\features\capabilities\CapabilityRoutesPanel.test.tsx`, and `node .\node_modules\typescript\bin\tsc --noEmit`. Next entry point is step 7.
- 2026-06-25: Completed step 7. Replaced the automation form's raw MCP preset text field with controlled preset chips while preserving the existing `runtime.mcp_preset_ids` storage and payload compatibility. `astrabridge_capabilities` is now always discoverable for automation authors, configured MCP servers are listed as selectable presets, and unknown existing preset IDs remain preserved as custom chips. Verified with `node .\node_modules\vitest\vitest.mjs run src\features\automations\AutomationsPanel.test.tsx src\features\capabilities\CapabilityRoutesPanel.test.tsx` and `node .\node_modules\typescript\bin\tsc --noEmit`. Next entry point is step 8.
- 2026-06-25: Completed step 8. Added redacted credential and safety UX to the capability panel: provider candidates show configured/missing/env/session/disabled credential states without exposing secrets, provider-backed routes show paid-quota warnings, artifact-producing routes show local large-artifact retention warnings, provider route errors remain visible, and pinned route saving is disabled when the selected provider has a missing/session-required/disabled credential state. Verified with `node .\node_modules\vitest\vitest.mjs run src\features\capabilities\CapabilityRoutesPanel.test.tsx src\features\automations\AutomationsPanel.test.tsx`, `node .\node_modules\typescript\bin\tsc --noEmit`, and a changed-file secret scan. Next entry point is step 9.
- 2026-06-25: Completed step 9. Aligned capability runtime/UI documentation and handoff material across `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`, `docs/ARCHITECTURE.md`, `docs/DEMO_RUNBOOK.md`, `docs/HANDOFF.md`, `docs/RELEASE_CHECKLIST.md`, and `docs/SECURITY_AND_ISOLATION.md`. The docs now cover the Capabilities tab, runtime API/MCP boundaries, standalone `web.search` lane, artifact roots, dry-run versus provider-backed smoke policy, redacted credential policy, and automation preset handoff through `runtime.mcp_preset_ids`. Verified local markdown links and changed-file secret scan. Next entry point is step 10.
- 2026-06-25: Completed step 10. Ran deterministic sidecar tests, focused desktop UI tests, TypeScript typecheck, production build, and end-to-end Playwright UI smoke against an isolated sidecar/preview environment. Preserved sanitized no-key smoke evidence under `PRIVATE/demo-runs/capability-ui-smoke-20260625-135156/`, including `capability-ui-smoke-report.json`, `capability-ui-smoke-summary.md`, logs, and screenshots. Provider-backed smoke was skipped because this execution round did not authorize reading provider keys or spending quota. Fixed the smoke-panel click target layout issue found during browser smoke, reran the UI smoke successfully, and verified with a changed-file/evidence secret scan. Next entry point is complete.
