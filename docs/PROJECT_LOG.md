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

## 2026-07-27

### Request

- The user asked to find the enhanced multi-round scripted handoff-plan skill
  and use it to persist AstraBridge's upgrade plan for becoming an open-source
  developer product.

### Changes

- Read and applied the enhanced scripted durable-handoff-plan contract and the
  project-memory governance workflow.
- Added the conditional execution queue
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.
  It keeps the product-stability queue as the default mainline and turns the
  intended positioning into bounded work: public foundation, truthful claims,
  no-key onboarding, flagship coding-agent and GUI/code examples, provider
  authority surface, extension/contribution paths, release evidence, and a
  developer-preview decision.
- Registered the new conditional queue, the completed provider-adaptation
  upgrade handoff, and the existing Codex-core multi-provider execution
  contract in the canonical document registry. Updated the human registry,
  repository governance, and project summary to match the new queue boundary.
- The owner must still select a license before any root `LICENSE` file or
  license-specific public claim can be added. No credentials, provider calls,
  external writes, artifacts, or user changes were removed.

### Validation And Sources

- `python C:\Users\cyz19\.codex\skills\durable-handoff-plan-scripted\scripts\validate_plan_contract.py PLAN\ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md` passed.
- `python scripts\repo_governance_check.py --repo .` passed with 0 errors and
  0 warnings after registry coverage was restored.
- `scripts/recent_context.py` is not present in this repository, so current
  context was verified from `AGENTS.md`, the document registry,
  `docs/PROJECT_SUMMARY.md`, `docs/PROJECT_LOG.md`, the release and security
  guidance, and the completed provider-adaptation records.
- No external sources or assets were introduced.

### Next Entry Point

- Step 1, `OSS-FOUNDATION-01`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`:
  audit the exact public foundation gap and create the license/community
  decision record without selecting a license on the owner's behalf.

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

## 2026-07-27 - Open-Source Productization Step 1

### Request

- Continue the active open-source developer-productization plan and complete
  its next bounded step.

### Changes

- Added `docs/OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md`, which inventories
  the missing public foundation, evaluates `Apache-2.0` and `MPL-2.0`,
  recommends a route without selecting it, and records the owner decisions
  required before a public preview.
- Added transparent pre-preview `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and
  `SECURITY.md` files. They map safe participation and disclosure behavior but
  do not invent a private reporting contact or contribution license.
- Updated `README.md` and the canonical registry/governance surfaces to expose
  the foundation state. The governance checker now deliberately recognizes the
  standard public root documents as registry-controlled documentation.

### Validation And Sources

- `python scripts\repo_governance_check.py --repo .` passed with 0 errors and
  0 warnings.
- The scripted plan validator passed before Step 1. Root inventory confirms
  the three public policy files exist and no root license exists.
- `git diff --check` produced no content-format failure; it reported only
  CRLF conversion warnings from the existing dirty worktree.
- Sources inspected: local repository and Git remote metadata, the existing
  README/security/release/product guidance, the [Apache-2.0 text](https://spdx.org/licenses/Apache-2.0.html), the [MPL-2.0 text](https://www.mozilla.org/en-US/MPL/2.0/), and Mozilla's [MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).
- No external assets, provider calls, credentials, or external writes were
  introduced.

### Unresolved And Next Entry Point

- License choice, copyright-holder confirmation, private security reporting,
  and conduct-enforcement contact remain owner-gated release blockers.
- Next: Step 2, `OSS-POSITION-02`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 2

### Request

- Continue the active plan by completing the evidence-qualified public
  positioning and claim-matrix step.

### Changes

- Added `docs/OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md` with public
  proposition, audiences, exact evidence labels, material claims, owners, and
  next validation gates.
- Rewrote the public README introduction and Product Brief around a
  developer-first, evidence-qualified multi-provider coding-agent story, and
  added the corresponding public-claim boundary to `docs/ARCHITECTURE.md`.
- Registered the new matrix and refreshed the document-registry counts and
  project-summary entry points.

### Validation And Sources

- `python -m unittest tests.test_provider_reference_cohort
  tests.test_agent_orchestration_file_format` passed 9 focused deterministic
  tests; three selected `TaskGraphApiTests` passed for TypeScript fixture round
  trip, supported generated export, and safe unsupported-export blocking.
- `python scripts\repo_governance_check.py --repo .` passed with 0 errors and
  0 warnings. Ports 4181 and 8826 had no listening AstraBridge process before
  or after the focused tests.
- Preserved a secret-free command/result record at
  `PRIVATE/open-source-productization/reports/step2-positioning-evidence-20260727.md`.
- No external assets, provider calls, credentials, or external writes were
  introduced.

### Unresolved And Next Entry Point

- License and private reporting decisions remain release blockers. The no-key
  route remains documented-only until it has clean-user evidence.
- Next: Step 3, `OSS-ONBOARDING-03`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 3

### Request

- Continue the active open-source productization plan by proving a no-key
  first-ten-minutes path rather than performing any provider-backed smoke.

### Changes

- Added `docs/NO_KEY_FIRST_TEN_MINUTES.md`, a Windows PowerShell clean-user
  route that uses `npm.cmd`, redirected application/runtime/Codex roots, the
  standard `4181` Desktop / `8826` sidecar pairing, and one fixture-backed
  beginner project.
- Updated the README, demo runbook, product brief, public claim matrix,
  registry, project summary, and governance inventory so public wording calls
  this deterministic fixture evidence rather than provider compatibility.
- Repaired an onboarding-path UI defect: the task-graph template modal now
  renders through a React portal, so its instantiate action remains clickable
  while the inspector is open.
- Preserved attempted-clone artifacts, screenshots, two 3-worker/22-artifact
  fixture runs, and a secret-free evidence report under `PRIVATE/**`.
- Corrected the sidecar package manifest by moving `jsonschema` to runtime
  dependencies and refreshing `uv.lock`, then created scoped local candidate
  `7737d36c51346ef6126d497aa8d48004448e966e` without staging unrelated dirty
  provider-adaptation work.
- Fast-forwarded the local canonical `codex/near-term-runtime-isolation` branch
  to that verified four-file revision, then added a scoped public-documentation
  transaction at `c8988fef6f1139ac056fadb68e395122ee59254a` without staging
  unrelated provider-adaptation work.

### Validation And Evidence

- The first local-clone browser fixture completed `npm.cmd ci` in 21 seconds;
  browser-driven project creation, template instantiation, and fixture
  execution all completed without a provider route. Its global-Python sidecar
  launch makes it UI/fixture evidence rather than clean-clone package proof.
- A pristine clone installed its declared sidecar dependencies but failed
  `import jsonschema` before server launch. The current-source fresh venv
  imported the sidecar after the manifest repair; focused source-registry and
  catalog tests passed 12/12 and `pip check` passed.
- A fresh clone of the scoped local candidate completed `npm.cmd ci`, 91
  focused task-graph tests, a production build, editable sidecar installation,
  sidecar import, and `pip check`. Its real browser route created a `.abproj`
  project, instantiated the fixture graph, and completed with 3 workers and 22
  artifacts while the UI remained missing-key/review-only. Browser requests and
  listener connections were loopback-only; owned test processes were reaped.
- Browser request-host audit observed only `127.0.0.1`; the UI remained in its
  missing-key/review-only state.
- `npm.cmd run test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  passed 91 tests; `npm.cmd run build` passed with the existing chunk-size
  warning; `python scripts\repo_governance_check.py --repo .` passed with 0
  errors and 0 warnings.
- The quick local gate preserved a non-green result only because the unrelated
  shell-module budget audit reports existing overruns in `runtime_service.py`,
  `task_service.py`, and `App.tsx`; governance, secret scan, and contract
  boundary audit passed first. See
  `PRIVATE/open-source-productization/validation/step3-local-gate-20260727/`.
- A fresh clone of the scoped public-documentation revision repeated the
  `npm.cmd ci`, 91-test, build, editable-install/import, `pip check`, and
  browser fixture checks. It created a `.abproj` project, remained visibly
  missing-key/review-only, and completed `Supervisor / Worker / Synthesizer`
  Fixture Run with 3 workers and 22 artifacts. All recorded browser requests
  were loopback-only; owned test processes were stopped after the run.

### Unresolved And Next Entry Point

- This route does not verify a public release installer, live model behavior,
  tool authority, a provider credential path, coding-route eligibility, or a
  published distribution. It is exact-source deterministic clean-clone
  evidence for `c8988fef6f1139ac056fadb68e395122ee59254a`.
- License, copyright, private reporting, and conduct-contact decisions remain
  owner-gated developer-preview blockers.
- Step 3 is complete. Next: Step 4, `OSS-FLAGSHIP-04`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 4

### Request

- Advance the scripted developer-product plan by turning an existing
  deterministic code-fix/test/review capability into the first inspectable
  flagship coding-agent reference without using a provider credential.

### Changes

- Added a bounded Task-Title Guard scenario, seed project, expected patch,
  deterministic runner, and focused sidecar regression test.
- The runner creates an isolated .abproj project, validates declared local
  route metadata without a provider call, records the approval-gated
  code-change boundary, exports its graph, injects a Plan Fix failure, and
  verifies retry recovery.
- Shortened the runner's internal evidence workspace name after a deep
  Windows evidence path reached the task-graph artifact-path limit.
- Added the public flagship reference guide; linked it from the README,
  project summary, claim matrix, registry, and governance inventory.
- Preserved secret-free deterministic and UI evidence under
  PRIVATE/open-source-productization.

### Validation And Evidence

- The focused runner test passed; the final runner packet recorded zero
  provider calls, dry-run pass, one expected seed failure, a recovered passing
  check, failed fixture injection, and completed retry_failed_nodes recovery.
- Desktop TaskGraphWorkspace passed 91 tests and the production build passed
  with the existing large-chunk warning. The isolated editable sidecar install
  and pip check passed.
- In the Codex in-app browser, a new isolated project instantiated Code Fix /
  Test / Review, stayed visibly missing-key, completed Fixture Run with four
  workers and 28 artifacts, and showed ask plus filesystem_write_gate for
  Apply Code Fix. Browser console errors were empty.
- Repository governance passed with 0 errors and 0 warnings. The scripted
  handoff-plan validator passed before the completion update. Owned local
  Desktop, sidecar, and terminal-browser processes were reaped; listener
  ports 4181, 4182, 8826, and 8827 were clear afterward.

### Unresolved And Next Entry Point

- This reference is deterministic no-provider evidence only. It does not
  establish live provider behavior, coding-route eligibility, autonomous
  write or tool authority, release-installer behavior, or a published
  distribution.
- Existing quick-gate shell-module budget overruns remain outside this step.
- Step 4 is complete. Next: Step 5, OSS-PROVIDER-TRUTH-05, in
  PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md.

## 2026-07-27 - Open-Source Productization Step 5

### Request

- Publish a truthful, developer-readable provider authority surface before any
  provider-backed upgrade or smoke claim.

### Changes

- Added `docs/PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md` with exact Qwen,
  DeepSeek, Kimi K3, and GLM route cards. It separates declared modality,
  advertised context, transport, and normalized reasoning metadata from
  deterministic checks and current route authority.
- Added a focused source-backed regression test that derives the public rows
  from the current catalog/profile and provider-free reference cohort.
- Linked the surface from the public README, project summary, registry, and
  governance inventory.

### Validation And Evidence

- The deterministic four-provider cohort passed with no network or provider
  calls: all four routes are `documented` plus deterministic `pass`, while
  `verified=0`, `partial=0`, `reduced_authority=4`, `blocked=0`, and
  `deferred=0`. Its live-smoke status remains `deferred`.
- The focused provider/catalog/authority suite passed 35 tests; repository
  governance passed with 0 errors and 0 warnings; the focused source,
  document, and evidence secret scan passed.
- Preserved the secret-free cohort report under
  `PRIVATE/agentic-update-pipeline/runs/oss-provider-truth-20260727/`.

### Unresolved And Next Entry Point

- No external route is promoted: every current reference route remains
  `review_only` / `reduced_authority` at `no_tools` / `ask` pending its exact
  `execution_route_adapter_dry_run`, then separately authorized smoke and
  later promotion gates. Kimi K3 receives no bypass.
- Step 5 is complete. Next: Step 6, `OSS-GUI-CODE-06`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 6

### Request

- Prove the product's GUI-and-code orchestration claim with one bounded,
  provider-free workflow rather than a visual-only demo.

### Changes

- Added [GUI / Code Orchestration Parity](GUI_CODE_ORCHESTRATION_PARITY.md),
  including canonical source/GUI/runtime representations, source ownership,
  explicit detach/export behavior, reproducibility commands, owners, and
  non-claims.
- Added a deterministic parity runner and focused regression test for the
  checked-in four-node Code Fix / Test / Review graph.
- Repaired task-graph synchronization so an unchanged machine-result schema
  retains its authored canonical schema reference instead of being silently
  renamed during a source -> GUI -> export cycle.
- Updated the README, claim matrix, registry, governance inventory, and
  project summary; preserved generated semantic, browser, screenshot, and
  focused secret-scan evidence under
  `PRIVATE/open-source-productization/validation/step6-gui-code-parity-20260727/`.

### Validation And Evidence

- The deterministic runner imported native source JSON into an isolated
  source-owned task graph, blocked direct GUI mutation as
  `graph_source_owned`, passed dry-run, completed fixture run, and completed
  export/re-import with `no_change` and zero changes. It recorded no provider
  or network calls.
- The in-app browser opened the generated `.abproj`, clicked **Task Graph**,
  rendered `Plan Fix`, `Apply Code Fix`, `Run Tests`, and `Review Result`,
  showed the source-owned banner, and exposed the selected node's ports and
  `ask` permission state. Browser console errors were empty.
- The focused parity/file-format suites, Desktop Task Graph test, and Desktop
  production build passed. The broader task-graph HTTP API suite reported nine
  initial tests as `ok` and then hung in its large HTTP integration test; its
  owned loopback process was stopped after a bounded wait and the exact
  default-stability handoff is preserved under the Step 6 validation root.
  Scripted handoff-plan validation and governance passed; the linked public
  evidence set passed the focused secret scan with zero findings.

### Unresolved And Next Entry Point

- The proof is intentionally limited to the native supported subset. It does
  not establish live provider behavior, tool authority, autonomous code
  writes, source-file write-back, or lossless conversion for arbitrary GUI or
  external workflow formats.
- A broad scan of the incidental isolated runtime tree finds generic
  token-shaped examples in copied skill documentation; that raw diagnostic
  tree is preserved but is not public proof. The exact linked evidence bundle
  is clean.
- The full task-graph HTTP API suite must be diagnosed under the default
  stability queue before it can be claimed as a complete suite pass; this does
  not invalidate the Step 6-specific deterministic parity proof.
- Step 6 is complete. Next: Step 7, `OSS-EXTENSION-CONTRIB-07`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 7

### Request

- Establish a safe first extension/contribution surface without advertising
  private runtime internals, automatic trust, or a pre-license public intake
  path as stable product APIs.

### Changes

- Added [Extension and First-Contribution Surface](EXTENSION_AND_FIRST_CONTRIBUTION_SURFACE.md),
  a public classification of supported native graph authoring, experimental
  candidate skills/plugins/presets/metadata/adapters, internal runtime and
  transport surfaces, and deferred marketplace/public-intake paths.
- Added a copyable read-only candidate skill example under
  `examples/extension-contribution/contributor-read-only-brief/`, a
  deterministic validation runner, and a focused regression test.
- Linked the contribution route from `CONTRIBUTING.md`, README, claim matrix,
  registry, governance inventory, and project summary.

### Validation And Evidence

- The candidate manifest resolved to the existing
  `supervisor_worker_synthesizer` graph and passed canonical lint, compile,
  and dry-run. The preserved evidence records zero provider, network, MCP, or
  agent-execution calls.
- A deliberately out-of-allowlist `glm/glm-5.2` request returned structured
  `requested_route_widens_*_allowlist` blockers. Candidate lifecycle and
  uncertain route/preset conditions remain warnings, not promotion signals.
- Focused candidate/skill/preset/registry/file-format suites passed 26 tests;
  the Desktop extensions inventory panel passed 21 tests. Governance and the
  scripted plan validator passed; the focused source and evidence secret scan
  had zero findings.

### Unresolved And Next Entry Point

- DG-OSS-03 selected the experimental-labeled route. The documented native
  graph subset is supported only to its present evidence boundary; skills,
  plugins, presets, provider metadata, and loss-aware external adapters are
  not promoted to automatic/live/stable public APIs.
- License/contribution terms, private reporting contacts, public marketplace,
  automatic third-party execution, live provider qualification, and broad
  external merge-ready intake remain owner-gated or deferred.
- Step 7 is complete. Next: Step 8, `OSS-RELEASE-08`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 8

### Request

- Make the install, release, security, privacy, support, and recovery baseline
  runnable without creating an unauthorized release, publishing private
  contacts, or turning package rehearsal into a public-installer claim.

### Changes

- Added [Developer Preview Baseline](DEVELOPER_PREVIEW_BASELINE.md), a public
  source-evaluation/install/support/recovery guide that lists the exact tested
  boundary, non-sensitive report contents, data-flow rules, five release
  blockers, and their owners.
- Added `scripts/run_developer_preview_baseline_check.py` and a focused
  regression test. The script aggregates passing release-readiness and isolated
  Windows update-rehearsal summaries into a compact, secret-free evidence
  packet and always classifies the public release as `blocked` until the owner
  gates are resolved.
- Linked the baseline from the README, security policy, release checklist,
  claim matrix, registry, governance inventory, and project summary.

### Validation And Evidence

- `PRIVATE/rr8/step8rr/reports/summary.json` passed all six release-identity,
  staging, and updater checks for `0.1.0`; both staged inventories contained
  904 files.
- `PRIVATE/wu8/step8wu/windows-update-rehearsal/summary.json` passed the
  isolated `canary` clean-bundle, update transaction, rollback, and four
  transaction-recovery scenarios. This remains deterministic rehearsal
  evidence, not a public update-service assertion.
- The new aggregator emitted `demonstrated` source evaluation, passing package
  and update evidence, five named blockers, zero provider calls, and zero
  network calls. The resulting secret-free evidence and scans are preserved
  under `PRIVATE/open-source-productization/validation/step8-preview-baseline-20260727/`.
- Focused baseline, release-identity, governance-check, and app-hardening
  suites passed 2, 10, 14, and 6 tests respectively. Repository governance
  and both focused secret scans passed with zero errors/warnings/findings.

### Unresolved And Next Entry Point

- A public release remains blocked by license/contribution terms, private
  vulnerability reporting, private conduct reporting, safe public
  support/triage, and authorized signing/distribution. No provider call,
  installer publication, external contact, or private credential was used.
- A first release-readiness run used an overly deep Windows artifact root and
  hit `FileNotFoundError` while staging generated Desktop files. The failed
  artifact is preserved; the short-root retry passed and the workaround is
  documented. The release owner must resolve path-length hardening before an
  installer release rather than hiding it as an install claim.
- Step 8 is complete. Next: Step 9, `OSS-QUALITY-09`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 9

### Request

- Build a public quality and reliability evidence dossier that presents current
  passing evidence, failures, reduced-authority states, warning gates, and
  release blockers without exposing private logs or turning a local check into
  a broad product claim.

### Changes

- Added [Public Quality and Reliability Dossier](PUBLIC_QUALITY_RELIABILITY_DOSSIER.md)
  and its machine-readable JSON source. It contains seven claim cards with an
  evidence class, result date, reproduction source, owner, limitation, and
  public failure-detection path.
- Added a deterministic dossier aggregator and focused regression test. The
  aggregator consumes fresh secret-free evidence inputs and rejects an attempt
  to hide the public-release blocker; it emits a separate negative ledger.
- Linked the dossier from the README, project summary, claim matrix,
  developer-preview baseline, registry, and governance inventory.

### Validation And Evidence

- Fresh local evidence for the flagship workflow, GUI/code parity, candidate
  extension, four-provider reference cohort, preview baseline, and hardening
  scan produced 7 cards: 3 `pass` or `demonstrated` cards and 4
  `reduced_authority`, `warning_gated`, or `blocked` cards.
- The negative ledger explicitly includes the provider cohort, first extension
  candidate, security/privacy boundary, and package/update baseline. It also
  surfaces the prior broader Task Graph HTTP-suite hang and Windows
  deep-artifact-path failure as qualification gaps rather than using focused
  checks as substitutes.
- Dossier tests passed 2/2. Related flagship, GUI/code, extension, provider,
  preview-baseline, release-identity, app-hardening, and governance tests
  passed. Repository governance and both focused secret scans had zero
  errors/warnings/findings. Evidence is preserved at `PRIVATE/qd9/` and
  `PRIVATE/agentic-update-pipeline/runs/qd9-provider-20260727/`.

### Unresolved And Next Entry Point

- No authority or release state changed: external routes remain reduced
  authority, the extension remains candidate/warning-gated, private reporting
  and public support are unconfigured, and public distribution remains blocked.
  The full Task Graph HTTP integration gap and release-artifact path-length
  hardening must not be hidden by this dossier.
- Step 9 is complete. Next: Step 10, `OSS-COMMUNITY-10`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 10

### Request

- Establish a safe contributor feedback and first-contribution protocol without
  opening public intake, inventing a private contact, accepting external code,
  or calling a provider.

### Changes

- Added five local GitHub-compatible issue templates and disabled blank issues.
  Each template carries secret-redaction, non-security, pre-preview, and scope
  boundaries rather than presenting an open support promise.
- Added [Contributor Feedback Protocol](CONTRIBUTOR_FEEDBACK_PROTOCOL.md), a
  public reference for safe templates, owner routing, three candidate tasks,
  two independent provider-free rehearsals, future-only response activation,
  and lightweight decision records for provider, orchestration, and public
  claim changes.
- Added a deterministic cohort runner and focused test. It runs the existing
  read-only candidate twice in separate roots, requires the authority-widening
  block, and records zero provider and network calls.
- Linked the protocol through contribution, preview, foundation, claim-matrix,
  README, project-summary, registry, and governance entry points. Retained
  evidence examples now use the `PRIVATE/.../reports/...` artifact bucket.

### Validation And Evidence

- Final cohort evidence at `PRIVATE/c10-final-20260727/reports/` reports five
  templates, three bounded candidates, two independent successful rehearsals,
  `pending_public_intake`, zero provider calls, and zero network calls.
- Focused cohort, extension-example, repository-governance, and app-hardening
  suites passed 2, 1, 14, and 6 tests. Repository governance passed with zero
  errors/warnings; final app-hardening and focused orchestration secret scans
  reported zero findings.
- An initial hardening scan correctly rejected the first diagnostic output
  because it was not stored under a permitted artifact bucket. The diagnostic
  remains preserved at `PRIVATE/c10-rerun-20260727/`; the final governed rerun
  uses `PRIVATE/c10-final-20260727/reports/` and passed without exceptions.

### Unresolved And Next Entry Point

- This creates no active public issue tracker, support SLA, private reporting
  route, named maintainer, license, contribution terms, external code intake,
  provider authority, or distribution approval. All remain explicit gates.
- Step 10 is complete. Next: Step 11, `OSS-CLOSURE-11`, in
  `PLAN/ASTRABRIDGE_OPEN_SOURCE_DEVELOPER_PRODUCTIZATION_SCRIPTED_HANDOFF_PLAN.md`.

## 2026-07-27 - Open-Source Productization Step 11

### Request

- Close the developer-preview readiness decision with current evidence, an
  honest go/dogfood/pause outcome, explicit non-claims, named owners, and one
  unambiguous next action without publishing or enabling any external path.

### Changes

- Added [Developer Preview Readiness Decision](DEVELOPER_PREVIEW_READINESS_DECISION.md),
  a failure-visible public dossier that applies DG-OSS-04 and records mandatory
  branch C `pause` for a public preview.
- Added a deterministic readiness evaluator and focused regression coverage.
  It joins the fresh preview-baseline packet, current quality manifest, and
  pre-preview contributor cohort; it fails if a release blocker is omitted or
  cohort evidence claims active public intake.
- Corrected the preview-baseline aggregate's stale pre-Step-10 support action:
  safe templates are now recognized as prepared but still disabled pending
  legal, private-reporting, triage, repository-host, and distribution gates.
- Completed and retired the open-source productization plan as an active queue.
  The only follow-up is `OSS-FOUNDATION-CLEARANCE-01`, an owner-gated unit in
  the readiness decision rather than a hidden agent release task.

### Validation And Evidence

- Fresh `PRIVATE/c11-final-20260727/reports/` evidence reports a passing
  source/package/update baseline, seven quality cards with four visible
  non-pass cards, and `DG-OSS-04 / pause / C` with zero provider or network
  calls.
- Readiness, baseline, quality-dossier, contributor, extension, provider,
  GUI/code, flagship, release-identity, governance, and hardening focused
  suites passed. Repository governance, app-hardening scan, and focused secret
  scan all returned zero errors/warnings/findings.
- A broad secret-pattern scan initially flagged safe hyphenated provider-
  credential prose in two governance documents. Both were changed to equivalent
  plain-language wording;
  the final scan passed. The failed scan report is preserved as a diagnostic
  in the final private evidence root.

### Unresolved And Next Entry Point

- Public preview is intentionally paused: license/contribution terms, private
  vulnerability reporting, private conduct reporting, public triage ownership,
  and authorized distribution remain owner-gated. Provider authority,
  extension stability, broader Task Graph HTTP integration, and Windows
  path-length limits retain their documented boundaries.
- The 11-step productization plan is complete. Do not resume it. After explicit
  owner authority, start only `OSS-FOUNDATION-CLEARANCE-01` in
  [Developer Preview Readiness Decision](DEVELOPER_PREVIEW_READINESS_DECISION.md),
  then run a new readiness evaluation.
