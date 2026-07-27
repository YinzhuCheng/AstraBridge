# Repository Governance

Last updated: 2026-07-27

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

## Canonical Document Registry

- Human-readable index: [DOCUMENT_REGISTRY.md](/D:/AstraBridge/docs/DOCUMENT_REGISTRY.md)
- Machine-readable inventory: [DOCUMENT_REGISTRY.json](/D:/AstraBridge/docs/DOCUMENT_REGISTRY.json)

The registry owns document status, replacement, archive policy, and execution activation. Historical progress text inside a plan does not override the registry. Every superseded entry must name a replacement, and every archived entry must name a replacement or explicit historical purpose.

Three execution plans are classified `active`:

- `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md` is the current default queue.
- `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` is conditional and activates only when the user explicitly asks to implement or advance capability runtime.
- `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md` is conditional and activates only when the user explicitly asks to create or advance the open-source developer-product upgrade lane.

## Bootstrap Document Inventory

| File | Status | Notes |
| --- | --- | --- |
| `AGENTS.md` | active | Repository rules and execution-loop constraints. |
| `CONTRIBUTING.md` | active | Pre-license participation guidance and future contribution workflow. |
| `CODE_OF_CONDUCT.md` | active | Conduct standards and private-enforcement-contact gate. |
| `SECURITY.md` | active | Pre-preview security-reporting policy and private-reporting-route gate. |
| `README.md` | active | Public development entry point. |
| `docs/PROJECT_SUMMARY.md` | active | Fast project state and current entry points. |
| `docs/PROJECT_LOG.md` | active | Chronological memory of substantive repository work. |
| `docs/REPO_GOVERNANCE.md` | active | Governance rules, document status, and local gate policy. |
| `docs/DOCUMENT_REGISTRY.md` | active | Canonical human-readable document and plan status index. |
| `docs/DOCUMENT_REGISTRY.json` | active | Machine-readable registry with owner, scope, replacement, and archive policy. |
| `docs/VERIFICATION_MATRIX.md` | active | Quick/focused/full/release validation matrix. |
| `docs/OWNERSHIP_BOUNDARIES.md` | active | Product subsystem and state ownership boundaries. |
| `docs/ASSET_SOURCES.md` | active | Committed asset provenance and local-artifact policy. |
| `docs/ARCHITECTURE.md` | reference | Current architecture and user mental model. |
| `docs/OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md` | reference | Current evidence-backed open-source foundation decision record. |
| `docs/NO_KEY_FIRST_TEN_MINUTES.md` | reference | Documented no-provider onboarding route, bounded current-source fixture evidence, and clean-clone dependency gate. |
| `docs/OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md` | reference | Current evidence-qualified public positioning and material-claim matrix. |
| `docs/FLAGSHIP_CODING_AGENT_REFERENCE.md` | reference | Deterministic no-provider code-fix/test/review reference with task, approval, artifact, failure, and recovery evidence. |
| `docs/HANDOFF.md` | reference | Handoff guidance for future agents/operators. |
| `docs/LEGACY_CLEANUP_AUDIT.md` | reference | Current classification of legacy residue. |
| `docs/INTERFACE_GOVERNANCE.md` | reference | Current interface status, evidence, replacement, and cleanup rules. |
| `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md` | archived | Compatibility shim inventory and do-not-revive list. |
| `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` | complete | Completed normalization record. |
| `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` | active | Capability runtime follow-on plan when requested. |
| `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md` | active | Conditional public onboarding, contributor adoption, extension readiness, and developer-preview productization queue. |
| `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md` | active | Current default multi-provider, A2A, orchestration, update, and release-stability queue. |
| `PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md` | complete | Completed 22-step stability/protocol/runtime implementation baseline. |
| `PLAN/ASTRABRIDGE_STANDARDIZATION_UI_LIVE_DOGFOOD_EXECUTION_PLAN.md` | superseded | Preserved prior UI/live-dogfood execution record. |
| `PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md` | complete | Completed 24-step dogfood record; preserved evidence. |
| `PLAN/FIVE_CAPABILITY_REAL_SCENARIO_EXECUTION_PLAN.md` | superseded | Superseded by the completed 24-step dogfood record. |

The full 123-entry inventory lives in the canonical registry. Do not infer status for an unlisted future file; add it to the registry before treating it as guidance or an execution queue.

## Local Governance Gate

Use the local gate before handoff, commit, or large follow-up work:

```powershell
python scripts/repo_governance_check.py --repo .
python scripts/run_local_gate.py --quick
```

Use the fail-closed promotion gate when a verdict must be promotable in CI:

```powershell
python scripts/run_promotion_gate.py --mode pr --expected-commit <sha>
```

Promotion summaries must stay bound to the tested commit, clean-tree state, toolchain versions, check manifest, and artifact digests. Required `skipped`, `missing`, `unknown`, or unevaluated checks are non-promotable.

The governance check scans text files for:

- registry coverage, required fields, status values, replacement targets, and active-plan activation conflicts
- broken local Markdown links in registered `active` and `reference` guidance
- mojibake in current guidance, while preserved completed/superseded records remain auditable historical information
- retired runtime symbols outside their canonical transport registry, test, archive, or inventory contexts
- secret-like strings
- tracked `PRIVATE/**` files other than `PRIVATE/README.md`
- legacy product paths outside allowed guardrail, archive, completed-history, test, or shim contexts
- active documents that could mislead agents into treating completed normalization as the current execution queue

Findings are graded:

- `error`: must be fixed before handoff.
- `warning`: review and either fix or document why it is intentional.
- `info`: allowed historical, guardrail, or compatibility context.

`--json-out <path>` writes a machine-readable report only when explicitly requested.
Use `--verbose` when informational archive, shim, and negative-test findings need to be audited.

Canonical CI entry points:

- `.github/workflows/pr-promotion-gate.yml`
- `.github/workflows/nightly-promotion-gate.yml`
- `.github/workflows/release-promotion-gate.yml`

These workflows may install dependencies and upload artifacts, but they must not redefine the check matrix inline. The source of truth is `scripts/run_promotion_gate.py`, which in turn delegates to the canonical gate scripts.

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
