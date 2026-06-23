# Active Repository Normalization Execution

## Scope

This is the active cleanup and normalization execution file for the current AstraBridge repository. Use it as the only active step tracker for this cleanup cycle.

Execution rule:

1. Complete one numbered step per execution round.
2. After completing a step, mark it complete in this file.
3. Append a dated completion record.
4. Update the next entry point so later agents continue from the correct place.

## Step Status

- [x] 1.1 Establish cleanup baseline
- [x] 1.2 Rebase repository rules onto the active normalization plan
- [x] 1.3 Create repository memory entry points
- [x] 2.1 Upgrade README to current product facts
- [x] 2.2 Rewrite HANDOFF to current product state
- [x] 2.3 Refresh release and operational docs
- [x] 3.1 Audit legacy product-path and naming residue
- [x] 3.2 Remove legacy compatibility code and obsolete tests
- [x] 3.3 Remove remaining public-facing legacy names
- [x] 4.1 Normalize top-level repository structure
- [x] 4.2 Tighten Sidecar Boundaries
- [x] 4.3 Tighten Desktop Boundaries
- [x] 5.1 Final repository wording and structure sweep
- [x] 5.2 Final validation and closeout

## Completion Record

- 2026-06-23: Completed `1.1` by recording the cleanup baseline and verifying desktop `npm run test` and `npm run build`.
- 2026-06-23: Completed `1.2` by updating `AGENTS.md` to point at the active cleanup plan and enforcing one numbered active-plan step per turn.
- 2026-06-23: Completed `1.3` by creating repository memory entry points and updating README links to the active plan and memory docs.
- 2026-06-23: Completed `2.1` by rewriting `README.md` around the current AstraBridge product boundary.
- 2026-06-23: Completed `2.2` by rewriting `docs/HANDOFF.md` to reflect the current repo state instead of the migration-era narrative.
- 2026-06-23: Completed `2.3` by upgrading operational and release docs to current AstraBridge terminology and paths.
- 2026-06-23: Completed `3.1` by auditing legacy `LCR` / `.lcrproj` / `.codexproj` / `.codex-shell` residue and recording the results in `docs/LEGACY_CLEANUP_AUDIT.md`.
- 2026-06-23: Completed `3.2` by removing obsolete legacy compatibility code paths and replacing migration-style tests with current-product assertions.
- 2026-06-23: Completed `3.3` by removing remaining public-facing legacy names from product routes, tool names, and user-visible outputs.
- 2026-06-23: Completed `4.1` by moving handoff and project-log materials under `docs/` and updating repository entry-point links to the normalized top-level structure.
- 2026-06-23: Completed `4.2` by tightening sidecar web-tool boundaries: introduced canonical `web_tool_service.py`, moved app/runtime imports to `AstraBridgeWebService` and `astrabridge_web_mcp_server`, kept `lcr_*` files as compatibility shims only, and passed focused sidecar boundary tests for runtime dynamic tools, MCP registration, and persisted research records.
- 2026-06-23: Completed `4.3` by extracting desktop inspector tool surfaces into `src/features/runtime/InspectorPanels.tsx`, reducing `App.tsx` from 5321 to 4949 lines while preserving existing test IDs and behavior, and passing desktop `npm run test` plus `npm run build`.
- 2026-06-23: Completed `5.1` by sweeping active operator and execution-entry docs (`README.md`, `AGENTS.md`, `docs/HANDOFF.md`, `docs/PROJECT_SUMMARY.md`, `docs/PROJECT_LOG.md`, `docs/DEMO_RUNBOOK.md`) to remove stale cleanup-era wording, tighten execution-plan terminology, and leave old plan references only as explicit historical records.
- 2026-06-23: Completed `5.2` by running final closeout validation: desktop `npm run test` passed, desktop `npm run build` passed, sidecar `python -B -m unittest discover -s tests -p test_sidecar_services.py` passed with 336 tests, and the final legacy-reference scan showed remaining old names only in explicit guardrails, historical audit docs, negative tests, or compatibility shims rather than active product paths.

## Current Step

### 5.2 Final validation and closeout

Goal:

- run final targeted validation across the normalized repo surface
- verify active docs, desktop, and sidecar align with the current product boundary
- confirm remaining legacy references are intentional historical evidence rather than active product paths
- record the final closeout state in this plan

Execution notes:

- Prefer current AstraBridge naming at service and tool boundaries.
- Historical audit files may still reference retired names and plans when clearly labeled as evidence.
- Do not touch `PRIVATE/**` or local run artifacts during closeout unless explicitly asked.

## Next Entry Point

`complete`
