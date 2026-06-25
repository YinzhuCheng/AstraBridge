# AstraBridge Handoff

Last updated: 2026-06-25

## Product Identity

- Product: AstraBridge
- Positioning: a local provider-neutral coding-agent workbench built around Codex CLI/app-server runtime patterns
- Non-goals:
  - being the official Codex App
  - depending on official OpenAI account login
  - using legacy `.lcrproj`, `.lcr`, `.codexproj`, or `.codex-shell` as normal product paths

## Current Product Facts

- Normal project format: `.abproj`
- Normal workspace state: `.astrabridge/`
- OpenAI is a normal API-key provider
- Runtime state is app-owned and isolated
- `PRIVATE/**` is local-only and must not be pushed

## Current Architecture

### Desktop UI

- Path: `apps/astrabridge-desktop/`
- Stack: Tauri + React + Zustand + TanStack Query
- Main surfaces:
  - Chat/task conversation
  - LLM API Manager
  - Capabilities setup and smoke panel
  - Inspector panels
  - Browser/demo workflow surfaces
  - Automations setup, inbox, and run history

### Sidecar Services

- Path: `apps/astrabridge-sidecar/`
- Responsibility:
  - project lifecycle
  - runtime orchestration
  - provider/profile/model APIs
  - capability registry, routes, dry-run smoke, artifact listing, and capability MCP server
  - MCP/runtime integration
  - browser smoke and demo-oriented service endpoints
  - automation CRUD, scheduler, runner, triage, manifests, and inbox APIs

### Model Catalog

- Responsibility: AstraBridge-managed provider/model metadata and effective routing truth
- Current product expectation: catalog and runtime/provider settings must stay aligned; stale manual seed logic should continue shrinking over time

### Vault And Key Safety

- Durable secrets belong in the app-managed encrypted vault or explicit local env vars
- Desktop plaintext key files are not normal product inputs and must not be read unless the user explicitly authorizes that exact action
- Never commit API keys, bearer tokens, cookies, auth headers, or provider raw secrets

### Native Kernel

- AstraBridge has a provider-neutral native-kernel workflow on the same event/evidence contract as the main coding workflow
- Native-kernel verification is part of the current usable demo baseline, not a side experiment
- Desktop runtime status lives under Setup -> Runtime
- Compatibility truth lives in [CODEX_KERNEL_COMPATIBILITY_MATRIX.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md)
- Upgrade and rollback procedure lives in [CODEX_KERNEL_UPGRADE_RUNBOOK.md](/D:/AstraBridge/docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md)
- The canonical no-key kernel evidence path is `python -m astrabridge_sidecar.codex_kernel_smoke`

### Browser Smoke

- Browser smoke is part of the current demo/validation path
- Expected URL shape:
  - `http://127.0.0.1:4181/?sidecar=http://127.0.0.1:8826&smoke=1`
- Artifacts belong under `PRIVATE/demo-runs/**` or other local-only paths

### Automations

- Workspace-visible state lives under `.astrabridge/automations/`
- Runtime manifests and optional worktrees live under the app-owned runtime root
- Surface map: [AUTOMATIONS_SURFACE_MAP.md](/D:/AstraBridge/PLAN/AUTOMATIONS_SURFACE_MAP.md)
- Release smoke: `python .\scripts\run_automation_smoke.py`

### MCP-Style Capabilities

- Desktop entry: Setup -> Capabilities
- Main UI component: `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.tsx`
- Sidecar APIs:
  - `/api/runtime/capability-management`
  - `/api/runtime/capability-routes/save`
  - `/api/runtime/capability-smoke`
  - `/api/runtime/capability-artifacts`
  - `/api/router/mcp/preset/astrabridge-capabilities`
- MCP server: `astrabridge_capabilities`
- Stable tools:
  - `astrabridge_capability_routes`
  - `astrabridge_capability_image_generate`
  - `astrabridge_capability_vision_analyze`
  - `astrabridge_capability_speech_transcribe`
  - `astrabridge_capability_speech_synthesize`
- Surface map: [CAPABILITY_RUNTIME_SURFACE_MAP.md](/D:/AstraBridge/PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md)
- UI execution plan: [CAPABILITY_UI_MANAGEMENT_IMPLEMENTATION_PLAN.md](/D:/AstraBridge/PLAN/CAPABILITY_UI_MANAGEMENT_IMPLEMENTATION_PLAN.md)

Capability rules:

- `web.search` remains standalone and does not enter model-backed routing.
- Dry-run smoke is the default no-key validation path.
- Provider-backed smoke requires explicit user approval.
- Artifacts live under `<workspace>/.astrabridge/capabilities/**`.
- Credential state in UI must remain redacted.

### Extensions

- Desktop entry: Setup -> Extensions
- Main UI component: `apps/astrabridge-desktop/src/features/extensions/PluginSkillInventoryPanel.tsx`
- Sidecar APIs:
  - `/api/runtime/plugin-skill-registry`
  - `/api/runtime/plugin-install-plan`
  - `/api/runtime/plugin-install-apply`
  - `/api/runtime/skill-enablement`
  - `/api/projects/plugin-skill-presets`
- Canonical no-key evidence paths:
  - inventory/UI smoke: `python -m astrabridge_sidecar.codex_plugin_skill_smoke`
  - install/update/rollback fixture smoke: `python -m astrabridge_sidecar.codex_plugin_install_smoke`

Extensions rules:

- discovery is metadata-first and does not imply trust
- install/apply stays inside isolated AstraBridge-managed Codex-home roots
- plugin-owned skills require explicit enablement and may be blocked by owner state
- warnings about generated fallback icons, malformed manifests, blocked owners, or pending approval must remain visible
- project plugin/skill presets stay distinct from MCP preset routing

## Current Validated Baseline

Most recent validated desktop baseline in the current repository normalization pass:

- `cd D:\AstraBridge\apps\astrabridge-desktop`
- `cmd /c npm run test`
- `cmd /c npm run build`

These commands passed on `2026-06-23` during repository normalization steps `1.1` and `1.2`.

Additional validated baseline notes:

- Automation implementation baseline now also includes the Step 1-10 automation layer, with final release-gate smoke and docs aligned on `2026-06-25`.
- Kernel compatibility and Extensions baseline now also includes the Step 1-27 probe, inventory, install-plan/apply, preset, smoke, and docs work aligned on `2026-06-25`.

## What Is Already Done

Completed before or during the current repository normalization pass:

- project hard cut to `.abproj` / `.astrabridge/`
- provider foundation cutover
- generated catalog and metadata truth consolidation
- release-grade end-to-end coding workflow demo
- provider-neutral native-kernel workflow
- repository execution rules moved to one numbered execution step per turn
- project memory entry points added:
  - `docs/PROJECT_SUMMARY.md`
  - `docs/PROJECT_LOG.md`
  - `docs/ASSET_SOURCES.md`
- automations Step 1-10 implementation:
  - contracts, store, scheduler, workspace isolation, runner, triage
  - sidecar routes and supervisor summary
  - desktop Automations panel
  - smoke script, surface map, and release docs
- capability runtime and UI management implementation:
  - management contract, route panel, dry-run smoke, artifact history, MCP preset health, standalone `web.search`, automation preset chips, runtime plugin/skill visibility, and redacted credential/safety UX
- Codex kernel compatibility implementation:
  - compatibility surface map, probe contract, binary/app-server/MCP/plugin/skill probes
  - aggregated runtime probe route and Runtime tab status panel
  - deterministic kernel smoke, matrix gate, compatibility matrix, and upgrade runbook
- Extensions implementation:
  - plugin/skill registry contract and inventory UI
  - icon provenance and generated fallback pipeline
  - install-plan preview and controlled apply with rollback evidence
  - skill enablement, project presets, automation preset handoff, plugin/skill smoke, and security/release docs

## What Still Needs Work

Current mainline work still in scope:

- audit remaining legacy naming and stale product-path references
- remove or isolate obsolete legacy compatibility code and tests
- tighten repo structure and component/service boundaries
- expand validation and browser smoke coverage where it improves current product reliability
- complete the final end-to-end kernel plus plugin/skill UI closeout step in [CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md)

## Active Operator Entry Points

- [Project Summary](/D:/AstraBridge/docs/PROJECT_SUMMARY.md)
- [Project Log](/D:/AstraBridge/docs/PROJECT_LOG.md)
- [Asset Sources](/D:/AstraBridge/docs/ASSET_SOURCES.md)
- [Demo Runbook](/D:/AstraBridge/docs/DEMO_RUNBOOK.md)
- [Security And Isolation](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)
- [Release Checklist](/D:/AstraBridge/docs/RELEASE_CHECKLIST.md)
- [Codex Kernel Upgrade Runbook](/D:/AstraBridge/docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md)
- [Automation Surface Map](/D:/AstraBridge/PLAN/AUTOMATIONS_SURFACE_MAP.md)
- [Capability Runtime Surface Map](/D:/AstraBridge/PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md)
- [Capability UI Management Plan](/D:/AstraBridge/PLAN/CAPABILITY_UI_MANAGEMENT_IMPLEMENTATION_PLAN.md)
- [Codex Kernel Compatibility Matrix](/D:/AstraBridge/PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md)
- [Codex Kernel / Plugin / Skill Execution Plan](/D:/AstraBridge/PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md)
- [Active Execution Plan](/D:/AstraBridge/PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md)
- [Repository Rules](/D:/AstraBridge/AGENTS.md)

## Future Agent Guidance

When a follow-up agent touches kernel or extension work, do not improvise the workflow.

- For a Codex binary change, start from [CODEX_KERNEL_UPGRADE_RUNBOOK.md](/D:/AstraBridge/docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md), then update [CODEX_KERNEL_COMPATIBILITY_MATRIX.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md) only after preserved probe/smoke evidence exists for the exact lane and binary locator.
- For plugin/skill inventory or UI validation, use `python -m astrabridge_sidecar.codex_plugin_skill_smoke` and keep the resulting `PRIVATE/demo-runs/plugin-skill-smoke-*` artifact root.
- For install/update fixture rehearsal, use `python -m astrabridge_sidecar.codex_plugin_install_smoke` before treating any plugin install/apply change as acceptable.
- Preserve secret-safe evidence by default; do not clean `PRIVATE/demo-runs/**` unless the user explicitly names cleanup targets.

## Execution Rule

When continuing repository normalization work, follow the active plan directly:

- use `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` as the only active execution source of truth
- complete exactly one full numbered step per turn
- after finishing a step, update the plan status table, completion record, and next-step entry point

## Historical Note

Older stabilization and migration plans may remain useful as historical evidence, but they are not current execution entry points and must not override the active execution plan.
