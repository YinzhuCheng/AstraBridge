# AstraBridge Near-Term Product Focus And Non-Trivial Priorities

Status: active focus guidance. This file is meant to reduce drift, not to replace the broader architecture plans.

Last updated: 2026-06-22

Related documents:

- [14_PROVIDER_NEUTRAL_CODING_RUNTIME_ROADMAP.md](D:/AstraBridge/PLAN/14_PROVIDER_NEUTRAL_CODING_RUNTIME_ROADMAP.md)
- [29_HERMES_SUGGESTION_CANONICAL_PRODUCT_UPGRADE_MASTER_EXECUTION_GUIDE.md](D:/AstraBridge/PLAN/29_HERMES_SUGGESTION_CANONICAL_PRODUCT_UPGRADE_MASTER_EXECUTION_GUIDE.md)

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
