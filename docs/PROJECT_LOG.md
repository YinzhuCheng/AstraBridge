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
