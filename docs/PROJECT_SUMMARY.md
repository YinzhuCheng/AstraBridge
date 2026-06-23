# AstraBridge Project Summary

## Current Product State

AstraBridge is a local multi-provider coding-agent workbench built around Codex CLI/app-server runtime patterns, with app-owned project state and isolated runtime paths.

Current product facts:

- Normal project format: `.abproj`
- Normal workspace state: `.astrabridge/`
- OpenAI is treated as a normal API-key provider, not as an official account-login path
- `PRIVATE/**` is local-only and must not be pushed

## Core Directories

- `apps/astrabridge-desktop/`: desktop/web UI, i18n, browser-facing workflows
- `apps/astrabridge-sidecar/`: project/runtime/provider/model APIs and supporting services
- `docs/`: active user, operator, security, release, and repository-history docs
- `PLAN/`: active repository execution plan
- `PRIVATE/`: local demo runs, screenshots, validation artifacts, and private operator material

## Current Execution Source

- Active plan: [ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md](/D:/AstraBridge/PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md)
- Repository rules: [AGENTS.md](/D:/AstraBridge/AGENTS.md)
- Chronological project memory: [PROJECT_LOG.md](/D:/AstraBridge/docs/PROJECT_LOG.md)
- Asset/source provenance: [ASSET_SOURCES.md](/D:/AstraBridge/docs/ASSET_SOURCES.md)

## Validation Baseline

Latest verified desktop baseline in the current repository normalization pass:

- `cd D:\AstraBridge\apps\astrabridge-desktop`
- `cmd /c npm run test`
- `cmd /c npm run build`

Both commands passed on `2026-06-23` during repository normalization steps `1.1` and `1.2`.

## Current Mainline

The current repository normalization pass is focused on:

- replacing stale planning and repository entry points
- aligning docs and repo rules with current AstraBridge product facts
- removing or isolating obsolete legacy paths and naming
- preserving demo artifacts, validation outputs, and private operator material by default
