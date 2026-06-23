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
- Verified `python -B -m unittest discover -s apps/astrabridge-sidecar/tests -p test_sidecar_services.py` passes (332 tests).
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

- **Status:** `Priority 1` is considered complete for this branch, and now enters the repository baseline.
- **Priority 2 status:** started and on-track. Core provider/profile truth paths are consolidated in:
  - `astrabridge_sidecar/model_catalog/catalog.py` (`known_*` no legacy model-name heuristics)
  - `astrabridge_sidecar/router_service.py` / `astrabridge_sidecar/router_config_service.py` (`provider_family` required for implicit profile inheritance)
  - `astrabridge_sidecar/llm_api_manager_service.py` (`web_smoke` source URL now catalog-driven)
  - `astrabridge_sidecar/tests/test_sidecar_services.py` (provider_family regression guard)

What remains before calling Priority 2 complete:

1. remove any remaining public paths that still document or expose legacy `lcr_*` model sources (if any) outside compatibility-only tooling names;
2. complete one more router/metadata smoke pass using generated catalog source/status as the single truth;
3. add a short, user-visible acceptance check that provider-truth fields appear in metadata model panel.

## 1.2 Execution Focus Guidance

- Current branch scope should stay constrained:
  1. remove remaining duplicated provider-specific fact derivations outside catalog/profile contracts;
  2. keep provider-switch and workflow continuity evidence as the highest-priority cross-panel acceptance path;
  3. keep any additional provider additions or cosmetic work deferred until these two items are complete.

## 2. Ranked Priorities

## Priority 1: Isolation Boundary Hardening

This is the highest-value immediate priority.

Reason:

- Recent repository pollution proved that shared repo roots, shared output roots, shared caches, and unrelated experiment artifacts can directly make the product unreliable.
- A coding app that cannot keep task artifacts, downloads, caches, and generated outputs inside the correct boundaries is not yet a dependable app.

What this priority includes:

1. define default roots for task artifacts, generated outputs, model caches, downloads, and temporary files
2. ensure unrelated tasks do not write into the main repo tree by default
3. ensure high-risk or high-volume workflows use isolated artifact roots or worktrees
4. ensure repo-facing Git operations cannot silently absorb large local experiment outputs
5. make the product's "safe default storage model" explicit in code and docs

What "done enough" looks like:

1. a new coding task cannot accidentally pollute the repo with large non-source artifacts
2. browser/demo tasks, model-cache tasks, and experimental tasks have clear separate roots
3. the product can survive multiple concurrent tasks without cross-contamination

## Priority 2: ProviderProfile Plus Generated Catalog As The Only Truth

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

## Priority 3: CodingEvent Contract Unification

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

## Priority 4: One Release-Grade End-To-End Coding Workflow

This is the fastest way to prove the app is genuinely usable.

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

**Isolation Boundary Hardening**

If two slices are chosen next, choose:

1. Isolation Boundary Hardening
2. ProviderProfile Plus Generated Catalog Single-Truth Consolidation

That pair most directly moves AstraBridge from "promising demo" to "dependable internal app."

## 6. Near-term Execution Slices

- Slice A (immediate):
  - finish Priority 2 hardening gap pass:
    - keep `lcr_*` usage only in explicit compatibility aliases,
    - complete one metadata/health smoke validation against generated catalog records,
    - keep desktop status and model panels aligned to provider-family derived fields.

- Slice B:
  - complete Priority 3 visible event-contract pass around task/thread evidence and handoff rows.

- Slice C:
  - keep Priority 4 release-style end-to-end workflow as the readiness gate before broader expansion.
