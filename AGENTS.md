# AstraBridge Agent Rules

AstraBridge is an independent product with its own runtime and project-state boundaries. Do not rely on any older Research OS prototype state.

- Do not store API keys, bearer tokens, cookies, auth headers, or provider raw secrets in git, project files, reports, or logs.
- In any commit/push path, ensure no secrets are logged, printed, persisted, or staged; run a quick secret scan before pushing and exclude any raw secret-bearing artifacts.
- New projects use `.abproj` and workspace-local `.astrabridge/` state only.
- `.abproj` and workspace-local `.astrabridge/` are the only normal product project paths. Do not reintroduce `.lcrproj`, `.lcr`, `.codexproj`, or `.codex-shell` as supported product state.
- Do not write official Codex `~/.codex/config.toml` or project `.codex*` files during normal use.
- OpenAI is a normal API-key provider. Do not reintroduce official OpenAI account login as a product path.
- Do not read Desktop key files or other plaintext secret sources unless the user explicitly authorizes that exact action for the current task.
- Preserve diagnostics and validation reports, but redact secrets before saving anything durable.

## Current Execution Focus

The active execution source of truth is:

- [PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md](D:/AstraBridge/PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md)

Do not delete, replace, or rewrite the active plan structure unless the user explicitly asks for that. If the active plan file is changed accidentally, restore its prior execution state before doing other work.

Current repository-wide objective:

- Normalize the repo around the current AstraBridge product architecture.
- Remove or rewrite obsolete legacy plan guidance, product-path compatibility language, and stale repository entry points.
- Keep `PRIVATE/**`, validation artifacts, demo runs, caches, logs, and raw experiment traces unless the user explicitly names cleanup targets.

## Execution Loop Rule

For each user-facing execution round under the active execution plan:

1. Start from the earliest unchecked numbered step unless the user explicitly redirects to another numbered step.
2. Complete exactly one full numbered step such as `1.2` or `3.1` before stopping; do not stop on partial progress inside that step.
3. After completing that step, update `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`:
   - mark the step as `[x]` in the execution status table
   - append a dated entry in the completion record
   - state the next step entry point
4. If blocked, record the concrete blocker and next entry point in the plan; do not write vague “continue cleanup” notes.
5. Do not revive deleted plans, retired priority systems, or superseded execution slices unless the user explicitly asks for them.

## Round Completion Log

- 2026-06-23: Rebased repository execution rules onto `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`; the active execution flow remains one numbered step per turn.

## Capability Runtime Follow-on Plan

When the user explicitly asks to implement or advance the capability runtime, use:

- [PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md](D:/AstraBridge/PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md)

Execution rule for the capability runtime follow-on plan:

1. Start from the next incomplete numbered step in that plan unless the user explicitly redirects to another numbered step.
2. Complete exactly one full numbered step per round; do not stop on partial progress inside that step.
3. After completing that step, update that plan's current progress and completion record before stopping.
4. Keep web search as a standalone web lane rather than a model-backed capability unless the user explicitly asks to merge them.
