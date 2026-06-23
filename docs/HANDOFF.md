# AstraBridge Handoff

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
  - Inspector panels
  - Browser/demo workflow surfaces

### Sidecar Services

- Path: `apps/astrabridge-sidecar/`
- Responsibility:
  - project lifecycle
  - runtime orchestration
  - provider/profile/model APIs
  - MCP/runtime integration
  - browser smoke and demo-oriented service endpoints

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

### Browser Smoke

- Browser smoke is part of the current demo/validation path
- Expected URL shape:
  - `http://127.0.0.1:4181/?sidecar=http://127.0.0.1:8826&smoke=1`
- Artifacts belong under `PRIVATE/demo-runs/**` or other local-only paths

## Current Validated Baseline

Most recent validated desktop baseline in the current repository normalization pass:

- `cd D:\AstraBridge\apps\astrabridge-desktop`
- `cmd /c npm run test`
- `cmd /c npm run build`

These commands passed on `2026-06-23` during repository normalization steps `1.1` and `1.2`.

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

## What Still Needs Work

Current mainline work still in scope:

- finish doc normalization across `docs/HANDOFF.md`, `docs/`, and release/security/demo docs
- audit remaining legacy naming and stale product-path references
- remove or isolate obsolete legacy compatibility code and tests
- tighten repo structure and component/service boundaries
- expand validation and browser smoke coverage where it improves current product reliability

## Active Operator Entry Points

- [Project Summary](/D:/AstraBridge/docs/PROJECT_SUMMARY.md)
- [Project Log](/D:/AstraBridge/docs/PROJECT_LOG.md)
- [Asset Sources](/D:/AstraBridge/docs/ASSET_SOURCES.md)
- [Demo Runbook](/D:/AstraBridge/docs/DEMO_RUNBOOK.md)
- [Security And Isolation](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)
- [Release Checklist](/D:/AstraBridge/docs/RELEASE_CHECKLIST.md)
- [Active Execution Plan](/D:/AstraBridge/PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md)
- [Repository Rules](/D:/AstraBridge/AGENTS.md)

## Execution Rule

When continuing repository normalization work, follow the active plan directly:

- use `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` as the only active execution source of truth
- complete exactly one full numbered step per turn
- after finishing a step, update the plan status table, completion record, and next-step entry point

## Historical Note

Older stabilization and migration plans may remain useful as historical evidence, but they are not current execution entry points and must not override the active execution plan.
