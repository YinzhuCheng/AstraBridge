# AstraBridge Project Summary

Last updated: 2026-07-10

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

- Canonical document registry: [DOCUMENT_REGISTRY.md](/D:/AstraBridge/docs/DOCUMENT_REGISTRY.md)
- Current execution plan: [ASTRABRIDGE_STANDARDIZATION_UI_LIVE_DOGFOOD_EXECUTION_PLAN.md](/D:/AstraBridge/PLAN/ASTRABRIDGE_STANDARDIZATION_UI_LIVE_DOGFOOD_EXECUTION_PLAN.md) (`active`)
- Repository normalization record: [ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md](/D:/AstraBridge/PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md) (`complete`)
- Repository rules: [AGENTS.md](/D:/AstraBridge/AGENTS.md)
- Repository governance: [REPO_GOVERNANCE.md](/D:/AstraBridge/docs/REPO_GOVERNANCE.md)
- Verification matrix: [VERIFICATION_MATRIX.md](/D:/AstraBridge/docs/VERIFICATION_MATRIX.md)
- Ownership boundaries: [OWNERSHIP_BOUNDARIES.md](/D:/AstraBridge/docs/OWNERSHIP_BOUNDARIES.md)
- Code ownership and contract gates: [CODE_OWNERSHIP_AND_CONTRACTS.md](/D:/AstraBridge/docs/CODE_OWNERSHIP_AND_CONTRACTS.md)
- Interface governance: [INTERFACE_GOVERNANCE.md](/D:/AstraBridge/docs/INTERFACE_GOVERNANCE.md)
- Project/task/lane semantics: [SIDEBAR_PROJECT_TASK_SEMANTICS.md](/D:/AstraBridge/PLAN/SIDEBAR_PROJECT_TASK_SEMANTICS.md)
- Chronological project memory: [PROJECT_LOG.md](/D:/AstraBridge/docs/PROJECT_LOG.md)
- Asset/source provenance: [ASSET_SOURCES.md](/D:/AstraBridge/docs/ASSET_SOURCES.md)
- Legacy compatibility archive: [LEGACY_COMPATIBILITY_SHIMS.md](/D:/AstraBridge/docs/archive/LEGACY_COMPATIBILITY_SHIMS.md)

## Validation Baseline

Current second-phase baseline from 2026-07-10:

- Evidence: `PRIVATE/app-standardization-ui-dogfood/baseline/step1-baseline.md`
- Desktop tests: `296` passed, `4` failed. The failures are preserved as current baseline facts, not a green claim.
- Desktop build: passed with the existing large-chunk warning (`1092.23 kB` main JavaScript chunk).
- Step 1 quick-gate snapshot: failed on two pre-existing mojibake lines in `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`. Step 2 repaired those two lines; the failure remains recorded only as baseline history.
- Visible UI baseline: 10 in-app-browser screenshots across chat, settings, providers, models, capabilities, plugins, automations, task graph, and a `900x760` narrow layout.
- Real provider calls for the baseline: none; provider token usage: `0`.

Historical repository-normalization validation on 2026-06-23 remains preserved in `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`; it must not be used to describe the current dirty worktree as green.

Latest documentation/structure hygiene validation on `2026-06-27`:

- targeted sidecar tests for checkpoint, WSL, and isolation-audit paths passed
- `npm.cmd test -- src/features/i18n/catalog.test.ts src/features/dogfood/DogfoodLedgerSummary.test.tsx` passed
- `npm.cmd run build` passed with only the existing Vite chunk-size warning
- mojibake scan only matches tests that assert mojibake is absent

Repository governance gate:

- `python scripts/repo_governance_check.py --repo .`
- `python scripts/run_local_gate.py --quick`

Current documentation and interface hygiene after Step 4 on 2026-07-10:

- canonical document registry coverage: 102/102 entries
- current guidance: 14 active and 44 reference entries
- active/reference mojibake: 0
- active/reference missing local links: 0
- interface registry: 251 entries across HTTP, SSE, runtime payload, provider metadata, MCP, CLI/launcher, and compatibility shims
- non-test Desktop HTTP paths: 179, all mapped to server definitions
- cleanup candidates: 31, including 12 `unknown`; every remaining candidate stays `safe_to_remove=false`
- one high-confidence historical Router adapter block was removed from current runtime source and preserved as private Step 5 evidence; a governance check prevents its symbols from returning to current code
- contract boundary audit validates 4 registered provider-family transports, 7 persisted task-graph fixtures, and 6 canonical orchestration examples through conversion and compilation in the quick gate
- quick gate: passed with 0 governance errors/warnings and 0 secret-scan errors/warnings
- historical corruption remains preserved as informational audit evidence and cannot act as current guidance

## Current Mainline

The active second-phase mainline is `PLAN/ASTRABRIDGE_STANDARDIZATION_UI_LIVE_DOGFOOD_EXECUTION_PLAN.md`. It preserves the completed normalization, hardening, provider-compatibility, automation, brand, Agent Graph, and dogfood records while advancing documentation/API normalization, UI renewal, and bounded live dogfood.

The shared Desktop UI system is defined in `apps/astrabridge-desktop/src/features/ui/uiSystem.ts` and `styles.css`. It fixes the compact spacing, typography, control geometry, surface radius, focus, tooltip, dialog, and status-row contract; `uiSystem.test.ts` is the focused regression entry.

The completed repository normalization pass still defines the product boundary:

- active product state is `.abproj` plus workspace-local `.astrabridge/`
- legacy `.lcr*`, `.codexproj`, `.codex-shell`, and official-login paths are guardrail or historical-audit text only
- web, capability, automation, kernel, plugin, and skill surfaces use AstraBridge-owned APIs and isolated runtime roots
- demo artifacts, validation outputs, and private operator material are preserved by default

Current forward work starts from the canonical registry. `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` is a separate conditional active queue only when the user explicitly asks for capability-runtime implementation; otherwise the current second-phase plan remains the execution entry.
