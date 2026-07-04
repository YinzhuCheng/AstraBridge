# Repository Governance

Last updated: 2026-06-27

## Purpose

This document is the current source of truth for AstraBridge repository hygiene. It keeps future agents aligned with the current product architecture, preserves evidence by default, and makes obsolete product paths visible as history rather than active guidance.

## Current Product Boundary

- AstraBridge projects use `.abproj` files plus workspace-local `.astrabridge/` state.
- The desktop app, sidecar, provider catalog, runtime lanes, and project services are AstraBridge-owned surfaces.
- OpenAI is a normal API-key provider. Official OpenAI account login is not an AstraBridge product path.
- Legacy `.lcr*`, `.codexproj`, `.codex-shell`, and official-login references are allowed only as guardrails, historical evidence, negative tests, or documented compatibility shims.

## Protected Artifacts

Preserve these by default:

- `PRIVATE/**`
- demo runs, screenshots, browser smoke captures, and validation reports
- raw LLM request/response records after secret redaction
- logs, caches, raw experiment traces, parsed outputs, and intermediate QA files

Do not clean or rewrite these artifacts unless the user explicitly names the target path. Never persist API keys, bearer tokens, cookies, auth headers, provider raw secrets, or plaintext vault passwords.

## Document Status Taxonomy

Use these statuses when describing plan and documentation files:

| Status | Meaning | Agent behavior |
| --- | --- | --- |
| `active` | The file owns current work or current policy. | Start here when the user asks for that area. |
| `complete` | The file is a finished execution record. | Preserve it; do not resume it unless explicitly requested. |
| `superseded` | The file has been replaced by a newer plan or record. | Keep it as history and point readers to the replacement. |
| `archived` | The file documents old behavior, shims, or evidence. | Do not treat it as current product guidance. |
| `reference` | The file describes stable product context or operator process. | Use it to orient work, not as an execution queue. |

## Current Document Inventory

| File | Status | Notes |
| --- | --- | --- |
| `AGENTS.md` | active | Repository rules and execution-loop constraints. |
| `README.md` | active | Public development entry point. |
| `docs/PROJECT_SUMMARY.md` | active | Fast project state and current entry points. |
| `docs/PROJECT_LOG.md` | active | Chronological memory of substantive repository work. |
| `docs/REPO_GOVERNANCE.md` | active | Governance rules, document status, and local gate policy. |
| `docs/VERIFICATION_MATRIX.md` | active | Quick/focused/full/release validation matrix. |
| `docs/OWNERSHIP_BOUNDARIES.md` | active | Product subsystem and state ownership boundaries. |
| `docs/ASSET_SOURCES.md` | active | Committed asset provenance and local-artifact policy. |
| `docs/ARCHITECTURE.md` | reference | Current architecture and user mental model. |
| `docs/HANDOFF.md` | reference | Handoff guidance for future agents/operators. |
| `docs/LEGACY_CLEANUP_AUDIT.md` | reference | Current classification of legacy residue. |
| `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md` | archived | Compatibility shim inventory and do-not-revive list. |
| `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` | complete | Completed normalization record. |
| `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` | active | Capability runtime follow-on plan when requested. |
| `PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md` | complete | Completed 24-step dogfood record; preserved evidence. |
| `PLAN/FIVE_CAPABILITY_REAL_SCENARIO_EXECUTION_PLAN.md` | superseded | Superseded by the completed 24-step dogfood record. |

Other files under `PLAN/**` are execution records, surface maps, or area-specific plans. If a plan is unclear, classify it before resuming it.

## Local Governance Gate

Use the local gate before handoff, commit, or large follow-up work:

```powershell
python scripts/repo_governance_check.py --repo .
python scripts/run_local_gate.py --quick
```

The governance check scans text files for:

- mojibake outside tests or explicit negative checks
- secret-like strings
- tracked `PRIVATE/**` files other than `PRIVATE/README.md`
- legacy product paths outside allowed guardrail, archive, test, or shim contexts
- active documents that could mislead agents into treating completed normalization as the current execution queue

Findings are graded:

- `error`: must be fixed before handoff.
- `warning`: review and either fix or document why it is intentional.
- `info`: allowed historical, guardrail, or compatibility context.

`--json-out <path>` writes a machine-readable report only when explicitly requested.
Use `--verbose` when informational archive, shim, and negative-test findings need to be audited.

## Dirty Worktree Triage

The worktree may contain user or prior-agent changes. Do not revert them by default.

When triaging:

- group changes by subsystem: docs, plans, desktop, sidecar, scripts, tests, private artifacts
- identify which files belong to the current request
- avoid staging unrelated files
- do not clean caches, logs, raw traces, screenshots, demo outputs, or `PRIVATE/**`
- record any unresolved unrelated changes in the final handoff if they affect validation

## API And Interface Evolution

Default to additive changes. Existing runtime payloads and API fields should continue to work unless the user explicitly requests a breaking change.

When deprecating behavior:

- document the replacement
- keep compatibility shims small
- test the shim if older preserved evidence depends on it
- prevent new implementation logic from being added behind legacy names

## UI Change Acceptance

UI work must include visual QA when a browser surface changes:

- inspect the in-app browser or Playwright screenshot
- check narrow and normal widths where practical
- verify no overlapping text, excessive whitespace, mojibake, or unreadable hover/focus states
- ensure icon-only controls have accessible labels or titles
- preserve the product mental model: left navigation is `Project -> Task`; runtime lanes are internal execution lines

## Artifact And Provenance Policy

Use `docs/ASSET_SOURCES.md` for committed external assets. Use `references/logging_and_artifacts.md` for local artifact preservation rules.

Do not write raw secrets into:

- docs
- plans
- logs
- validation reports
- screenshots metadata
- project files
- provider request/response records

If a report needs to prove secret handling, store redacted evidence only.
