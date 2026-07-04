# AstraBridge Project Summary

## Current Product State

AstraBridge is a local multi-provider coding-agent workbench built around Codex CLI/app-server runtime patterns, with app-owned project state and isolated runtime paths.

Current product facts:

- Normal project format: `.abproj`
- Normal workspace state: `.astrabridge/`
- User-visible navigation model: `Project -> Task`
- Runtime `thread_id` values are internal execution-lane identifiers, not left-sidebar user work units
- OpenAI is treated as a normal API-key provider, not as an official account-login path
- `PRIVATE/**` is local-only and must not be pushed

## Core Directories

- `apps/astrabridge-desktop/`: desktop/web UI, i18n, browser-facing workflows
- `apps/astrabridge-sidecar/`: project/runtime/provider/model APIs and supporting services
- `docs/`: active user, operator, security, release, and repository-history docs
- `PLAN/`: tracked execution plans, surface maps, and historical execution records
- `PRIVATE/`: local demo runs, screenshots, validation artifacts, and private operator material

## Current Entry Points

- Repository normalization record: [ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md](/D:/AstraBridge/PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md) (`complete`)
- Repository rules: [AGENTS.md](/D:/AstraBridge/AGENTS.md)
- Repository governance: [REPO_GOVERNANCE.md](/D:/AstraBridge/docs/REPO_GOVERNANCE.md)
- Verification matrix: [VERIFICATION_MATRIX.md](/D:/AstraBridge/docs/VERIFICATION_MATRIX.md)
- Ownership boundaries: [OWNERSHIP_BOUNDARIES.md](/D:/AstraBridge/docs/OWNERSHIP_BOUNDARIES.md)
- Project/task/lane semantics: [SIDEBAR_PROJECT_TASK_SEMANTICS.md](/D:/AstraBridge/PLAN/SIDEBAR_PROJECT_TASK_SEMANTICS.md)
- Chronological project memory: [PROJECT_LOG.md](/D:/AstraBridge/docs/PROJECT_LOG.md)
- Asset/source provenance: [ASSET_SOURCES.md](/D:/AstraBridge/docs/ASSET_SOURCES.md)
- Legacy compatibility archive: [LEGACY_COMPATIBILITY_SHIMS.md](/D:/AstraBridge/docs/archive/LEGACY_COMPATIBILITY_SHIMS.md)

## Validation Baseline

Latest verified desktop baseline from the completed repository normalization pass:

- `cd D:\AstraBridge\apps\astrabridge-desktop`
- `cmd /c npm run test`
- `cmd /c npm run build`

Both commands passed on `2026-06-23` during repository normalization steps `1.1` and `1.2`.

Latest documentation/structure hygiene validation on `2026-06-27`:

- targeted sidecar tests for checkpoint, WSL, and isolation-audit paths passed
- `npm.cmd test -- src/features/i18n/catalog.test.ts src/features/dogfood/DogfoodLedgerSummary.test.tsx` passed
- `npm.cmd run build` passed with only the existing Vite chunk-size warning
- mojibake scan only matches tests that assert mojibake is absent

Repository governance gate:

- `python scripts/repo_governance_check.py --repo .`
- `python scripts/run_local_gate.py --quick`

## Current Mainline

The completed repository normalization pass established the current product boundary:

- active product state is `.abproj` plus workspace-local `.astrabridge/`
- legacy `.lcr*`, `.codexproj`, `.codex-shell`, and official-login paths are guardrail or historical-audit text only
- web, capability, automation, kernel, plugin, and skill surfaces use AstraBridge-owned APIs and isolated runtime roots
- demo artifacts, validation outputs, and private operator material are preserved by default

Current forward work should start from the specific active plan for the target area, not from retired normalization or migration narratives.
