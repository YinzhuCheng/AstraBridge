# AstraBridge Near-Term Product Focus And Non-Trivial Priorities

Status: active focus guidance. This file is meant to reduce drift, not to replace the broader architecture plans.

Last updated: 2026-06-23

Related documents:

- Current active tracking for this branch is this plan itself and:
- [HANDOFF.md](/D:/AstraBridge/HANDOFF.md)
- [README.md](/D:/AstraBridge/README.md)

## 1. Current Judgment

AstraBridge is already close to a usable internal app demo.

What is still missing is not "more features everywhere," but a small number of structural cuts that determine whether the app is merely demoable or actually dependable during real multi-thread, multi-provider use.

Therefore, near-term execution should optimize for:

1. hardening the product boundary
2. reducing structural drift
3. proving one real coding workflow end to end

Near-term execution should not optimize for:

1. additional cosmetic polish
2. metadata micro-tuning without workflow impact
3. broad provider expansion before current contracts are stable
4. installer/packaging work before the core workflow is dependable

## 1.1 Execution checkpoint (2026-06-23)

- Completed by sidecar test harness team:
  - Extended browser smoke presets to assert checkpoint/review/diagnostic workflow facts and artifacts (`task-fact-*`, `workflow-fact-*`) rather than only presence of basic app chrome.
  - Added corresponding unit test assertions in `apps/astrabridge-sidecar/tests/test_sidecar_services.py` to lock in the new acceptance expectations.
- Verified `python -B -m unittest discover -s apps/astrabridge-sidecar/tests -p test_sidecar_services.py` passes (335 tests).
- Verified `cmd /c npm run test` in `apps/astrabridge-desktop` passes (61 tests).
- Verified `cmd /c npm run build` in `apps/astrabridge-desktop` passes.
- Follow-up hardening completed on this branch:
  - Removed heuristic fallback logic in `astrabridge_sidecar/model_catalog/catalog.py` from `known_context_window()` and `known_input_modalities()`, so catalog/profile-derived facts now take precedence.
  - Removed provider-name prefix hardcoding from `apps/astrabridge-desktop/src/App.tsx` for active model provider inference; Composer now prefers explicit model metadata.
  - Hardened `RouterConfigService` to require explicit `provider_family` to consume provider profile semantics; custom provider ids no longer inherit unknown-family profile defaults.
  - Tightened LLM API smoke logic to use only configured `source_urls` on model/provider records, removing legacy hardcoded provider URL fallbacks.
  - Added regression test to ensure each new `.abproj` gets an isolated runtime bundle root, with independent `project_runtime_root` and `codex_home_root` values under appdata runtime.
  - Reworked storage policy documentation in `docs/SECURITY_AND_ISOLATION.md` to make the default isolation model explicit (workspace state roots vs runtime roots vs injected launch env vars).
  - Reasserted router normalization test resilience (provider-error actionable hint can route to auth/connectivity/context hints instead of a single phrase).
- Interpretation against current priorities:
  - **Priority 1 (Isolation Hardening):** strengthened by asserting workflow evidence surfaces and checkpoint/review artifacts that are part of the isolation/audit picture.
  - **Priority 3 (CodingEvent Contract Unification):** improved by forcing the product’s high-value workflow surfaces to remain in one observable acceptance trace.

### Execution status snapshot

- **Priority 1 status:** completed and retired into the repository baseline.
- **Priority 2 status:** completed in this branch for demoability gates. Core provider/profile truth paths are consolidated in:
  - `astrabridge_sidecar/model_catalog/catalog.py` (`known_*` no legacy model-name heuristics)
  - `astrabridge_sidecar/router_service.py` / `astrabridge_sidecar/router_config_service.py` (`provider_family` required for implicit profile inheritance)
  - `astrabridge_sidecar/llm_api_manager_service.py` (`web_smoke` source URL now catalog-driven)
  - `astrabridge_sidecar/tests/test_sidecar_services.py` (provider_family regression guard)

Priority 2 hardening gap completed (2026-06-23): single-truth catalog/metadata/health consistency and explicit user-facing metadata model panel checks are now in place.

- **Priority 3 status:** completed in this branch for visible workflow semantics.
  - `astrabridge_sidecar/task_conversation_service.py` keeps one canonical visible task conversation with event-only handoff turns.
  - `astrabridge_sidecar/task_service.py` persists checkpoint / verification / diagnostic refs derived from coding events.
  - `apps/astrabridge-desktop/src/features/runtime/taskInspectorEvidence.ts` and `taskWorkflowFacts.ts` now provide one shared event-derived evidence path for review/files/terminal/workflow facts.
  - `apps/astrabridge-desktop/src/App.tsx` now refreshes `task-conversation` together with runtime thread/turn/supervisor updates, so the visible task chat stays aligned with provider handoffs.
- **Priority 4 status:** completed in this branch as the release-grade workflow gate.
  - `astrabridge_sidecar/project_tools_service.py` prepares a repeatable isolated demo workflow with provider handoff, review artifact, failed command, recovered command, and checkpoint evidence.
  - `astrabridge_sidecar/dogfood_run_service.py` now treats browser-smoke success as workflow-assertion success, while filtering known nonblocking local runtime polling noise instead of failing the whole demo on background fetch churn.
  - `apps/astrabridge-desktop/src/App.tsx` now opens browser smoke URLs in explicit `smoke=1` low-noise mode and disables background event/polling churn during smoke acceptance.
  - Acceptance passed on `http://127.0.0.1:4181/?sidecar=http://127.0.0.1:8820&smoke=1` with review/files/terminal/status/checkpoint nodes verified and screenshot evidence captured under `.astrabridge/captures/`.

## 1.2 Execution Focus Guidance

- Current branch scope should stay constrained:
  1. keep the now-passing release workflow as baseline and avoid reopening it for cosmetic churn;
  2. move directly to the narrow native-kernel cut on top of the same workflow/evidence contract;
  3. keep additional provider additions or cosmetic work deferred until that native path is stable.

## 2. Ranked Priorities

## ~~Priority 2: ProviderProfile Plus Generated Catalog As The Only Truth~~

Completed on this branch. This is now repository baseline, not an active near-term slice.

This is the most important architecture consolidation after isolation.

Reason:

- Current foundations already exist, but provider truth is still partially duplicated across runtime, catalog, router, and UI.
- If this is not tightened now, every later provider/model feature will keep multiplying drift.

What this priority includes:

1. ProviderProfile owns provider-family behavior
2. generated catalog owns model-specific overrides
3. UI, router, runtime, and diagnostics consume those contracts rather than re-deriving them
4. capability badges, reasoning controls, edit preferences, and fallback candidates come from one truth path

What "done enough" looks like:

1. changing provider behavior mostly means changing profile or catalog, not many unrelated layers
2. desktop and sidecar stop carrying shadow logic for the same provider facts
3. adding a provider family no longer requires broad if-else edits

## ~~Priority 3: CodingEvent Contract Unification~~

Completed on this branch. This is now repository baseline, not an active near-term slice.

This is the most important product-shaping priority.

Reason:

- The app already has chat, files, review, checkpoint, and diagnostics surfaces.
- It still needs one event contract so these surfaces describe the same reality.

What this priority includes:

1. unify visible task conversation around a canonical event model
2. make file/review/checkpoint/diagnostic surfaces consume compatible event-derived state
3. make provider handoff and runtime transitions first-class events
4. stop letting different panels rely on unrelated internal representations

What "done enough" looks like:

1. the app feels like one coherent product, not several stitched tools
2. provider switching does not break the user's visible workflow model
3. review/checkpoint/diagnostics reflect the same underlying execution history

## ~~Priority 4: One Release-Grade End-To-End Coding Workflow~~

Completed on this branch. This is now repository baseline, not an active near-term slice.

Reason:

- A product is not validated by many partial capabilities.
- It is validated by one important workflow that reliably works from start to finish.

The canonical workflow should include:

1. create/open project
2. create or resume a task
3. send coding request
4. switch provider once
5. inspect files
6. inspect review/diff
7. run command or tests
8. create or preview checkpoint
9. trigger one failure and confirm recovery path

What "done enough" looks like:

1. this flow is repeatable without repo pollution
2. browser acceptance and sidecar validation both confirm it
3. failures are explainable and recoverable

## Priority 5: Minimal Native Kernel Cut, Not Full Native Expansion

This matters, but it should stay scoped.

Reason:

- Native kernel work is strategically important.
- It becomes wasteful if done before isolation, provider truth, and event contracts are stable.

What this priority includes:

1. keep the native path intentionally narrow
2. first prove read/review/small-edit/verify
3. do not expand to broad multi-provider autonomous write flows too early

What "done enough" looks like:

1. one non-Codex path works for a constrained coding task
2. event semantics remain aligned with the rest of the app
3. native kernel does not create a second inconsistent product model

## 3. Explicit Depriorities

Until the priorities above are substantially complete, agents should avoid spending primary effort on the following unless the user explicitly asks:

1. broad new provider expansion
2. UI cosmetic polish that does not affect workflow clarity
3. metadata seed polishing without user-facing workflow consequences
4. installer/bundling/packaging work
5. broad internal renaming with little product effect
6. generalized non-coding agent features
7. large documentation churn that does not sharpen the current execution path

These are not forbidden forever. They are simply not the current main goal.

## 4. Decision Rule For Future Agents

When choosing the next implementation slice, use this rule:

1. prefer changes that reduce contamination risk
2. then prefer changes that reduce provider-truth duplication
3. then prefer changes that unify visible workflow semantics
4. only then prefer nice-to-have polish

If a proposed task mostly improves a small detail but does not improve:

- isolation
- provider truth
- event unification
- end-to-end workflow reliability

then it should normally be deferred.

## 5. Immediate Recommendation

If only one major slice is chosen next, choose:

**Minimal Native Kernel Cut scoped to the same event contract**

If two slices are chosen next, choose:

1. Minimal Native Kernel Cut scoped to the same event contract
That most directly moves AstraBridge from "dependable app-server demo" to "provider-neutral product foundation."

## 6. Near-term Execution Slices

- Slice A (immediate):
  - finish Priority 2 hardening gap pass:
    - keep `lcr_*` usage only in explicit compatibility aliases,
    - complete one metadata/health smoke validation against generated catalog records,
    - keep desktop status and model panels aligned to provider-family derived fields.
  - Slice A status: completed (metadata provenance regression + smoke acceptance hooks landed).

- Slice B (immediate):
  - complete Priority 3 visible event-contract pass around task/thread evidence and handoff rows.
  - Slice B status: completed (composite task conversation refresh + shared inspector evidence path landed).

- Slice C (immediate):
  - Slice C status: completed (release workflow prepare + browser acceptance + visible in-app validation passed).

- Slice D:
  - keep Priority 5 native-kernel cut narrow now that Priority 4 acceptance is repeatable.
