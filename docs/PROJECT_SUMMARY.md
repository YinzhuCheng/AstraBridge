# AstraBridge Project Summary

Last updated: 2026-07-27

## Current Product State

AstraBridge is a local multi-provider coding-agent workbench built around Codex CLI/app-server runtime patterns, with app-owned project state and isolated runtime paths.

Current product facts:

- Normal project format: `.abproj`
- Normal workspace state: `.astrabridge/`
- User-visible navigation model: `Project -> Task`
- Runtime `thread_id` values are internal execution-lane identifiers, not left-sidebar user work units
- OpenAI is treated as a normal API key provider, not as an official account-login path
- `PRIVATE/**` is local-only and must not be pushed

## Core Directories

- `apps/astrabridge-desktop/`: desktop/web UI, i18n, browser-facing workflows
- `apps/astrabridge-sidecar/`: project/runtime/provider/model APIs and supporting services
- `docs/`: active user, operator, security, release, and repository-history docs
- `PLAN/`: tracked execution plans, surface maps, and historical execution records
- `PRIVATE/`: local demo runs, screenshots, validation artifacts, and private operator material

## Current Entry Points

- Canonical document registry: [DOCUMENT_REGISTRY.md](/D:/AstraBridge/docs/DOCUMENT_REGISTRY.md)
- Current execution plan: [ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md](/D:/AstraBridge/PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md) (`active`)
- Completed open-source developer-productization record: [ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md](/D:/AstraBridge/PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md) (all 11 steps complete; DG-OSS-04 pauses public preview and hands owner-gated clearance to the readiness decision)
- Open-source foundation decision record: [OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md](/D:/AstraBridge/docs/OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md) (license, private security-reporting route, and maintainer-contact decisions remain owner-gated)
- Public positioning and claim matrix: [OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md](/D:/AstraBridge/docs/OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md) (authoritative wording and evidence status for public product claims)
- Provider truth and authority surface: [PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md](/D:/AstraBridge/docs/PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md) (current route-level metadata, deterministic evidence, reduced-authority posture, and escalation boundary for Qwen, DeepSeek, Kimi K3, and GLM)
- GUI/code orchestration parity: [GUI_CODE_ORCHESTRATION_PARITY.md](/D:/AstraBridge/docs/GUI_CODE_ORCHESTRATION_PARITY.md) (public deterministic native JSON-to-GUI-to-runtime proof for Code Fix / Test / Review, with source ownership and explicit non-claims)
- Extension and first-contribution surface: [EXTENSION_AND_FIRST_CONTRIBUTION_SURFACE.md](/D:/AstraBridge/docs/EXTENSION_AND_FIRST_CONTRIBUTION_SURFACE.md) (supported/experimental/internal/deferred classification and a bounded provider-free candidate skill example; no auto-enable, live route, or pre-license merge claim)
- Contributor feedback protocol: [CONTRIBUTOR_FEEDBACK_PROTOCOL.md](/D:/AstraBridge/docs/CONTRIBUTOR_FEEDBACK_PROTOCOL.md) (prepared local templates, two independent provider-free candidate rehearsals, and future-only response activation; public intake remains pending)
- Documented no-provider onboarding: [NO_KEY_FIRST_TEN_MINUTES.md](/D:/AstraBridge/docs/NO_KEY_FIRST_TEN_MINUTES.md) (exact-source local-canonical clean-clone fixture evidence at `c8988fef6f1139ac056fadb68e395122ee59254a`; no provider, coding-route, or release-installer claim)
- Developer preview baseline: [DEVELOPER_PREVIEW_BASELINE.md](/D:/AstraBridge/docs/DEVELOPER_PREVIEW_BASELINE.md) (source evaluation plus deterministic staging/update rehearsal evidence; public installer, security/contact, legal, support, and distribution claims remain explicitly blocked)
- Developer preview readiness decision: [DEVELOPER_PREVIEW_READINESS_DECISION.md](/D:/AstraBridge/docs/DEVELOPER_PREVIEW_READINESS_DECISION.md) (DG-OSS-04 branch C: public preview is paused pending owner-gated legal, private-reporting, support, and distribution evidence)
- Public quality and reliability dossier: [PUBLIC_QUALITY_RELIABILITY_DOSSIER.md](/D:/AstraBridge/docs/PUBLIC_QUALITY_RELIABILITY_DOSSIER.md) (seven machine-checked public evidence cards with a four-card non-pass ledger for provider authority, candidate extension, security/support, and release state)
- Flagship coding-agent reference: [FLAGSHIP_CODING_AGENT_REFERENCE.md](FLAGSHIP_CODING_AGENT_REFERENCE.md) (deterministic no-provider code-fix/test/review workflow with visible task, approval, artifact, failure, and recovery evidence)
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

Historical second-phase baseline from 2026-07-10:

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

Current documentation, protocol, and gate status after the 2026-07-17 stability audit plus Steps 1-4 of the active product-stability plan:

- canonical document registry coverage: 107/107 entries
- current guidance: 14 active and 46 reference entries
- active/reference mojibake: 0
- active/reference missing local links: 0
- interface registry: 251 entries across HTTP, SSE, runtime payload, provider metadata, MCP, CLI/launcher, and compatibility shims
- non-test Desktop HTTP paths: 179, all mapped to server definitions
- cleanup candidates: 31, including 12 `unknown`; every remaining candidate stays `safe_to_remove=false`
- one high-confidence historical Router adapter block was removed from current runtime source and preserved as private Step 5 evidence; a governance check prevents its symbols from returning to current code
- contract boundary audit passes its current 21/21 ownership and boundary checks
- quick gate: passed with 0 governance errors/warnings and 0 secret-scan errors/warnings
- canonical fail-closed promotion gate: `scripts/run_promotion_gate.py`
- canonical CI entry points: `.github/workflows/pr-promotion-gate.yml`,
  `.github/workflows/nightly-promotion-gate.yml`,
  `.github/workflows/release-promotion-gate.yml`
- dirty-tree promotion proof preserved at
  `PRIVATE/promotion-gates/local-pr-dirty-check-2/`
- canonical release identity owner: `release/astrabridge-release-identity.json`
- canonical release-readiness gate: `scripts/run_release_readiness_gate.py`
- preserved Step 2 release-readiness evidence:
  `PRIVATE/release-readiness/local-step2-readiness/`
- canonical protocol persistence owner:
  `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/persistence.py`
- runtime event and artifact vocabularies are now schema-derived in generated
  Python and TypeScript protocol bindings rather than duplicated runtime-owned
  literals
- durable persistence rejects schema-external protocol events, invalid schema
  versions, missing required protocol fields, and unsupported run-projection
  versions before database writes
- shared canonical protocol fixture corpus currently covers 10 valid and 7
  invalid cases across Python, TypeScript, migration, and persistence tests
- durable delivery semantics now separate immutable `message_id`, delivery
  `idempotency_key`, and processing-key inbox admission for live handoffs and
  late-result deduplication
- inbox and outbox ids deduplicate identical payloads but reject conflicting
  payload reuse on the same identity
- incoming live handoffs reject early, expired, replayed, out-of-order, and
  mismatched-audience delivery before provider dispatch
- live cancellation suppresses late completed provider turns and converges the
  cancellation record to a resolved terminal state instead of reviving the run
- historical corruption remains preserved as informational audit evidence and cannot act as current guidance

## Current Mainline

The active mainline is `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`. It preserves the completed normalization, hardening, provider-compatibility, automation, brand, Agent Graph, dogfood, and 22-step stability/protocol/runtime records while advancing multi-provider control, standards-based external A2A, GUI/code orchestration parity, signed updates, CI enforcement, and final release closure.

The shared Desktop UI system is defined in `apps/astrabridge-desktop/src/features/ui/uiSystem.ts` and `styles.css`. It fixes the compact spacing, typography, control geometry, surface radius, focus, tooltip, dialog, and status-row contract; `uiSystem.test.ts` is the focused regression entry.

The completed repository normalization pass still defines the product boundary:

- active product state is `.abproj` plus workspace-local `.astrabridge/`
- legacy `.lcr*`, `.codexproj`, `.codex-shell`, and official-login paths are guardrail or historical-audit text only
- web, capability, automation, kernel, plugin, and skill surfaces use AstraBridge-owned APIs and isolated runtime roots
- demo artifacts, validation outputs, and private operator material are preserved by default

Current forward work starts from Step 7 of the canonical product-stability plan.
`PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` is a separate conditional active
queue only when the user explicitly asks for capability-runtime implementation;
otherwise the product-stability and interoperability plan remains the execution
entry.

Latest completed execution slice:

- Step 6 standardized the built-in provider transport ABI and tied multimodal
  live graph admission to current verified capability snapshots instead of
  static model booleans.
- Validation on 2026-07-17: `python -m unittest
  tests.test_provider_capability_snapshot
  tests.test_provider_transport_conformance
  tests.test_router_transport_registry tests.test_graph_scheduler
  tests.test_runtime_client_pool
  tests.test_provider_capability_verification_gate` passed 44/44 with a
  writable local runtime root; `python scripts\contract_boundary_audit.py`
  passed 21/21 checks; `python scripts\run_local_gate.py --quick` passed; `git
  diff --check` reported only CRLF warnings.
