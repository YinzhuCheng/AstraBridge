# AstraBridge Project Log

## 2026-06-23

### Request

Start a repository normalization pass driven by `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`, with one numbered step completed per turn.

### Changes Completed So Far

- Removed obsolete plan file `PLAN/30_NEAR_TERM_PRODUCT_FOCUS_AND_NON_TRIVIAL_PRIORITIES.md`.
- Added active execution plan `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`.
- Completed plan step `1.1` by establishing the normalization baseline:
  - recorded current worktree scope
  - verified desktop `npm run test`
  - verified desktop `npm run build`
- Completed plan step `1.2` by updating `AGENTS.md`:
  - removed references to deleted `PLAN/30`
  - aligned repository rules with `.abproj` / `.astrabridge/`
  - required one numbered active-plan step per execution turn
- Completed plan step `1.3` by creating repository memory entry points:
  - `docs/PROJECT_SUMMARY.md`
  - `docs/PROJECT_LOG.md`
  - `docs/ASSET_SOURCES.md`
  - updated `README.md` links to current memory and active plan entry points

### Current Validated Baseline

- Desktop tests: passed
- Desktop build: passed

Validation command set used during the normalization pass:

- `cd D:\AstraBridge\apps\astrabridge-desktop`
- `cmd /c npm run test`
- `cmd /c npm run build`

### Historical Note

- This entry records the start of the normalization pass only.
- Later step completions are tracked in `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`.

### Artifacts / Sources Added

- Added repository memory files only.
- No new external visual assets were added.
- Demo screenshots and validation artifacts remain under `PRIVATE/**` and are intentionally not tracked here.

## 2026-06-27

### Request

Audit repository documentation, remove outdated current-state guidance, align docs with the latest AstraBridge implementation, and archive redundant legacy code/interfaces so future agents do not treat them as active product facts.

### Changes Completed

- Updated current-entry documentation so repository normalization is described as a completed record, not the active source of truth:
  - `AGENTS.md`
  - `README.md`
  - `docs/PROJECT_SUMMARY.md`
  - `docs/HANDOFF.md`
- Updated `docs/ARCHITECTURE.md` to document the current user mental model:
  - visible navigation is `Project -> Task`
  - provider threads, lanes, Codex kernel thread ids, and handoff routes are runtime internals
  - task-level composite conversation is the user-visible conversation source
- Rewrote `docs/LEGACY_CLEANUP_AUDIT.md` around current classifications:
  - `guardrail`
  - `historical-evidence`
  - `compatibility-shim`
  - `current`
  - `cleanup-candidate`
- Added `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md` as the canonical archive for legacy compatibility shims.
- Moved web MCP implementation ownership to the current AstraBridge module:
  - current implementation: `apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_web_mcp_server.py`
  - legacy shim: `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_mcp_server.py`
  - current service: `apps/astrabridge-sidecar/astrabridge_sidecar/web_tool_service.py`
  - legacy shim: `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_service.py`
- Updated web-lane tests to import and patch the canonical AstraBridge web MCP module.

### Follow-Up Notes

- Preserved historical plans and completion records instead of rewriting them.
- `PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md` and its companion plan still contain mojibake text from earlier encoding damage; fix those as a separate targeted documentation cleanup to avoid corrupting preserved plan progress.
- `project-memory-governance` referenced `references/logging_and_artifacts.md`, but that reference file was not present in the skill directory during this pass.

### Artifacts / Sources Added

- Added documentation only under `docs/archive/`.
- No external assets were added.
- No plaintext keys, provider tokens, cookies, or authorization headers were read or persisted.

## 2026-06-27

### Request

Deepen the repository documentation and structure cleanup by repairing mojibake, reducing misleading legacy code/test names, and keeping current docs aligned with the latest implementation.

### Changes Completed

- Rewrote `PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md` from an unreadable mojibake-heavy plan into a concise readable 24/24 completion record.
- Rewrote `PLAN/FIVE_CAPABILITY_REAL_SCENARIO_EXECUTION_PLAN.md` as a readable superseded-plan note pointing to the completed 24-step dogfood record.
- Preserved the key dogfood evidence paths, final status, residual automation failure, and verification summary instead of deleting or hiding failed evidence.
- Renamed internal CSS keyframes from legacy `lcr-*` names to `astrabridge-*`.
- Renamed non-negative test fixture strings and test method names that still carried legacy `lcr` wording:
  - generated asset fixture filenames now use `*_astrabridge.png`
  - test Git identity now uses `astrabridge@example.invalid` / `AstraBridge Test`
  - WSL path rewrite fixture now uses an AstraBridge app-data path
  - affected test method names now use `managed`, `astrabridge`, or `legacy` wording
- Documented the remaining `lcr minimal visual mode:` thread-title prefix as parser-only compatibility in `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md`.
- Updated `docs/LEGACY_CLEANUP_AUDIT.md` to reflect the mojibake repair, CSS rename, and remaining compatibility boundary.

### Verification

- Mojibake scan over README, AGENTS, docs, PLAN, sidecar code/tests, and desktop src now only matches tests that explicitly assert mojibake is absent.
- Legacy active-code scan now leaves only `.lcr` guardrail checks and the documented `lcr minimal visual mode:` compatibility prefix.
- Targeted sidecar tests passed:
  - checkpoint save/load
  - managed asset pruning
  - WSL path rewrite
  - WSL AstraBridge-managed launch
  - isolation audit legacy-boundary reporting
- Frontend tests passed:
  - `src/features/i18n/catalog.test.ts`
  - `src/features/dogfood/DogfoodLedgerSummary.test.tsx`
- `npm.cmd run build` passed with only the existing Vite chunk-size warning.
- `git diff --check` passed for touched files, aside from normal Windows CRLF conversion warnings.

### Follow-Up Notes

- The remaining `.lcr` mentions in active source are intentional guardrails or compatibility handling, not current product paths.
- The completed dogfood record remains `partial` because the automation scenario still preserves a real `codex exec` failure around reasoning effort `max`.

### Artifacts / Sources Added

- No external assets were added.
- No `PRIVATE/**` evidence or runtime artifacts were deleted.
- No plaintext keys, provider tokens, cookies, or authorization headers were read or persisted.

## 2026-06-27

### Request

Implement a detailed repository-governance modernization plan so the repository has executable hygiene checks, clearer documentation entry points, and stronger handoff rules for future agents.

### Changes Completed

- Added repository governance documentation:
  - `docs/REPO_GOVERNANCE.md`
  - `docs/VERIFICATION_MATRIX.md`
  - `docs/OWNERSHIP_BOUNDARIES.md`
  - `references/logging_and_artifacts.md`
- Added local governance tooling:
  - `scripts/repo_governance_check.py`
  - `scripts/run_local_gate.py`
  - `apps/astrabridge-sidecar/tests/test_repo_governance_check.py`
- Updated current repository entry points in `README.md` and `docs/PROJECT_SUMMARY.md`.
- Updated `docs/ASSET_SOURCES.md` and `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md` with governance and artifact-preservation links.
- Repaired residual brand/product mojibake in `docs/BRAND.md` and `docs/PRODUCT_BRIEF.md`.
- Tightened active docs around official OpenAI account-login wording so legacy/auth guardrails are unambiguous.

### Verification

- `python -m py_compile scripts/repo_governance_check.py scripts/run_local_gate.py apps/astrabridge-sidecar/tests/test_repo_governance_check.py` passed.
- `python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_repo_governance_check.py` passed.
- `python scripts/run_local_gate.py --quick` passed with `0` errors and `0` warnings.
- `cmd /c npm run build` in `apps/astrabridge-desktop` passed with only the existing Vite chunk-size warning.
- Residual mojibake search now only reports explicit negative-test/governance marker fixtures.

### Follow-Up Notes

- The repository still has many unrelated existing worktree changes from product/UI/sidecar work; this governance pass did not revert them.
- The new full local gate is available as `python scripts/run_local_gate.py --full`, but this round verified the quick gate plus desktop build.

### Artifacts / Sources Added

- Added governance docs and local validation scripts only.
- No external visual assets were added.
- No `PRIVATE/**` evidence or runtime artifacts were deleted.
- No plaintext keys, provider tokens, cookies, or authorization headers were read or persisted.

## 2026-06-27

### Request

Normalize AstraBridge product semantics around project, task, conversation view, and thread/lane terminology. Keep `对话框` as the composer/input-control name, but stop using session/conversation/thread as user-visible task synonyms.

### Changes Completed

- Documented the current semantic model in `PLAN/SIDEBAR_PROJECT_TASK_SEMANTICS.md`:
  - user navigation is `Project -> Task`
  - a task owns internal execution lanes backed by runtime `thread_id` values
  - Codex `new thread` maps to AstraBridge `new task`
  - Codex `fork/branch thread` maps to AstraBridge `branch task`
- Updated active docs and runbooks to use task/execution-lane wording instead of user-visible thread/session wording.
- Updated desktop UI copy so the visible task work unit now appears as `任务`, `新任务`, `项目与任务`, and `创建分支任务`.
- Kept auth/session-key copy such as anonymous session and session key unchanged because it refers to login/key lifetime, not the task data model.
- Fixed runtime activity Chinese labels and web/multimodal evidence previews while validating the updated activity surface.

### Verification

- `cmd /c npm test -- src/features/runtime/taskSummary.test.ts src/features/runtime/threadRendering.test.ts src/features/i18n/catalog.test.ts` passed.
- `cmd /c npm run build` in `apps/astrabridge-desktop` passed with only the existing Vite chunk-size warning.
- `python scripts/repo_governance_check.py --repo .` passed with `0` errors and `0` warnings.
- In-app browser screenshot QA confirmed the visible UI shows `新任务`, `项目与任务`, center-pane `任务`, and `创建分支任务`.

### Follow-Up Notes

- Internal code and API fields still use `thread_id`, `active_provider_thread_id`, generated Codex protocol names, and related runtime identifiers by design.
- Future UI copy should call provider/runtime switches `执行线路` or `lane`, not sidebar threads.

### Artifacts / Sources Added

- No external assets were added.
- No `PRIVATE/**` evidence or runtime artifacts were deleted.
- No plaintext keys, provider tokens, cookies, or authorization headers were read or persisted.

## 2026-07-10

### Request

Continue the second-phase standardization/UI/live-dogfood plan by completing Step 2: establish one canonical, machine-checkable status registry for current documentation and all execution plans, align the main entry documents, and preserve completed or superseded history.

### Changes Completed

- Added `docs/DOCUMENT_REGISTRY.json` with 101 classified entries covering `AGENTS.md`, `README.md`, every Markdown file under `docs/`, every execution/reference file under `PLAN/`, and the registry itself.
- Added `docs/DOCUMENT_REGISTRY.md` as the human-readable navigation layer, including precedence, taxonomy, active execution conditions, completed families, superseded families, archive behavior, and maintenance rules.
- Established one default active execution queue: `PLAN/ASTRABRIDGE_STANDARDIZATION_UI_LIVE_DOGFOOD_EXECUTION_PLAN.md`.
- Kept `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` as a non-conflicting conditional active queue that activates only when the user explicitly asks for capability-runtime implementation.
- Classified 19 stale or duplicate queues as `superseded` in the registry without modifying their historical progress records.
- Aligned `README.md`, `docs/PROJECT_SUMMARY.md`, `docs/HANDOFF.md`, and `docs/REPO_GOVERNANCE.md` on the registry, current plan, conditional capability-runtime rule, and current 2026-07-10 validation baseline.
- Repaired only the two known mojibake lines in `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md` that blocked the Step 2 governance gate; execution meaning and evidence paths were preserved.

### Verification

- Registry coverage: 101 expected / 101 present, with zero missing, extra, duplicate, missing-field, unknown-status, missing-target, or invalid superseded-replacement entries.
- Markdown link check: 70 absolute links across the five current entry documents, zero missing targets.
- `python scripts/run_local_gate.py --quick` passed with zero governance errors/warnings and zero app-hardening secret-scan errors/warnings; 13 focused tests passed.
- Validation evidence: `PRIVATE/app-standardization-ui-dogfood/docs-api/step2-document-registry-validation.json` and `.md`.

### Follow-Up Notes

- Step 3 owns broader active-document normalization, remaining mojibake/old-path cleanup, and archive placement. Step 2 did not move or delete historical plans.
- Current desktop test failures from the Step 1 baseline remain unresolved and are not hidden by the green documentation/governance gate.

### Artifacts / Sources Added

- Added the two registry files under `docs/` and two validation reports under `PRIVATE/app-standardization-ui-dogfood/docs-api/`.
- No external visual asset was added or changed, so `docs/ASSET_SOURCES.md` required no update.
- No private evidence, logs, screenshots, or raw experiment artifacts were deleted.

## 2026-07-10

### Request

Continue the active second-phase plan by completing Step 3: normalize active/reference documentation, prevent stale guidance from becoming an execution entry, preserve historical evidence, and enforce the boundary automatically.

### Changes Completed

- Audited all 56 registry-selected active/reference entries. No mojibake remains in current guidance, and every retired project/login marker is an explicit prohibition, negative check, compatibility boundary, or historical note.
- Reclassified three stale gap reports as completed snapshots and added maintained replacement banners without moving or deleting their evidence:
  - `PLAN/CAPABILITY_UI_SURFACE_GAP_REPORT.md`
  - `PLAN/MULTIMODAL_CAPABILITY_SURFACE_DRIFT_REPORT.md`
  - `PLAN/PLUGIN_SKILL_SURFACE_GAP_REPORT.md`
- Extended `scripts/repo_governance_check.py` with canonical registry validation, inventory coverage, required-field/status checks, replacement validation, active-plan consistency, active/reference local-link checks, and registry-aware mojibake/retired-path handling.
- Added four governance regression tests and updated the registry, governance guide, verification matrix, project summary, and durable execution plan.
- Preserved completed/superseded corruption as informational audit evidence so history remains reproducible but cannot act as current guidance.

### Verification

- Registry coverage remains 101/101; status counts are 14 active, 25 complete, 42 reference, 19 superseded, and 1 archived.
- Current guidance contains 55 Markdown files with 107 checked links and zero missing local targets.
- Active/reference mojibake findings: 0. Active/reference retired-path findings without guardrail/history context: 0.
- Python compilation passed; governance tests passed 11/11.
- `python scripts/run_local_gate.py --quick` passed with zero governance errors/warnings, zero secret-scan errors/warnings, and 17 focused tests passed.
- Validation evidence is under `PRIVATE/app-standardization-ui-dogfood/docs-api/step3-*`.

### Follow-Up Notes

- The next execution entry is Step 4, which owns the current/legacy interface registry. Step 3 did not delete endpoints, compatibility shims, or UI surfaces.
- The Step 1 desktop baseline remains 296 passing / 4 failing tests; documentation gates passing does not resolve those product-test failures.

### Artifacts / Sources Added

- Added Step 3 machine-readable and human-readable validation reports plus raw governance output under `PRIVATE/app-standardization-ui-dogfood/docs-api/`.
- No external assets were added, so `docs/ASSET_SOURCES.md` was unchanged.
- No private evidence, logs, screenshots, raw experiment artifacts, credentials, or provider records were deleted.
- No real provider call was made; provider token usage was 0.

## 2026-07-10

### Request

Continue the active second-phase plan by completing Step 4: inventory current and legacy APIs, SSE events, runtime payloads, provider metadata, CLI/launcher surfaces, and compatibility shims without deleting interfaces from name-based assumptions.

### Changes Completed

- Added `scripts/interface_registry_audit.py`, a read-only AST and consumer-search auditor that generates and validates a private machine-readable interface registry.
- Added `apps/astrabridge-sidecar/tests/test_interface_registry_audit.py` with four focused checks for route coverage, classification, non-HTTP families, and cleanup safety.
- Added `docs/INTERFACE_GOVERNANCE.md` with status semantics, current counts, known shims, 12 explicit unknown routes, and Step 5 change rules.
- Generated `PRIVATE/app-standardization-ui-dogfood/docs-api/step4-interface-registry.json` with 251 interfaces across HTTP, SSE, payload, provider metadata, MCP, CLI/launcher, and shim families.
- Updated document registry, project summary, handoff, repository governance, project log, and the durable execution plan.

### Verification

- Interface status counts: 219 current, 14 shim-only, 12 unknown, 3 deprecated, 2 test-only, and 1 historical.
- Non-test Desktop HTTP literals: 179; paths without a server definition: 0.
- Cleanup candidates: 32; candidates without definition or consumer-search evidence: 0; candidates marked safe to remove: 0.
- Interface audit tests passed 4/4; generator completed in about 4.3 seconds.
- `python scripts/run_local_gate.py --quick` passed with zero governance errors/warnings, zero secret-scan errors/warnings, and 17 quick-gate tests passed.
- The app-hardening artifact-root scanner was incompatible with the `docs-api/` evidence layout and preserved a failed report; the supported path-focused scanner checked four Step 4 JSON/Markdown deliverables with zero findings.
- Validation evidence: `PRIVATE/app-standardization-ui-dogfood/docs-api/step4-interface-registry-validation.json` and `.md`.

### Follow-Up Notes

- Step 5 must revalidate every cleanup candidate. In particular, zero repository string matches do not prove that dynamic or external callers are absent.
- The 12 unknown routes cannot move directly to deletion. Each has an owner, definition line, handler symbols, searched scopes, prerequisites, and next investigation in the private registry.
- The Step 1 desktop baseline remains 296 passing / 4 failing tests; this inventory step did not claim product-test closure.

### Artifacts / Sources Added

- Added one public interface-governance document, one audit script, one focused test file, and three private Step 4 reports/registries.
- No external visual assets were added, so `docs/ASSET_SOURCES.md` was unchanged.
- No existing interfaces, private evidence, logs, screenshots, raw experiment artifacts, or provider records were removed.
- No real provider call was made; provider token usage was 0.

## 2026-07-10

### Request

Continue the active second-phase plan by completing Step 5: safely deprecate or archive only interfaces proved obsolete, retain required compatibility shims, and prevent retired implementation names from returning to current code.

### Changes Completed

- Removed the unused historical inline provider-adapter block from `apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py`.
- Preserved the exact 40,252-character block under `PRIVATE/app-standardization-ui-dogfood/docs-api/step5-router-inline-adapters-before.py` before the source edit.
- Added a runtime-symbol governance rule and focused router absence regression so the five retired adapter classes cannot return to active code outside inventory, tests, or history contexts.
- Updated interface governance, the archived compatibility-shim inventory, the interface audit registry, and the durable execution plan.
- Left all HTTP aliases, official-Codex guardrails, LCR shims, test fixtures, DashScope compatibility normalizers, and 12 unknown interfaces intact.

### Verification

- Router transport registry tests passed 4/4.
- Sidecar provider/router/tool tests passed 21/21.
- Governance tests passed 13/13; interface registry tests passed 5/5.
- Desktop reasoning tests passed 9/9; desktop production build passed with the existing 1092.23 kB chunk warning.
- Quick gate passed with zero governance errors/warnings and zero secret-scan errors/warnings.
- Interface cleanup candidates fell from 32 to 31; all remaining candidates remain `safe_to_remove=false`.
- Focused Step 5 evidence scan found zero findings, including zero bearer/key-pattern matches in the archived source block.

### Follow-Up Notes

- The next execution entry is Step 6, which owns code ownership and contract validation. It must not convert the remaining 12 unknown interfaces into deletion candidates without stronger runtime or UI evidence.
- The Step 1 desktop baseline remains 296 passing / 4 failing tests; this interface cleanup step does not claim those product-test failures are fixed.

### Artifacts / Sources Added

- Added Step 5 before/after interface registries, validation reports, secret scan report, and preserved source block under `PRIVATE/app-standardization-ui-dogfood/docs-api/`.
- No external visual assets were added, so `docs/ASSET_SOURCES.md` was unchanged.
- No provider credentials, Vault state, cookies, authorization headers, or raw provider records were read, stored, or deleted.
- No real provider call was made; provider token usage was 0.

## 2026-07-10

### Request

Continue the active second-phase plan through Step 6, then perform a user-authorized in-app-browser click check using the hosted account without reading any secret source.

### Changes Completed

- Added `scripts/contract_boundary_audit.py` and made it part of the quick local gate.
- Added the canonical ownership and contract-boundary reference, including the permitted task-graph/orchestration bridge and provider transport selection ownership.
- Added three contract-audit tests: current state, provider registry drift, and lowering field drift.
- Registered the new reference document and updated the verification matrix and project summary.

### Verification

- Contract audit passed: 4 provider families, 2 wire fallbacks, 7 persisted task-graph fixtures, and 6 orchestration examples.
- Focused Sidecar tests passed: contract audit 3/3, router transports 4/4, orchestration contract 5/5, compiler 7/7.
- Desktop task-graph UI tests passed 60/60; Desktop typecheck/build passed with the existing 1092.23 kB Vite chunk warning.
- Repository governance passed with zero errors and warnings.

### Directed Click Evidence

- In-app browser was logged in as the hosted `user` account. The click path entered Task Graph, selected a node, opened/closed the node editor, opened/closed the template selector, ran Dry-run, opened its diagnostics, returned to chat, and submitted one minimal Qwen request.
- Dry-run ended `blocked`: the selected graph had no configured profile matching `qwen / qwen3-coder-plus`, and its entry node lacked a declared incoming edge. The diagnostics dialog exposed both reasons, while the canvas only exposed `blocked` state.
- The template selector has substantial unused right-side space; node configuration still uses a tall stack of short-value fields; the live request remained in a waiting state after the observation window with no visible cancellation action or final error. On the final read-only check, the composer had cleared but the required exact reply was absent; the UI had switched to Plan mode and showed an empty plan. Browser logs also showed repeated React duplicate-key warnings for `item-1` and `item-2` in `AppShell`.
- Screenshots are preserved at `PRIVATE/app-standardization-ui-dogfood/click-qa/20260710-live-account/`. This directed check is early Step 7 evidence only and does not mark the full UI baseline complete.

### Artifacts / Sources Added

- Added `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, the Step 6 audit report and validation note, and six private click-QA screenshots.
- No external visual asset was added, and no existing private evidence or provider record was deleted.
- The contract audit made no provider call. The separate user-authorized chat request may have consumed provider tokens, but no usage result was returned during the observation window; no secret was read or written.

## 2026-07-12

### Request

Repair AstraBridge isolation before returning to the official Codex sidebar issue: prevent AstraBridge from sharing or fighting official Codex state, move AstraBridge runtime/cache storage to D:, reclaim leaked sidecar trees, and preserve existing runtime artifacts.

### Changes Completed

- Added `ASTRABRIDGE_RUNTIME_ROOT` and made `D:\AstraBridgeRuntime` the Windows default when D: is available; explicit `ASTRABRIDGE_APPDATA` test/demo roots remain self-contained.
- Moved the fallback AstraBridge Codex home below the managed runtime root.
- Added fail-closed overlap checks for all AstraBridge app-data, runtime, and Codex-home roots against the conventional official `%USERPROFILE%\.codex` home.
- Updated the desktop launcher to remove inherited `CODEX_HOME` and `ASTRABRIDGE_CODEX_HOME`, reclaim a stale AstraBridge `--serve` tree on its managed port before launch, and terminate the complete managed sidecar process tree on exit without disturbing deliberate development sidecars on other ports.
- Added a dry-run-by-default migration script and focused Python/Rust isolation tests.
- Stopped 34 stale AstraBridge sidecar roots, copied and twice verified all runtime files, replaced the two legacy C: directories with compatibility junctions, and preserved a redacted validation report.

### Verification

- Runtime copy: 37,146 files / 487,237,836 bytes, 0 missing, 0 size mismatches.
- Legacy default Codex home copy: 69 files / 9,217,778 bytes, 0 missing, 0 size mismatches.
- Final D: inventory: 37,215 files / 496,455,614 bytes.
- `%APPDATA%\AstraBridge\runtime` and `%LOCALAPPDATA%\AstraBridge\cx` both read back as directory reparse points targeting D:.
- Matching stale sidecars after migration: 0.
- Windows Sidecar regressions passed 7/7; post-migration storage-isolation tests passed 4/4; Rust launcher isolation test passed 1/1; Rust format check passed.
- App-hardening secret scan checked 179 text files with 0 errors and 0 warnings.

### Follow-Up Notes

- The official Codex App was not restarted and its SQLite state was not edited. The next user decision is a controlled official-App restart under the restored Windows-native smart environment, followed by a read-only sidebar/catalog check if older tasks remain absent.
- Source changes still need the normal AstraBridge desktop packaging/deployment path before a newly installed binary contains the launcher lifecycle fix. The compatibility junctions protect current/older binaries from recreating the large C: runtime in the meantime.

### Artifacts / Sources Added

- Added `PRIVATE/app-hardening/reports/astrabridge-runtime-migration-20260712.md` with secret-safe migration and verification evidence.
- No external asset was added, so `docs/ASSET_SOURCES.md` was unchanged.
- No official Codex database, task record, config, provider secret, cookie, or authorization header was modified or persisted.

## 2026-07-17

### Request

Audit the next stability phase for AstraBridge's multi-provider agent positioning,
standards-based A2A interoperability, automatic upgrades, GUI orchestration, and
code-authored orchestration, then land a durable multi-round handoff plan.

### Changes Completed

- Added `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`
  as a 24-step durable follow-on queue with one active work unit, per-step
  acceptance criteria, adjustment rules, evidence-review triggers, and an
  append-only progress log.
- Preserved the completed 22-step
  `PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md` as the
  implementation baseline rather than restarting its completed work.
- Activated the new plan in the machine-readable and human document registries;
  updated README, handoff, project summary, repository governance, interface
  governance, code ownership, and the conditional capability-runtime delegation
  so they identify one current execution source.
- Updated `scripts/contract_boundary_audit.py` to validate both the active
  follow-on plan and the completed baseline plan.
- Set the next execution entry to Step 1: make promotion gates non-skippable and
  add canonical PR/nightly/release CI entry points.

### Verification

- `python scripts/run_local_gate.py --quick` passed in 34.3 seconds.
- Repository governance: 0 errors, 0 warnings, 1,268 text files scanned.
- Secret scan: 0 errors, 0 warnings, 181 text files scanned.
- Contract boundary audit: 18/18 checks passed and now resolves the active and
  baseline stability plans separately.
- Focused governance and secret-scan unit suites passed 14/14 and 6/6.
- The document registry contains 107 entries: 14 active, 26 complete, 46
  reference, 20 superseded, and 1 archived.

### Follow-Up Notes

- Future general stability work starts at Step 1 of the new plan and completes
  exactly one full numbered step per execution round.
- `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` remains conditionally active
  only for explicit capability-runtime requests and must not create parallel
  MCP, envelope, scheduler, A2A, executor, or updater contracts.
- GitHub CLI authentication remains user-deferred. It is not required to author
  and locally validate CI workflow files in Step 1.

### Artifacts / Sources Added

- Added one tracked execution-plan document and updated current governance and
  project-memory documents.
- No external assets, provider calls, credentials, raw provider records, or
  private experiment artifacts were added or removed.

## 2026-07-17

### Request

Continue the active product-stability plan by completing Step 1: make promotion
gates non-skippable and add canonical CI entry points.

### Changes Completed

- Added `apps/astrabridge-sidecar/astrabridge_sidecar/promotion_gate.py` as the
  fail-closed promotion owner and `scripts/run_promotion_gate.py` as the only
  public wrapper for PR/nightly/release promotion verdicts.
- Upgraded `scripts/run_local_gate.py` to emit machine-readable summary/report
  artifacts without creating a second suite list.
- Added `.github/workflows/pr-promotion-gate.yml`,
  `.github/workflows/nightly-promotion-gate.yml`, and
  `.github/workflows/release-promotion-gate.yml`; each installs from repository
  lockfiles and invokes the canonical promotion wrapper instead of redefining
  checks inline.
- Extended `scripts/contract_boundary_audit.py` and code-ownership/governance
  docs so the promotion gate and workflow entry points are now audited
  contracts.
- Added focused promotion-gate tests for machine-readable local-gate output,
  fail-closed unknown status / commit mismatch behavior, and forged or
  incomplete summary rejection.

### Verification

- `python -m py_compile scripts/run_local_gate.py scripts/run_promotion_gate.py apps/astrabridge-sidecar/astrabridge_sidecar/promotion_gate.py scripts/contract_boundary_audit.py` passed.
- `python -m unittest apps.astrabridge-sidecar.tests.test_promotion_gate` passed 3/3.
- `python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_contract_boundary_audit.py` passed 3/3.
- `python scripts/contract_boundary_audit.py` passed 19/19 checks.
- `python scripts/run_local_gate.py --quick` passed with 0 governance errors, 0 governance warnings, 0 secret-scan errors, and 0 secret-scan warnings.
- A real `python scripts/run_promotion_gate.py --mode pr --expected-commit <HEAD>` run failed closed because the current worktree is dirty, preserving redacted summary/report/manifest evidence under `PRIVATE/promotion-gates/local-pr-dirty-check-2/`.
- `git diff --check` reported only line-ending warnings and no content-format failures.

### Follow-Up Notes

- The active execution plan now advances to Step 2: establish one release
  identity and clean packaging staging.
- The local promotion gate intentionally refuses promotable status in a dirty
  worktree; CI workflows are expected to run it from clean checkouts.
- The local environment reports Python 3.11.15, Node v22.23.0, npm 10.9.8, and
  Cargo 1.96.0 in the preserved dirty-tree promotion evidence.

### Artifacts / Sources Added

- Added one new Sidecar promotion-gate owner module, one wrapper script, three
  GitHub workflow files, one focused test file, and preserved local promotion
  evidence under `PRIVATE/promotion-gates/local-pr-dirty-check-2/`.
- No external assets, provider calls, credentials, raw provider records, or
  private experiment artifacts were deleted.

## 2026-07-17

### Request

Continue the active product-stability plan by completing Step 2: establish one
release identity and a clean packaging staging contract for Desktop, Sidecar,
updater metadata, and release-readiness verification.

### Changes Completed

- Added one canonical tracked release manifest:
  `release/astrabridge-release-identity.json`.
- Added `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py` as
  the release-identity/readiness owner for version binding checks, staging,
  inventory/hash generation, updater-manifest emission, SBOM input, provenance,
  and deterministic stage comparison.
- Added `scripts/run_release_readiness_gate.py` as the canonical release
  readiness wrapper and `apps/astrabridge-sidecar/tests/test_release_identity.py`
  as focused coverage for drift detection and deterministic staging.
- Switched current Sidecar/MCP/runtime version consumers to the canonical
  release identity rather than duplicating literal version strings.
- Extended `scripts/contract_boundary_audit.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, `docs/VERIFICATION_MATRIX.md`,
  `docs/RELEASE_CHECKLIST.md`, and `README.md` so the release-identity and
  clean-staging contract is now enforced and documented.

### Verification

- `python -m py_compile apps\astrabridge-sidecar\astrabridge_sidecar\release_identity.py scripts\run_release_readiness_gate.py apps\astrabridge-sidecar\astrabridge_sidecar\__init__.py apps\astrabridge-sidecar\astrabridge_sidecar\app_server_client.py apps\astrabridge-sidecar\astrabridge_sidecar\mcp_broker_service.py apps\astrabridge-sidecar\astrabridge_sidecar\server.py` passed.
- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_release_identity.py` passed 3/3.
- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_contract_boundary_audit.py` passed 3/3.
- `python scripts\contract_boundary_audit.py` passed 20/20 checks.
- `python scripts\run_release_readiness_gate.py --artifact-root PRIVATE\release-readiness --run-id local-step2-readiness` passed with zero binding mismatches and matching stage inventories/content hashes between Stage A and Stage B.
- `python scripts\run_local_gate.py --quick` passed with 0 governance errors, 0 governance warnings, 0 secret-scan errors, and 0 secret-scan warnings.
- `git diff --check` reported only line-ending warnings and no content-format failures.

### Follow-Up Notes

- Forward execution now starts at Step 3 of
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`:
  enforce the canonical protocol at every durable write boundary.
- The preserved readiness evidence under
  `PRIVATE/release-readiness/local-step2-readiness/` is the current baseline for
  release identity, clean staging, and deterministic package inventory.
- GitHub CLI authentication remains intentionally deferred and is unrelated to
  local release-readiness verification.

### Artifacts / Sources Added

- Added one tracked release manifest, one new Sidecar owner module, one wrapper
  script, one focused test file, and preserved Step 2 release-readiness
  artifacts under `PRIVATE/release-readiness/local-step2-readiness/`.
- No external assets, provider calls, credentials, raw provider records, or
  private experiment artifacts were deleted.

## 2026-07-17

### Request

Continue the active product-stability plan by completing Step 3: enforce the
canonical protocol at every durable write boundary so runtime and persistence
cannot drift from the schema.

### Changes Completed

- Added `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/persistence.py`
  as the canonical protocol-persistence owner for run projections, events,
  envelopes, content parts, and artifact references.
- Updated the durable run store to canonicalize and validate protocol objects at
  the innermost persistence boundary before SQLite writes.
- Extended `scripts/generate_protocol_types.py` and regenerated the Python and
  TypeScript protocol bindings so runtime vocabularies are schema-derived
  instead of duplicated literals.
- Replaced schema-external persisted runtime event names with canonical schema
  events and added actionable compatibility failures for unsupported
  run-projection schema versions.
- Expanded the shared golden protocol fixture corpus and added focused
  persistence coverage so Python, TypeScript, migration, and durable-store paths
  reuse the same valid/invalid cases.
- Extended `scripts/contract_boundary_audit.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and
  `docs/VERIFICATION_MATRIX.md` so the protocol durable-write boundary is now an
  explicit audited contract.

### Verification

- `python scripts\generate_protocol_types.py --write` passed.
- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_protocol_persistence.py` passed 5/5.
- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_protocol_schema.py` passed 9/9.
- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_durable_run_store.py` passed 9/9.
- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_contract_boundary_audit.py` passed 3/3.
- `npm.cmd test -- src/astrabridge_protocol/generated/v1.test.ts` passed 4/4.
- `python scripts\contract_boundary_audit.py` passed 21/21 checks with
  canonical protocol fixture counts 10 valid / 7 invalid.
- `python scripts\run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings.
- `git diff --check` reported only CRLF conversion warnings and no
  content-format failures.

### Follow-Up Notes

- The next execution entry is Step 4, which owns durable delivery identity,
  ordering, expiry, replay handling, and cancellation convergence.
- Step 3 preserved current and documented N-1 run-projection read behavior by
  upgrading supported legacy payloads at the persistence boundary and failing
  unsupported schema versions with an actionable error instead of silent drift.

### Artifacts / Sources Added

- Added one new Sidecar protocol-persistence owner module and one focused test
  file; updated generated protocol bindings, shared fixtures, and durable-store
  tests in place.
- No external assets, provider calls, credentials, raw provider records, or
  private experiment artifacts were deleted.

## 2026-07-17

### Request

Continue the active product-stability plan by completing Step 4: separate
delivery identity from processing identity, enforce replay/expiry/audience
policy before dispatch, and make cancellation converge under late-result races.

### Changes Completed

- Extended `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/persistence.py`
  so canonical agent envelopes now derive a normalized delivery contract from
  message identity, delivery identity, target audience, sequence, not-before,
  deadline, TTL, and replay-window policy.
- Updated the durable run store so agent envelopes enforce immutable
  `message_id` and delivery-id identity, per-edge sequence ordering, and
  processing-key inbox admission. Duplicate inbox/outbox ids with the same
  payload remain idempotent, while conflicting payload reuse now rejects.
- Updated task-graph handoff construction so delivery sequence is monotonic per
  attempt instead of always `0`, and tightened recipient-lane validation for
  structured handoffs.
- Updated live runtime handoff admission to reject early, expired, replayed,
  and mismatched-audience delivery before provider dispatch by routing
  processing admission through the durable store.
- Updated live cancellation handling so late completed provider turns are
  suppressed after cancellation, do not emit downstream worker output, and
  converge the persisted cancellation record to a resolved terminal state.
- Removed the remaining schema-external live terminal event emission
  `run_needs_review`; live runs now preserve `needs_review` as run status while
  using canonical terminal events.

### Verification

- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_durable_run_store.py` passed 11/11.
- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_graph_scheduler.py` passed 20/20.
- `python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_protocol_persistence.py` passed 5/5.
- `python scripts\contract_boundary_audit.py` passed 21/21 checks.
- `python scripts\run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings.
- `git diff --check` reported only CRLF conversion warnings and no
  content-format failures.

### Follow-Up Notes

- The next execution entry is Step 6, which owns the provider adapter ABI and
  verified capability snapshots.
- Step 4 now makes live duplicate suppression and cancellation race handling a
  durable-store concern rather than an in-memory best effort.

### Artifacts / Sources Added

- No external assets were added.
- No private evidence, logs, caches, provider records, credentials, or
  preserved validation outputs were deleted.

### 2026-07-17 - Step 5 Provider Admission / Backpressure / Retry / Breaker

- Completed Step 5 of `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`.
- Added `apps/astrabridge-sidecar/astrabridge_sidecar/graph_dispatch_control.py`
  to own per-run/provider/model retry budgets plus provider/model
  circuit-breaker state for live graph dispatch.
- Hardened `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
  so live graph parallel groups are structurally normalized into bounded
  batches before provider dispatch, and runtime environment snapshots now
  expose redacted graph-dispatch / breaker status.
- Hardened `apps/astrabridge-sidecar/astrabridge_sidecar/graph_scheduler.py`
  with queue capacity metadata and queued-cancel skip-dispatch handling so a
  cancelled queued run never reaches the provider callback.
- Added Step 5 regression coverage in
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py` for queued
  cancellation, bounded parallel-group dispatch, retry-budget storm
  suppression, and observable circuit-open blocking.
- Validation:
  `python -m unittest tests.test_graph_scheduler` passed 24/24;
  `python -m unittest tests.test_runtime_client_pool` passed 7/7 with
  `ASTRABRIDGE_RUNTIME_ROOT` redirected into a writable local runtime root;
  `python scripts\contract_boundary_audit.py` passed 21/21 checks; `python
  scripts\run_local_gate.py --quick` passed; `git diff --check` reported only
  CRLF conversion warnings.
- Next entry: Step 6, provider adapter ABI plus verified capability snapshots.

### 2026-07-17 - Step 6 Provider Adapter ABI / Verified Capability Snapshots

- Completed Step 6 of `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`.
- Added `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_snapshot.py`
  to own versioned verified capability snapshots, current provider-adapter
  contract fingerprints, snapshot aggregation, and graph-port capability
  projection.
- Updated `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`
  so provider compatibility-matrix evidence produces persisted per-model
  verified capability snapshots and stale adapter/model revisions fail closed
  as `stale` rather than silently reusing old capability claims.
- Updated `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`
  and `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` so
  live multimodal graph admission requires current verified capability
  snapshots and queued/live run policy manifests preserve the approved
  model-capability snapshot.
- Updated `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/base.py`
  with shared structured error classification and cancellation-contract
  reporting, and registered the new shared transport conformance suite in
  `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate.py`.
- Added focused Step 6 regression coverage in
  `apps/astrabridge-sidecar/tests/test_provider_capability_snapshot.py` and
  `apps/astrabridge-sidecar/tests/test_provider_transport_conformance.py`.
- Validation:
  `python -m unittest tests.test_provider_capability_snapshot
  tests.test_provider_transport_conformance tests.test_router_transport_registry
  tests.test_graph_scheduler tests.test_runtime_client_pool
  tests.test_provider_capability_verification_gate` passed 44/44 with
  `ASTRABRIDGE_RUNTIME_ROOT` redirected into a writable local runtime root;
  `python scripts\contract_boundary_audit.py` passed 21/21 checks; `python
  scripts\run_local_gate.py --quick` passed; `git diff --check` reported only
  CRLF conversion warnings.
- Follow-up: Step 7 is now the active entry point and will own cross-provider
  context projection, neutral artifact continuity, and end-to-end handoff
  lineage auditing.
- No external assets were added.
- No private evidence, logs, caches, provider records, credentials, or
  preserved validation outputs were deleted.
