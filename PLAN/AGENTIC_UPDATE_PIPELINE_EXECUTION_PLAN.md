# Agentic Update Pipeline Execution Plan

## Total Objective

Build an agent-friendly, user-scoped update pipeline for AstraBridge provider/model metadata, provider adapters, compatibility evidence, and Codex kernel candidate validation. The final system should let a user explicitly choose an update scope and version policy, then let an agent discover official upstream changes, generate a reviewable proposal, apply changes only in a safe boundary, run deterministic and provider-backed validation gates when authorized, and preserve a rollback path.

This plan does not mean AstraBridge should silently auto-update to every latest upstream release. The intended product behavior is controlled update assistance: discover, propose, verify, apply after approval, and promote only after evidence.

## Deliverables

- A dedicated AstraBridge update skill, provisionally under `apps/astrabridge-sidecar/skills/agentic-update-pipeline/`, with a `SKILL.md` that defines user-scoped update workflows, safety gates, and handoff rules.
- Update proposal schemas and scripts for discovery, diffing, validation, application, and rollback.
- Sidecar orchestration APIs for running update discovery/proposal jobs, reading status, preserving artifacts, applying approved proposals, and rolling back.
- Desktop UI surfaces for update scope selection, proposal review, explicit provider-call/install authorization, validation results, and rollback.
- Integration with existing metadata refresh, web lane, provider compatibility smoke, Codex kernel probe/smoke, automation scheduler, runbook, release checklist, and secret-scan gates.
- Secret-free durable evidence under `PRIVATE/agentic-update-pipeline/` and updated public docs/runbooks.

## Out Of Scope

- No automatic merge, push, release, or external platform writeback unless a later user explicitly authorizes that operation.
- No official OpenAI account login path. OpenAI remains a normal API-key provider.
- No reading desktop key files or plaintext secret files unless the user explicitly authorizes the exact path for the current run.
- No automatic provider-backed smoke, paid API call, or Codex candidate installation unless the proposal/run payload explicitly sets the corresponding authorization flag.
- No claim that a newly discovered model is agent-ready until validation evidence supports that claim.

## User Scope Contract

Every update run must start from an explicit user scope or a stored user-approved automation spec. A valid request should be normalized into a contract with these fields:

- `scope`: one or more of `provider_metadata`, `provider_adapter`, `capability_routes`, `codex_kernel`, `plugin_skill_surface`, `docs_only`.
- `providers`: optional list such as `qwen`, `deepseek`, `kimi`, `glm`, `yunwu`, `openai`.
- `models`: optional list of exact model ids.
- `version_policy`: `pinned`, `stable`, `latest`, `deprecated_check`, or `security_fix_only`.
- `target_version`: required when `version_policy=pinned`; may be a model id, release tag, or Codex version.
- `apply_mode`: `discover_only`, `proposal_only`, `isolated_apply`, `verify_candidate`, or `promote_after_smoke`.
- `allow_network`: default `true` for official docs discovery; can be disabled for fixture-only validation.
- `allow_provider_calls`: default `false`.
- `allow_install`: default `false`, only relevant for Codex kernel candidates or external dependencies.
- `allow_code_changes`: default `false` unless the user wants implementation changes.
- `approval_policy`: `manual_review_required` by default.

## Constraints And Attention Notes

1. Preserve all discovery inputs, fetched source records, parsed proposals, diffs, validation reports, smoke outputs, screenshots, rollback manifests, and run summaries under `PRIVATE/agentic-update-pipeline/` by default.
2. Never persist API keys, bearer tokens, cookies, authorization headers, vault passwords, admin tokens, desktop key contents, raw provider secrets, or raw private reasoning blobs.
3. Default to `proposal_only`. Do not modify router config, source code, generated catalog, Codex binary locators, plugin state, or user settings unless the current update contract permits it.
4. Use official provider documentation and official release/changelog sources by default. If a source is unofficial, mark it as `untrusted_source` and do not use it for promotion.
5. Keep web search as a standalone web lane. Discovery may use web/search/fetch/research records, but model-backed provider routing must not be used to fabricate source truth.
6. New or changed model capabilities must start conservative: text-only, no parallel tools, no hosted web/search, no `apply_patch`, no image/audio/tool capability, and no recommended/default promotion unless validation passes.
7. Provider-backed smoke and Codex candidate installation must be explicit, bounded, logged, and reversible.
8. All generated public docs must cite sanitized evidence paths and avoid raw external responses that may contain secrets or copyrighted long excerpts.
9. Any `full-access` automation or code-changing update must use explicit opt-in and a dedicated branch/worktree or equivalent rollback boundary.
10. The pipeline must be testable without network and without provider keys using fixtures.

## Adjustment Policy

Agents may reasonably adjust specific substeps, implementation details, file paths, commands, or sequencing when evidence from the workspace requires it. Such adjustments must not change the total objective, lower the planned safety bar, remove user-scope controls, remove validation gates, or replace substantive update work with cosmetic UI-only work. If a core objective becomes infeasible, record the blocker, evidence, attempted approaches, and a substitute path that preserves the original intent.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Start from the earliest numbered step whose status is not `completed`, unless the user redirects to a specific step.
3. Each turn must update this plan before stopping.
4. A step can be marked `completed` only when all of its acceptance criteria are met.
5. If blocked, mark the step `blocked`, record the concrete blocker and next entry point, and do not leave vague continuation notes.
6. Each turn must end with a handoff summary: completed work, files changed, validation run, blockers, and exact next step.

## Current Progress

- Current status: Complete
- Completed steps: 0. Create Durable Plan; 1. Baseline Inventory And Existing Surface Map; 2. Update Run Contract And Schema; 3. Artifact Layout And Rollback Manifest Design; 4. Provider Source Registry Hardening; 5. Discovery Runner; 6. Provider Parser Interface And Fixtures; 7. Codex Kernel Candidate Discovery; 8. Diff And Risk Classification Engine; 9. Agentic Update Skill Scaffold; 10. Proposal-Only Sidecar Service; 11. Desktop Proposal Review UI; 12. Isolated Apply Engine For Metadata-Only Changes; 13. Code-Change Proposal And Worktree Boundary; 14. Validation Gate Orchestrator; 15. Provider-Backed Smoke Integration; 16. Codex Kernel Verify Candidate Flow; 17. Automation Scheduler Integration; 18. End-To-End Fixture Dogfood; 19. Provider Pilot With User-Selected Scope; 20. Final Runbook, Release Checklist, And Promotion Policy
- Current step: Complete
- Next step: None
- Last updated: 2026-07-06

## Execution Steps

### 0. Create Durable Plan

Goal: Create this durable plan and make the next entry point clear.

Main actions:

- Define the controlled agentic update objective.
- Record scope contract, safety constraints, adjustment policy, execution rules, and implementation steps.
- Mark the initial next step for a future agent.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, deliverables, constraints, adjustment policy, current progress, numbered steps, acceptance criteria, and progress log.
- Step 1 is clearly identified as the next entry point.

Status: completed

### 1. Baseline Inventory And Existing Surface Map

Goal: Produce a current-source inventory of everything the updater should reuse instead of duplicating.

Main actions:

- Map existing metadata refresh APIs, web lane tools, provider compatibility smoke, capability smoke, model catalog generation, Codex kernel probe/smoke, automation scheduler, UI surfaces, and runbooks.
- Identify exact source owners and test owners for each surface.
- Record current gaps between existing mechanisms and the proposed update pipeline.

Acceptance criteria:

- A baseline report is saved under `PRIVATE/agentic-update-pipeline/reports/step1-baseline-inventory-<date>.md`.
- The report lists source files, APIs, UI entry points, existing tests, and reusable artifacts.
- The report explicitly distinguishes available mechanisms from missing updater features.
- No code or product config is changed in this step.

Status: completed

### 2. Update Run Contract And Schema

Goal: Define a stable, secret-free update run contract and proposal schema.

Main actions:

- Add schemas or typed helpers for update request, normalized scope contract, discovery result, proposal, diff, validation result, approval state, apply manifest, and rollback manifest.
- Include fields for `scope`, `version_policy`, `target_version`, `allow_provider_calls`, `allow_install`, `allow_code_changes`, and `apply_mode`.
- Add redaction and validation rules for forbidden secret fields and raw external payloads.

Acceptance criteria:

- Schema definitions exist in an appropriate sidecar module or documented JSON schema path.
- Unit tests cover valid and invalid scope contracts, missing pinned target versions, unsafe authorization combinations, and secret-like field rejection.
- A fixture proposal can be validated without network or provider keys.

Status: completed

### 3. Artifact Layout And Rollback Manifest Design

Goal: Establish durable evidence and rollback paths before any updater applies changes.

Main actions:

- Define the run directory layout under `PRIVATE/agentic-update-pipeline/runs/<run_id>/`.
- Define rollback manifests for router config, metadata sources, generated catalog locks, changed source files, UI changes, and Codex binary locator state.
- Define naming rules for fetched docs, parser outputs, proposal diffs, validation reports, screenshots, and secret-scan reports.

Acceptance criteria:

- A documented artifact contract exists in code or docs.
- Tests verify generated paths stay under the intended workspace/private roots.
- Rollback manifest fixtures can round-trip through JSON validation.
- The artifact layout does not require deleting old evidence.

Status: completed

### 4. Provider Source Registry Hardening

Goal: Turn existing provider source URLs into a maintained source registry suitable for update discovery.

Main actions:

- Extend the provider source model with source type, official/unofficial trust level, channel, parser strategy, stale-after policy, and provider-specific notes.
- Include current sources for Yunwu, OpenAI, DeepSeek, Kimi, Qwen, and GLM.
- Keep source edits reviewable and secret-free.

Acceptance criteria:

- Existing metadata source tests still pass.
- Source registry includes trust/channel/parser metadata for every managed provider.
- Sources are visible through sidecar metadata APIs and do not break existing UI.
- Untrusted or screenshot-seeded sources are clearly marked as non-promotable without manual review.

Status: completed

### 5. Discovery Runner

Goal: Implement a reusable discovery runner that fetches official sources and writes sanitized source packs.

Main actions:

- Reuse the standalone web lane and/or metadata fetcher to retrieve source pages.
- Preserve source URL, timestamp, HTTP status, content hash, content type, short excerpt, and fetch classification.
- Support fixture mode so tests can run without network.
- Enforce per-run source limits and timeouts.

Acceptance criteria:

- Discovery runner can run for one provider in fixture mode and write a complete source pack.
- Network mode records source metadata without secrets or full unbounded page dumps.
- Tests cover timeout, failed fetch, untrusted source, duplicate source, and fixture replay.

Status: completed

### 6. Provider Parser Interface And Fixtures

Goal: Create a parser interface that can convert source packs into structured provider/model metadata proposals.

Main actions:

- Define parser outputs for model id, display name, context window, modalities, reasoning modes, tool support, pricing, deprecation, default/recommended hints, source references, confidence, and warnings.
- Implement a generic conservative parser for simple JSON/table/text fixtures.
- Add provider-specific parser stubs for Qwen, DeepSeek, Kimi, GLM, OpenAI, and Yunwu.

Acceptance criteria:

- Parser fixtures produce deterministic proposals for at least two providers without network.
- Unknown fields default conservative and emit warnings.
- No parsed model is marked tool/web/vision/audio/apply-patch verified without validation evidence.

Status: completed

### 7. Codex Kernel Candidate Discovery

Goal: Add a controlled discovery path for Codex kernel candidates without installing or switching binaries by default.

Main actions:

- Define official release sources and candidate metadata fields.
- Discover candidate version, release date, platform, download/install hints, and changelog notes.
- Keep install and binary switching out of discovery unless `allow_install=true`.

Acceptance criteria:

- Fixture-based kernel candidate discovery works without network.
- Discovered candidates can be represented in the update proposal schema.
- The runner never writes official Codex config or AstraBridge runtime config during discovery.

Status: completed

### 8. Diff And Risk Classification Engine

Goal: Compare discovered proposals against the current AstraBridge catalog/profile/transport state and classify risk.

Main actions:

- Detect added models, removed/deprecated models, changed context windows, pricing changes, modality changes, reasoning changes, default changes, and transport/schema-impacting changes.
- Classify diffs as `docs_only`, `metadata_only`, `requires_adapter_review`, `requires_provider_smoke`, `requires_kernel_smoke`, or `blocked_manual_review`.
- Generate a human-readable Markdown proposal and machine-readable JSON diff.

Acceptance criteria:

- Diff tests cover add/change/remove/deprecate cases.
- Risk classification is conservative for tool calls, web search, apply_patch, audio, image, and long-context claims.
- Generated proposal points to source evidence and current-state references.

Status: completed

### 9. Agentic Update Skill Scaffold

Goal: Create the dedicated skill that agents will use to run controlled update workflows.

Main actions:

- Add `apps/astrabridge-sidecar/skills/agentic-update-pipeline/SKILL.md`.
- Document supported scopes, user contract fields, default modes, safety rules, required scripts, validation commands, and handoff protocol.
- Route provider metadata, provider adapter, Codex kernel, and docs-only workflows to the correct scripts and APIs.

Acceptance criteria:

- Skill file exists and is task-independent.
- Skill instructs agents to generate a proposal first and never silently apply changes.
- Skill references concrete scripts/API endpoints and evidence paths.
- Skill includes rollback and secret-scan rules.

Status: completed

### 10. Proposal-Only Sidecar Service

Goal: Expose sidecar APIs to start, inspect, and retrieve update discovery/proposal jobs.

Main actions:

- Add an update service with endpoints for `start`, `status`, `result`, and `list runs`.
- Wire discovery, parsing, diffing, and artifact persistence into proposal-only runs.
- Keep apply and provider-backed validation disabled until later steps.

Acceptance criteria:

- API tests cover starting a fixture update run, polling status, reading proposal output, and failed job handling.
- Proposal-only jobs do not mutate router config, source code, Codex binary locators, or provider credentials.
- Job result references artifact paths under `PRIVATE/agentic-update-pipeline/`.

Status: completed

### 11. Desktop Proposal Review UI

Goal: Add a user-facing review surface for update scope selection and proposal inspection.

Main actions:

- Add a UI panel under Setup or an appropriate manager area for selecting scope, provider, version policy, target version, and apply mode.
- Show proposal summary, source trust, risk classification, validation requirements, and artifact links.
- Keep apply/install/provider-call buttons disabled unless the current proposal and user authorization allow them.

Acceptance criteria:

- Desktop tests cover scope selection, proposal display, disabled unsafe actions, and error states.
- UI does not expose raw secrets or raw full external documents.
- A screenshot is preserved for the proposal review flow.

Status: completed

### 12. Isolated Apply Engine For Metadata-Only Changes

Goal: Implement the first safe apply path for metadata-only provider/model proposals.

Main actions:

- Apply only proposals classified as `metadata_only` or lower risk.
- Snapshot current router config and generated catalog metadata before applying.
- Write an apply manifest with files/config touched, before/after summary, and rollback path.

Acceptance criteria:

- Fixture proposal can apply in a temp project or isolated state root.
- Rollback restores the pre-apply router/catalog state in tests.
- Apply refuses high-risk changes, missing approval, missing rollback manifest, or unsafe paths.

Status: completed

### 13. Code-Change Proposal And Worktree Boundary

Goal: Support adapter/profile/source-code changes only inside an explicit branch/worktree boundary.

Main actions:

- Add a mode for `requires_adapter_review` proposals that creates or uses a dedicated worktree/branch.
- Generate a task brief for the agent explaining required files, tests, and evidence.
- Prevent direct main-worktree mutation unless the user explicitly chooses that mode.

Acceptance criteria:

- Tests or scripted dry runs prove code-change proposals produce a worktree/apply plan instead of mutating source by default.
- Branch/worktree path is recorded in the apply manifest.
- Rollback instructions are explicit and do not use destructive git commands without user approval.

Status: completed

### 14. Validation Gate Orchestrator

Goal: Provide one command/API path that runs the correct validation set for a proposal.

Main actions:

- Map risk classes to validation commands: schema tests, metadata tests, model catalog tests, provider compatibility smoke, capability smoke, Codex kernel smoke, desktop tests, build, diff check, and secret scan.
- Support fixture-only validation, dry-run validation, and provider-backed validation when authorized.
- Preserve validation reports and stdout/stderr excerpts in sanitized artifacts.

Acceptance criteria:

- Fixture validation gate passes without network or provider keys.
- Provider-backed validation is skipped with an explicit reason when unauthorized.
- Failed validation blocks promotion and records concrete next-fix targets.

Status: completed

### 15. Provider-Backed Smoke Integration

Goal: Connect update proposals to existing provider compatibility and capability smoke runners.

Main actions:

- Generate provider smoke cases from proposals.
- Require `allow_provider_calls=true` and available redacted credential status before real calls.
- Write smoke evidence and matrix update suggestions.

Acceptance criteria:

- Dry-run smoke cases are generated for proposed model/capability changes.
- Real provider smoke cannot run without explicit authorization.
- Smoke output is secret-free and links back to the proposal run id.

Status: completed

### 16. Codex Kernel Verify Candidate Flow

Goal: Implement the controlled Codex kernel candidate verification path.

Main actions:

- Accept a pinned Codex candidate binary or version locator.
- Run kernel probe and kernel smoke in isolated runtime roots.
- Produce a matrix update recommendation without rewriting official Codex config or normal user config.

Acceptance criteria:

- Candidate verification works in fixture or existing-binary mode.
- `verified` is impossible unless both probe and smoke evidence exist.
- Rollback evidence is recorded when a candidate is blocked or worse than baseline.

Status: completed

### 17. Automation Scheduler Integration

Goal: Allow user-approved recurring update checks without silent upgrades.

Main actions:

- Add an automation template for recurring `discover_only` or `proposal_only` checks.
- Ensure scheduled jobs respect daily run limits, network limits, provider-call authorization, and no-code-change defaults.
- Route findings to automation inbox with proposal artifact links.

Acceptance criteria:

- Scheduled update check can run in fixture mode and create an inbox finding.
- No scheduled job can apply changes, install binaries, or call providers unless that exact authorization is stored in the automation spec.
- Automation evidence is preserved and secret-free.

Status: completed

### 18. End-To-End Fixture Dogfood

Goal: Validate the whole pipeline without network, provider keys, installs, or source-code mutation.

Main actions:

- Create fixture docs for one provider new-model release and one Codex candidate release.
- Run discovery, parse, diff, proposal review, validation, and blocked apply paths.
- Capture UI screenshots and evidence.

Acceptance criteria:

- End-to-end fixture run produces a proposal, diff, validation report, rollback manifest, and UI screenshot.
- Unsafe actions remain disabled in UI and API without authorization.
- Local tests, `git diff --check`, and secret scan pass for touched files and artifacts.

Status: completed

### 19. Provider Pilot With User-Selected Scope

Goal: Run one real, user-selected provider/model update pilot after explicit authorization.

Main actions:

- Ask the user to select provider, version policy, and whether provider-backed calls are allowed.
- Run discovery against official sources.
- Generate proposal, validate, optionally apply metadata-only changes, and preserve evidence.

Acceptance criteria:

- Pilot scope is explicitly recorded in the run contract.
- Proposal and validation artifacts are preserved under `PRIVATE/agentic-update-pipeline/`.
- Any real provider call is authorized, bounded, and recorded as sanitized evidence.
- Final status is one of `proposal_only_complete`, `applied_metadata_only`, `blocked_manual_review`, or `failed_with_rollback_available`.

Status: completed

### 20. Final Runbook, Release Checklist, And Promotion Policy

Goal: Document the finished update pipeline and define promotion rules for future provider/model/kernel updates.

Main actions:

- Add or update public docs for using the update skill, UI, APIs, scripts, automation template, rollback, and validation gates.
- Update release checklist with updater-specific gates.
- Define exact language for statuses: discovered, proposed, applied, verified, partial, blocked, deprecated, recommended.

Acceptance criteria:

- Public docs explain how a user specifies update scope and version policy.
- Docs state what is never automatic.
- Release checklist includes updater validation, rollback verification, and secret-scan gates.
- Final report summarizes implemented surfaces, remaining limitations, and next recommended pilot.

Status: completed

## Progress Log

### 2026-07-06 - Post-completion Qwen Provider Smoke Follow-up

- Completed: Continued the recommended Qwen provider-backed smoke after explicit provider-call authorization. The first attempt was blocked by the admin guard before provider execution. The r2 smoke initially reported `partial`, but artifact inspection proved the runtime actually invoked Kimi (`provider_id=kimi`, `model=kimi-k2.7-code`) while the report displayed Qwen case labels, so r2 is invalid as Qwen evidence. The root cause was provider-backed default smoke fixtures not preserving explicit `provider_id`, `model`, and `workspace_root` into the runtime payload; the source and tests now cover that. The r3 smoke used explicit inline image input to force a true Qwen route and both Qwen vision cases failed with DashScope HTTP 400, making r3 valid known-failure evidence. Added conservative HTTPS image URL support to the chat vision adapter so the next Qwen run can avoid inline data URI images.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/vision_analyze_adapter.py`, `apps/astrabridge-sidecar/tests/test_capability_smoke.py`, `apps/astrabridge-sidecar/tests/test_provider_compatibility_smoke.py`, `apps/astrabridge-sidecar/tests/test_vision_analyze_adapter.py`, `PRIVATE/agentic-update-pipeline/reports/followup-qwen-provider-smoke-20260706.md`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Evidence: Preserved `followup-qwen-provider-smoke-20260706-attempt1-http400`, `followup-qwen-provider-smoke-20260706-r2`, and `followup-qwen-provider-smoke-20260706-r3` under `PRIVATE/agentic-update-pipeline/runs/`. The follow-up report records why r2 must not be used as Qwen pass evidence, why r3 is a real Qwen failure record, and why the HTTPS image URL path remains provider-unverified until the sidecar is reloaded with managed Qwen credentials.
- Validation: Ran the focused provider/capability/agentic-update tests and the broader agentic update regression set; 77 tests passed. Ran `py_compile` for the touched provider/capability files and tests. Ran `git diff --check`; it exited cleanly with only existing LF-to-CRLF working-copy warnings. Ran a focused sensitive-value scan over touched source/tests, the follow-up report, the plan, attempt1/r2/r3 Qwen smoke evidence, and the invalid Kimi artifact summaries; no real secret matches.
- Blockers: The live `8791` sidecar still has old adapter code loaded, and this shell does not expose Qwen/DashScope environment credentials. Do not restart the sidecar from this shell unless the credential path is intentionally restored through a managed mechanism.
- Next step: Reload or start a sidecar with updated source plus managed Qwen credentials, then rerun a small provider-backed `vision.analyze` smoke using a public HTTPS image URL fixture. Treat r2 as invalid and r3 as a known-failure baseline until that rerun passes.

### 2026-07-06 - Step 20

- Completed: Added the final public runbook for the controlled agentic update pipeline, updated the release checklist with updater-specific gates, and wrote the final implementation report. The runbook documents how users specify update scope, provider/model filters, version policy, pinned target versions, apply mode, network allowance, provider-call authorization, install authorization, code-change authorization, and manual approval policy. It also records what is never automatic, the supported entry points, preserved artifact layout, validation gates, rollback requirements, status language, promotion policy, and the next recommended Qwen parser pilot.
- Files changed: `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`, `docs/RELEASE_CHECKLIST.md`, `PRIVATE/agentic-update-pipeline/reports/step20-final-report-20260706.md`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Evidence: The final report summarizes implemented surfaces across the skill/user contract, artifact and rollback layout, discovery, parsing, Codex kernel candidate discovery, diff/proposal/risk classification, sidecar API, desktop proposal UI, isolated metadata apply, code-change boundary planning, validation gates, provider smoke integration, kernel verification, automation templates, Step 18 fixture dogfood, and Step 19 Qwen official-docs pilot. It records remaining limitations and the recommended next pilot instead of overclaiming promotion readiness.
- Validation: Ran the agentic update sidecar regression suite covering service, contract, artifacts, discovery, parsers, diffing, kernel candidates, and automation; 52 tests passed. Verified the new runbook, release checklist, and final report contain scope/version policy, never-automatic, rollback, secret-scan, promotion, and next-pilot language. Ran `git diff --check`; it exited cleanly with only existing LF-to-CRLF warnings. Adjusted the release checklist's example secret-scan pattern so the documentation does not trigger its own sensitive-value scan.
- Blockers: None.
- Next step: None; all numbered steps are complete.

### 2026-07-06 - Step 19

- Completed: Ran a real provider metadata pilot against Qwen official documentation under the safest available scope: `provider_metadata`, provider `qwen`, `version_policy=stable`, `apply_mode=proposal_only`, `allow_network=true`, and no provider calls, installs, or code changes authorized. The interactive scope-selection tool was unavailable in this continuation mode, so the pilot recorded the conservative active-plan continuation scope and did not authorize any paid provider-backed calls. Discovery fetched 5 official Qwen / DashScope source records successfully in network mode and preserved source hashes/excerpts; proposal generation and validation artifacts were written under the Step 3 run layout. The generic HTML parser produced a conservative `requires_adapter_review` proposal for `qwen/unknown-model`, showing the current parser is not promotion-safe for this official HTML source. Provider compatibility and capability smoke gates were skipped with `provider_calls_not_authorized` and blocked promotion, yielding final status `blocked_manual_review`, which is one of the planned Step 19 terminal statuses.
- Files changed: `PRIVATE/agentic-update-pipeline/step19_provider_pilot_runner.py`, `PRIVATE/agentic-update-pipeline/runs/step19-provider-pilot-qwen-20260706/`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Evidence: Preserved Step 19 run `step19-provider-pilot-qwen-20260706` under `PRIVATE/agentic-update-pipeline/runs/step19-provider-pilot-qwen-20260706/`, including `run-contract.json`, `sources/source-index.json`, `sources/source-pack.jsonl`, `parsed/parser-output.json`, `proposals/proposal.json`, `diffs/proposal-diff.json`, `validation/validation-report.json`, `rollback/rollback-manifest.json`, `secret-scan/secret-scan-report.json`, `logs/step19-provider-pilot-report.json`, and `logs/step19-provider-pilot-report.md`. The summary top-level status is `blocked_manual_review`; provider calls attempted, installs attempted, code changes attempted, and apply are all false.
- Validation: Ran `.\.venv\Scripts\python.exe .\PRIVATE\agentic-update-pipeline\step19_provider_pilot_runner.py` and it completed with final status `blocked_manual_review`. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service tests.test_agentic_update_discovery tests.test_agentic_update_parsers tests.test_agentic_update_diffing tests.test_agentic_update_contract tests.test_agentic_update_artifacts tests.test_provider_source_registry` from `apps/astrabridge-sidecar` and passed 49 tests. Ran `py_compile` for the Step 19 runner with `PYTHONPYCACHEPREFIX=D:\AstraBridge\PRIVATE\agentic-update-pipeline\pycache-step19`. Ran `git diff --check`; it exited cleanly with only existing CRLF warnings. Ran a focused sensitive-value scan over the Step 19 runner, Step 19 run artifacts, and this plan; no matches were found.
- Blockers: None.
- Next step: Step 20, Final Runbook, Release Checklist, And Promotion Policy.

### 2026-07-05 - Step 18

- Completed: Added an offline end-to-end fixture dogfood harness for the agentic update pipeline. The new harness creates fixture source documents for one Qwen new-model release and one Codex kernel candidate release, runs the existing proposal-only service through discovery, parsing, kernel candidate discovery, diffing, proposal writing, fixture-only validation, blocked apply checks, rollback manifest generation, review snapshot rendering, Playwright screenshot capture, and sensitive scan report generation. The dogfood run records that no network, provider calls, installs, code changes, router config changes, Codex binary locator changes, or official Codex config writes were authorized or attempted. Unsafe API paths are blocked both before manual approval and after manual approval because the combined proposal risk is `requires_kernel_smoke`; the review snapshot records apply, provider-smoke, install, and code-change actions as disabled.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/dogfood.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_fixture_dogfood.py`, `scripts/agentic_update_fixture_dogfood.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Evidence: Real fixture dogfood run `step18-fixture-dogfood-20260705-r2` passed and preserved artifacts under `PRIVATE/agentic-update-pipeline/runs/step18-fixture-dogfood-20260705-r2/`, including `proposals/proposal.json`, `diffs/proposal-diff.json`, `validation/validation-report.json`, `rollback/rollback-manifest.json`, `screenshots/proposal-review.png`, `screenshots/screenshot-index.json`, `secret-scan/secret-scan-report.json`, and `logs/step18-fixture-dogfood-report.json`.
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_fixture_dogfood` and passed 1 test. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_fixture_dogfood tests.test_agentic_update_service tests.test_agentic_update_diffing tests.test_agentic_update_kernel_candidates tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract tests.test_agentic_update_kernel_verify tests.test_agentic_update_automation` from `apps/astrabridge-sidecar` and passed 59 tests. Ran `.\.venv\Scripts\python.exe -m py_compile` for the new dogfood module, package export, and test with `PYTHONPYCACHEPREFIX=D:\AstraBridge\PRIVATE\agentic-update-pipeline\pycache-step18`. Ran `git diff --check`; it exited cleanly with only existing CRLF warnings. Ran a focused sensitive-value scan over touched files and `PRIVATE/agentic-update-pipeline/runs/step18-fixture-dogfood-20260705-r2`; no matches were found.
- Blockers: None.
- Next step: Step 19, Provider Pilot With User-Selected Scope.

### 2026-07-05 - Step 17

- Completed: Added automation scheduler integration for controlled agentic update checks. Automation specs now support a new `agentic_update_check` kind with a normalized, secret-free `agentic_update` section, proposal/discover-only apply modes, read-only runtime enforcement, fixture-only or official-docs-only network policy, bounded source-record limits, disabled side effects, and required daily run limits for recurring schedules. The automation service can create disabled-by-default update check templates from user scope/version payloads, and the sidecar exposes `POST /api/agentic-updates/automation-template`. The automation runner now invokes `AgenticUpdateService.start()` directly for check runs, creates proposal-only update runs, classifies detected changes as inbox findings, and preserves proposal/diff/summary artifact references in the automation run, manifest, and inbox item.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/automations/specs.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/automations/runner.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/automations/service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/automations/triage.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/automations/store.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_automation.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_automation tests.test_automation_api tests.test_agentic_update_service` from `apps/astrabridge-sidecar` and passed 30 tests. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_automation tests.test_automation_api tests.test_agentic_update_service tests.test_agentic_update_contract tests.test_agentic_update_diffing tests.test_agentic_update_discovery tests.test_agentic_update_parsers tests.test_agentic_update_kernel_candidates tests.test_agentic_update_artifacts tests.test_provider_source_registry` and passed 66 tests. Ran `.\.venv\Scripts\python.exe -m py_compile` for the touched automation, server, and test files. Checked touched files for conflict markers and trailing whitespace. Ran a focused secret-like scan; matches were only existing `server.py` ephemeral API-key handler field names, not persisted secrets.
- Blockers: None.
- Next step: Step 18, End-To-End Fixture Dogfood.

### 2026-07-05 - Step 16

- Completed: Added the controlled Codex kernel candidate verification path. The new kernel verification module accepts a pinned Codex kernel candidate from an update proposal plus an optional existing binary locator, runs fixture or existing-binary verification under the agentic update run's isolated `validation/codex-kernel-verify/` artifact root, preserves smoke and kernel-probe evidence, and emits a Codex kernel matrix update suggestion without rewriting official Codex config, project `.codex*` files, AstraBridge runtime config, or normal user settings. The service now exposes `verify_kernel_candidate()`, and the HTTP API exposes `POST /api/agentic-updates/kernel-verify`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/kernel_verify.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_kernel_verify.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service` from `apps/astrabridge-sidecar` and passed 18 tests, including the new HTTP kernel verify path. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_kernel_verify tests.test_agentic_update_kernel_candidates tests.test_codex_kernel_smoke tests.test_codex_kernel_matrix_gate` and passed 12 tests, including existing-binary mode with a fake smoke runner. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service tests.test_agentic_update_kernel_verify tests.test_agentic_update_kernel_candidates tests.test_agentic_update_diffing tests.test_agentic_update_contract tests.test_agentic_update_artifacts tests.test_codex_kernel_probe_snapshot tests.test_codex_kernel_smoke tests.test_codex_kernel_matrix_gate` and passed 50 tests. Ran `py_compile` for the touched modules/tests with `PYTHONPYCACHEPREFIX=D:\AstraBridge\PRIVATE\agentic-update-pipeline\pycache-step16`. Ran `git diff --check`; only the pre-existing line-ending warning for `server.py` appeared. Checked touched files for conflict markers. Ran a focused secret-like scan; matches were code field names, existing server secret/admin-token handlers, and unit-test fake `unit-admin-token` strings.
- Blockers: None.
- Next step: Step 17, Automation Scheduler Integration.

### 2026-07-05 - Step 15

- Completed: Integrated update proposals with the existing provider compatibility and capability smoke runners. Added proposal-to-smoke-case generation for capability/model changes that require provider smoke, with conservative automated support for image generation, vision analysis, speech transcription, and speech synthesis. Provider-backed smoke now requires both explicit `allow_provider_calls=true` authorization and redacted credential availability before real runtime calls; otherwise the gate records a blocked/skipped reason without invoking the provider runtime. Validation gates now attach compact provider smoke summaries, preserve secret-free case packs and smoke reports under the agentic update run, emit matrix update suggestions linked back to the proposal run id, and use short stable internal smoke run ids to avoid Windows path-length failures in nested evidence paths.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/provider_smoke.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/validation.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran a focused diagnostic confirming provider-backed smoke blocks without credentials and does not call runtime, then passes with redacted credential availability and calls runtime. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service` from `apps/astrabridge-sidecar` and passed 16 tests. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service tests.test_agentic_update_diffing tests.test_agentic_update_kernel_candidates tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract tests.test_provider_compatibility_smoke tests.test_capability_smoke` and passed 65 tests. Ran `py_compile` for the touched sidecar modules/tests with `PYTHONPYCACHEPREFIX=D:\AstraBridge\PRIVATE\agentic-update-pipeline\pycache-step15`. Ran `git diff --check` on the touched files; only the pre-existing line-ending warning for `server.py` appeared. Checked touched files for conflict markers. Ran a focused secret-like scan; matches were only code field names and existing unit-test fake tokens such as `unit-admin-token`.
- Blockers: None.
- Next step: Step 16, Codex Kernel Verify Candidate Flow.

### 2026-07-05 - Step 14

- Completed: Added the agentic update validation gate orchestrator and API path. The new validation module maps proposal risk classes to concrete gate IDs and command/API shapes for schema validation, metadata tests, model catalog tests, transport tests, provider compatibility smoke, capability smoke, Codex kernel probe/smoke, desktop tests, desktop build, git diff check, secret scan, rollback review, and manual review. It supports `dry_run`, `fixture_only`, and `provider_backed` modes, writes `validation/validation-report.json` and `validation/validation-report.md`, stores sanitized stdout/stderr excerpts, updates the proposal `validation_result`, writes validation status into the run summary, and records `next_fix_targets` whenever validation blocks promotion. Provider-backed gates are explicitly skipped with `provider_calls_not_authorized` and still block promotion when the run is not authorized for provider calls; real provider smoke case generation remains the next step.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/validation.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service` from `apps/astrabridge-sidecar` and passed 13 tests, including fixture-only validation pass without provider keys, dry-run gate recording without execution, provider-backed gate skip without authorization, failed gate promotion blocking with next-fix target, and HTTP validate coverage. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service tests.test_agentic_update_diffing tests.test_agentic_update_kernel_candidates tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` and passed 49 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\validation.py astrabridge_sidecar\agentic_updates\__init__.py astrabridge_sidecar\agentic_update_service.py astrabridge_sidecar\server.py tests\test_agentic_update_service.py`. Ran `git diff --check` and conflict-marker scan over touched files; only the existing Windows LF-to-CRLF warning for `server.py` appeared. Ran a focused secret-like scan; matches were pre-existing server secret-service/admin-token route names, synthetic unit-test admin token text, `QWEN_API_KEY` env-key fixture text, validation gate names/safety text, and policy wording in this plan, not persisted raw secrets.
- Blockers: None.
- Next step: Step 15, Provider-Backed Smoke Integration.

### 2026-07-05 - Step 13

- Completed: Added a code-change boundary planner for `requires_adapter_review` proposals. The new planner requires manual approval, requires `run_contract.allow_code_changes=true`, refuses blocked or non-code-change proposals, defaults to a dedicated worktree boundary, records a `codex/agentic-update/<run_id>` branch name, records the planned worktree path, generates a task brief with likely source/test files and validation/evidence expectations, writes an apply manifest without mutating source files, and writes rollback instructions that require explicit user approval before removing the worktree or deleting the branch. The service exposes `code_change_plan()` and `POST /api/agentic-updates/code-change-plan`; `AppContext` passes the project runtime root so real future worktrees can live outside the main workspace. Direct current-workspace mutation is refused unless the payload explicitly opts in with `allow_main_worktree_mutation=true`, and even then this step only plans the boundary rather than applying source edits.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/code_changes.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service` from `apps/astrabridge-sidecar` and passed 9 tests, including dry-run code-change worktree planning, source non-mutation, branch/worktree path manifest recording, current-workspace refusal without opt-in, non-code proposal refusal, and HTTP code-change-plan coverage. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service tests.test_agentic_update_diffing tests.test_agentic_update_kernel_candidates tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` and passed 45 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\code_changes.py astrabridge_sidecar\agentic_updates\__init__.py astrabridge_sidecar\agentic_update_service.py astrabridge_sidecar\server.py tests\test_agentic_update_service.py`. Ran `git diff --check` and conflict-marker scan over touched files; only the existing Windows LF-to-CRLF warning for `server.py` appeared. Ran a focused secret-like scan; matches were pre-existing server secret-service/admin-token route names, synthetic unit-test admin token text, `QWEN_API_KEY` env-key fixture text, safety wording in the new task brief, and policy wording in this plan, not persisted raw secrets.
- Blockers: None.
- Next step: Step 14, Validation Gate Orchestrator.

### 2026-07-05 - Step 12

- Completed: Added the first safe isolated apply path for metadata-only agentic update proposals. The new apply engine validates the proposal, requires explicit manual approval, refuses risk classes above `metadata_only`, refuses unsupported metadata change types, requires a reversible proposal rollback contract, snapshots sanitized router config and generated catalog locks, writes isolated router/catalog state under the run artifact boundary by default, preserves before-state backups, writes an apply manifest with before/after summaries and touched paths, and rolls back by restoring the backed-up router/catalog state. The sidecar service now exposes apply and rollback methods plus `POST /api/agentic-updates/apply` and `POST /api/agentic-updates/rollback`; this path does not mutate the live router config or global generated catalog by default.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/apply.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service` from `apps/astrabridge-sidecar` and passed 7 tests, including fixture metadata apply, rollback restore, missing approval refusal, high-risk refusal, missing rollback refusal, unsafe path refusal, and HTTP apply/rollback. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service tests.test_agentic_update_diffing tests.test_agentic_update_kernel_candidates tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` and passed 43 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\apply.py astrabridge_sidecar\agentic_updates\__init__.py astrabridge_sidecar\agentic_update_service.py astrabridge_sidecar\server.py tests\test_agentic_update_service.py`. Ran `git diff --check` and conflict-marker scan over touched files; only the existing Windows LF-to-CRLF warning for `server.py` appeared. Ran a focused secret-like scan; matches were pre-existing server secret-service/admin-token route names, synthetic unit-test admin token text, `QWEN_API_KEY` env-key fixture text, and policy wording in this plan, not persisted raw secrets.
- Blockers: None.
- Next step: Step 13, Code-Change Proposal And Worktree Boundary.

### 2026-07-05 - Step 11

- Completed: Added a desktop `AgenticUpdateReviewPanel` under the Setup/developer area for proposal-only update review. The UI lets users select update scope, provider, version policy, pinned target version, apply mode, and public-doc fetch allowance, then calls the Step 10 proposal API. It displays proposal status, risk class, change count, run id, selected scope/provider, source trust rows, change/risk rows, validation requirements, and artifact paths. Apply, provider-smoke, and install actions are present but disabled in the proposal review surface. Displayed source/proposal strings are limited to selected safe fields and lightly redacted; raw excerpts, raw external document bodies, and secret-like fields are not rendered.
- Files changed: `apps/astrabridge-desktop/src/types.ts`, `apps/astrabridge-desktop/src/api.ts`, `apps/astrabridge-desktop/src/features/updates/AgenticUpdateReviewPanel.tsx`, `apps/astrabridge-desktop/src/features/updates/AgenticUpdateReviewPanel.test.tsx`, `apps/astrabridge-desktop/src/features/navigation/abilityEntries.ts`, `apps/astrabridge-desktop/src/features/i18n/catalog.ts`, `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/styles.css`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `npm.cmd run test -- AgenticUpdateReviewPanel.test.tsx` from `apps/astrabridge-desktop` and passed 3 tests covering scoped request construction, proposal display, disabled unsafe actions, redaction/non-rendering of raw secret-like excerpt content, and request error state. Ran `npm.cmd run build` from `apps/astrabridge-desktop`; TypeScript and Vite build passed with the existing large chunk warning. Preserved screenshot evidence at `PRIVATE/agentic-update-pipeline/screenshots/step11-proposal-review-ui.png` with companion static screenshot fixture `PRIVATE/agentic-update-pipeline/screenshots/step11-proposal-review-ui.html`; a live preview attempt against the current sidecar opened the launcher instead of the active project, so the screenshot fixture links the built desktop CSS while behavior is covered by the component tests.
- Blockers: None.
- Next step: Step 12, Isolated Apply Engine For Metadata-Only Changes.

### 2026-07-05 - Step 10

- Completed: Added the proposal-only agentic update sidecar service and HTTP API entry points. The new `AgenticUpdateService` registers proposal jobs, normalizes and records run contracts, creates the Step 3 artifact layout, runs provider discovery/parsing, runs Codex kernel candidate discovery when scoped, builds the Step 8 diff, writes `proposals/proposal.json`, `diffs/proposal-diff.json`, `diffs/proposal.md`, and `summary.json`, exposes job `start`, `status`, `result`, and `list_runs`, and records failed jobs so callers can inspect errors. The service is intentionally proposal-only: it rejects apply/provider-call/install/code-change modes, writes `changed_paths=[]`, records no runtime/source/provider credential mutations, and only reads current router models for diff context. `server.py` now exposes `POST /api/agentic-updates/start`, `GET /api/agentic-updates/runs`, `GET /api/agentic-updates/status`, `GET /api/agentic-updates/result`, plus `/api/agentic-updates/<run_id>/status` and `/api/agentic-updates/<run_id>/result`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service` from `apps/astrabridge-sidecar` and passed 5 tests, covering fixture start/status/result/list API flow, failed job status, failed result HTTP handling, and proposal-only rejection of apply/provider-call/install/code-change modes. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_service tests.test_agentic_update_diffing tests.test_agentic_update_kernel_candidates tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` and passed 41 tests. Ran `py_compile` for `agentic_update_service.py`, `server.py`, and `test_agentic_update_service.py` with `PYTHONPYCACHEPREFIX=D:\AstraBridge\PRIVATE\agentic-update-pipeline\pycache-step10` after the default Windows pycache path hit a transient access-denied error. Checked touched files for trailing whitespace and conflict markers. Ran a focused secret-like scan; matches were existing non-secret `API-key provider` text in this plan and pre-existing API-key/admin-token handler names in `server.py`.
- Blockers: None.
- Next step: Step 11, Desktop Proposal Review UI.

### 2026-07-05 - Step 9

- Completed: Added the dedicated `agentic-update-pipeline` skill scaffold under `apps/astrabridge-sidecar/skills/agentic-update-pipeline/`. The skill defines when agents should use the update pipeline, requires every run to start from an explicit scope contract, defaults to proposal-first behavior, forbids silent apply/install/provider calls/external writeback, points agents to current sidecar code entry points for contracts/artifacts/discovery/parsing/kernel candidates/diffing, lists expected evidence paths under `PRIVATE/agentic-update-pipeline/runs/<run_id>/`, documents future proposal-only API shapes for Step 10, routes provider metadata, provider adapter/capability route, Codex kernel, docs-only, and plugin/skill workflows, records conservative risk classes, and includes validation, rollback, and secret-scan rules. The skill was initialized with the skill-creator scaffold and includes `agents/openai.yaml` UI metadata generated from the skill purpose.
- Files changed: `apps/astrabridge-sidecar/skills/agentic-update-pipeline/SKILL.md`, `apps/astrabridge-sidecar/skills/agentic-update-pipeline/agents/openai.yaml`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `python C:\Users\cyz19\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AstraBridge\apps\astrabridge-sidecar\skills\agentic-update-pipeline` and it reported `Skill is valid!`. Ran content checks confirming the skill contains proposal-first/no-silent-apply rules, concrete current code entry points, future API shapes, evidence paths, rollback rules, and secret-scan rules. Checked touched skill files and this plan for TODOs, trailing whitespace, and conflict markers. Ran a focused secret-like scan; matches were only existing non-secret `API-key provider` text in this plan and prior validation notes mentioning that phrase.
- Blockers: None.
- Next step: Step 10, Proposal-Only Sidecar Service.

### 2026-07-05 - Step 8

- Completed: Added the agentic update diff and risk classification engine. The new diff module compares parsed provider/model proposals and Codex kernel candidates against current model state, writes machine-readable `diffs/proposal-diff.json`, writes human-readable `diffs/proposal.md`, and can update an existing proposal JSON with the generated diff. It detects added models, removed models when a complete provider snapshot is explicitly provided, deprecated/undeprecated models, context window changes, pricing changes, modality changes, reasoning/default changes, default/recommended hint changes, capability claim changes, transport/schema review signals, and Codex kernel candidates. Risk classification is conservative: image/audio/video modalities, tool calls, web search, apply_patch claims, reasoning changes, and long-context claims require provider smoke; Codex kernel candidates require kernel probe/smoke; unknown schema fields or missing provider ids require adapter review; removals require manual review. Markdown proposal rows include source evidence labels and current-state references.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/diffing.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_diffing.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_diffing` from `apps/astrabridge-sidecar` and passed 4 tests. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_diffing tests.test_agentic_update_kernel_candidates tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` and passed 36 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\diffing.py astrabridge_sidecar\agentic_updates\__init__.py tests\test_agentic_update_diffing.py`. Checked touched files for trailing whitespace and conflict markers. Ran a focused secret-like scan; matches were only existing non-secret `API-key provider` text in this plan and the prior Step 7 validation note mentioning that phrase.
- Blockers: None.
- Next step: Step 9, Agentic Update Skill Scaffold.

### 2026-07-05 - Step 7

- Completed: Added controlled Codex kernel candidate discovery for the agentic update pipeline. The new candidate discovery module declares official release/package/install-hint sources, parses fixture source bodies into candidate version records, writes `parsed/codex-kernel-candidates.json`, and also writes a proposal-compatible `proposals/proposal.json`. Candidate records include version, release date, platforms, download/install/changelog hints, source refs, conservative validation and promotion state, permission policy, and an explicit side-effect policy showing discovery does not write official Codex config, project `.codex*` files, AstraBridge runtime config, install binaries, or switch binaries. `allow_install=true` only changes the permission flag for later verification steps; it does not perform installation or switching.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/kernel_candidates.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_kernel_candidates.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_kernel_candidates` from `apps/astrabridge-sidecar` and passed 5 tests. Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_kernel_candidates tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` and passed 32 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\kernel_candidates.py astrabridge_sidecar\agentic_updates\__init__.py tests\test_agentic_update_kernel_candidates.py`. Checked touched files for trailing whitespace and conflict markers. Ran a focused secret-like scan; the only match was the existing non-secret policy phrase `API-key provider` in this plan.
- Blockers: None.
- Next step: Step 8, Diff And Risk Classification Engine.

### 2026-07-05 - Step 6

- Completed: Added the conservative provider parser interface and fixture coverage. The parser reads Step 5 source packs or direct in-memory fixture records, extracts simple JSON, fenced JSON, JSON arrays, and line-oriented key/value model records, then writes `parsed/parser-output.json` under the Step 3 artifact layout. Parser output includes model id, display name, context window, modalities, reasoning levels, default reasoning, pricing, deprecation/default/recommended hints, confidence, source references, capability claims, validation state, and warnings. Provider-specific stubs are registered for Qwen, DeepSeek, Kimi, GLM, OpenAI, and Yunwu, currently delegating to the generic conservative parser. Unknown fields are retained long enough to emit `unknown_field:*` warnings, and missing context/modalities/reasoning fields default conservatively.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/parsers.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_parsers.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_parsers tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` from `apps/astrabridge-sidecar` and passed 27 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\parsers.py astrabridge_sidecar\agentic_updates\__init__.py tests\test_agentic_update_parsers.py`. Checked touched files for trailing whitespace/conflict markers. Ran a focused secret-like scan over parser files and tests with no matches.
- Blockers: None.
- Next step: Step 7, Codex Kernel Candidate Discovery.

### 2026-07-05 - Step 5

- Completed: Added the reusable agentic update discovery runner. The runner normalizes the user run contract, reuses the Step 3 artifact layout, consumes the hardened Step 4 provider source registry, filters by requested provider scope, deduplicates source URLs, skips non-official/non-promotable sources as `untrusted_source`, supports fixture replay without network, and supports bounded network fetches. It writes `sources/source-index.json` and `sources/source-pack.jsonl` under `PRIVATE/agentic-update-pipeline/runs/<run_id>/`, recording source URL, final URL, timestamps, HTTP status, content type, content hash, byte count, truncation flag, short sanitized excerpt, trust/channel/parser metadata, classification, and warnings. Network fetches are capped by per-run source count, timeout, max bytes, and max excerpt chars; raw full page dumps and secret-like text are not persisted.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/discovery.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_discovery.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_discovery tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` from `apps/astrabridge-sidecar` and passed 23 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\discovery.py astrabridge_sidecar\agentic_updates\__init__.py tests\test_agentic_update_discovery.py`. Checked touched files for trailing whitespace/conflict markers. Ran a focused secret-like scan over touched discovery files; the only match was the synthetic bearer string in `test_agentic_update_discovery.py` used to verify excerpt redaction.
- Blockers: None.
- Next step: Step 6, Provider Parser Interface And Fixtures.

### 2026-07-05 - Step 4

- Completed: Hardened the provider source registry used by the generated catalog and metadata API. Added a normalized provider source registry model with `source_type`, `trust_level`, `channel`, `parser_strategy`, `stale_after_days`, `promotion_policy`, provider-level `source_provenance`, and per-URL `source_records`. The default registry now covers Yunwu, OpenAI, DeepSeek, Kimi, Qwen, and GLM. Official provider sources are marked as official and promotable only after later parser/smoke validation; Yunwu screenshot/Apifox-seeded sources and unknown custom sources are explicitly non-promotable and require manual review. The generated catalog writes `source_registry_schema` to `sources.lock.json`, propagates enhanced source provenance into model records, and the metadata sources API returns the normalized fields without removing the legacy `urls`, `source_status`, and `notes` fields used by the desktop UI.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/metadata_service.py`, `apps/astrabridge-sidecar/tests/test_provider_source_registry.py`, `apps/astrabridge-desktop/src/types.ts`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_provider_source_registry tests.test_agentic_update_artifacts tests.test_agentic_update_contract` from `apps/astrabridge-sidecar` and passed 18 tests. Ran existing metadata/catalog tests: `tests.test_sidecar_services.AstraBridgeServiceTests.test_metadata_seed_import_and_effective_catalog_are_conservative`, `test_metadata_report_writes_sanitized_html_and_catalog_json`, `test_metadata_refresh_writes_source_level_artifacts_and_partial_summary`, `test_metadata_refresh_async_job_exposes_status_and_result`, `test_router_http_metadata_and_health_endpoints_expose_generated_catalog_provenance`, and `tests.test_model_catalog_contract`; all 7 passed. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\model_catalog\source_registry.py astrabridge_sidecar\model_catalog\generated_catalog.py astrabridge_sidecar\model_catalog\__init__.py astrabridge_sidecar\metadata_service.py tests\test_provider_source_registry.py`. Ran `node .\node_modules\typescript\bin\tsc --noEmit` from `apps/astrabridge-desktop`; passed. Checked touched files for trailing whitespace/conflict markers. Ran a focused secret-like scan over touched files; matches were a synthetic rejection fixture in `test_provider_source_registry.py` and an existing non-secret `token` type field in `types.ts`.
- Blockers: None.
- Next step: Step 5, Discovery Runner.

### 2026-07-05 - Step 3

- Completed: Added the agentic update artifact layout and rollback manifest design. The artifact contract documents the durable run root under `PRIVATE/agentic-update-pipeline/runs/<run_id>/`, fixed subdirectories, standard filenames for source packs, parser outputs, proposals, diffs, validation reports, screenshots, secret-scan reports, apply manifests, rollback manifests, summaries, and event logs. The helper functions validate run ids, enforce run-relative artifact paths, generate layout metadata, create directories with mkdir-only semantics, preserve existing evidence, and validate rollback manifests for router config, metadata sources, generated catalog locks, changed source files, UI changes, and Codex binary locator state.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/artifacts.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_artifacts.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_artifacts tests.test_agentic_update_contract` from `apps/astrabridge-sidecar` and passed 13 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\__init__.py astrabridge_sidecar\agentic_updates\contracts.py astrabridge_sidecar\agentic_updates\artifacts.py tests\test_agentic_update_artifacts.py tests\test_agentic_update_contract.py`. Checked touched files for trailing whitespace/conflict markers. Ran a focused secret-like scan over the touched code/test files; matches were only synthetic rejection fixtures in `test_agentic_update_contract.py`.
- Blockers: None.
- Next step: Step 4, Provider Source Registry Hardening.

### 2026-07-05 - Step 2

- Completed: Added the agentic update run contract and proposal schema helpers. The new contract normalizes user scope, version policy, target version, provider/model filters, apply mode, approval policy, and explicit authorization flags. It rejects unsupported scopes, missing pinned target versions, unsafe provider-call/install/code-change combinations, forbidden secret-bearing fields, desktop key paths, inline media data, secret-like strings, and raw external request/response payload fields. The proposal template and validator cover discovery result, diff, validation result, approval state, apply manifest, and rollback manifest, and support fixture-only validation without network or provider keys.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/contracts.py`, `apps/astrabridge-sidecar/tests/test_agentic_update_contract.py`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_contract` from `apps/astrabridge-sidecar` and passed 7 tests. Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\agentic_updates\__init__.py astrabridge_sidecar\agentic_updates\contracts.py tests\test_agentic_update_contract.py`. Checked touched files for trailing whitespace/conflict markers. Ran a focused secret-like scan over the touched code/test files; matches were only synthetic rejection fixtures in the unit test.
- Blockers: None.
- Next step: Step 3, Artifact Layout And Rollback Manifest Design.

### 2026-07-05 - Step 1

- Completed: Produced the current-source baseline inventory for the agentic update pipeline. The report maps the existing metadata refresh/catalog generation surfaces, standalone web lane, LLM health checks, capability runtime and smoke, provider compatibility smoke, provider/model compatibility matrix, Codex kernel probe/smoke/matrix gate, automation scheduler/runner/spec safety, desktop UI/API surfaces, existing metadata skill, tests, reusable artifact roots, runbooks, and the concrete missing updater features. The conclusion is that AstraBridge already has the primitive update and validation surfaces, but still needs the orchestration layer: normalized run contract, proposal schema, source packs, parser outputs, diff/risk engine, rollback manifests, update APIs, update UI, and automation template.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step1-baseline-inventory-20260705.md`, `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Re-read the active plan and durable handoff skill; inspected current source with `rg` across sidecar APIs, metadata service, generated catalog, web lane, provider compatibility smoke, capability smoke/runtime, LLM health, Codex kernel probe/smoke/matrix gate, automations, desktop API/UI, tests, scripts, and docs; confirmed the Step 1 report satisfies the acceptance criteria and records no code or product configuration change.
- Blockers: None.
- Next step: Step 2, Update Run Contract And Schema.

### 2026-07-05 - Step 0

- Completed: Created this durable execution plan for implementing a controlled agentic update pipeline as a skill-backed, script-backed, sidecar/app-integrated workflow. The plan preserves the user's product direction: users choose update scope and version policy; the updater defaults to proposal-only; provider calls, installs, code changes, promotion, and external writeback require explicit authorization; and every apply path must be verifiable and rollbackable.
- Files changed: `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- Validation: Read the durable handoff plan skill and its template, then adapted it into a 20-step implementation plan with per-step acceptance criteria, safety constraints, and an unambiguous next entry point.
- Blockers: None.
- Next step: Step 1, Baseline Inventory And Existing Surface Map.
