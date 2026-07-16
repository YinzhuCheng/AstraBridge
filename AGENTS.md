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
- Treat AstraBridge background-process hygiene as a standing engineering requirement: during local app development, proactively audit and reap clearly stale AstraBridge-owned frontend, sidecar, router, MCP, and helper processes so zombie `python`/`node`/`cmd` launchers do not accumulate across retries, restarts, or failed debug sessions.
- During AstraBridge desktop or sidecar development, inspect local background processes regularly and promptly terminate stale or zombie AstraBridge-owned frontend, sidecar, router, MCP, or helper processes left behind by failed runs, so they do not accumulate into large batches of background zombies. Treat this as routine hygiene, not optional cleanup: before starting a new local frontend or sidecar stack, first check the expected listener ports and clear stale AstraBridge instances that still hold them, and after substantial test/debug sessions, verify that only the intentionally active local instances remain. At the start and end of each local dev round, run a quick process audit for duplicate AstraBridge listeners and orphaned `cmd`/`node`/`python` launch wrappers, and reap only the clearly stale ones. If a local launch fails to bind or a restart behaves unexpectedly, stop and audit existing AstraBridge listeners before retrying so failed relaunch loops do not accumulate more background zombies. Prefer the repository cleanup helper `scripts/cleanup_stale_astrabridge_processes.ps1` when it matches the current stack, and record any manual kills in the working notes when they affect a live debug session. Do not kill unrelated user processes without clear ownership evidence. Prefer listener ports and explicit launch records over parent/child-process inference when deciding what is stale, because detached launchers can make active AstraBridge instances appear under an older parent PID.

## Current Repository Execution State

The repository normalization pass is complete and is preserved as a historical execution record:

- [PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md](D:/AstraBridge/PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md)

Do not delete, replace, or rewrite that completed plan structure unless the user explicitly asks for that. If the record file is changed accidentally, restore its prior execution state before doing other work.

Current repository-wide product boundary:

- Current projects use `.abproj` plus workspace-local `.astrabridge/` state.
- Legacy `.lcr*`, `.codexproj`, `.codex-shell`, and official-login paths are guardrails or historical evidence only.
- Compatibility shims are documented in `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md` and must not become new implementation entry points.
- Keep `PRIVATE/**`, validation artifacts, demo runs, caches, logs, and raw experiment traces unless the user explicitly names cleanup targets.

## Execution Loop Rule

For each user-facing execution round under a numbered plan that explicitly owns the requested work:

1. Start from the earliest unchecked numbered step unless the user explicitly redirects to another numbered step.
2. Complete exactly one full numbered step such as `1.2` or `3.1` before stopping; do not stop on partial progress inside that step.
3. After completing that step, update that plan file:
   - mark the step as `[x]` in the execution status table
   - append a dated entry in the completion record
   - state the next step entry point
4. If blocked, record the concrete blocker and next entry point in the plan; do not write vague “continue cleanup” notes.
5. Do not revive deleted plans, retired priority systems, or superseded execution slices unless the user explicitly asks for them.

## Round Completion Log

- 2026-06-23: Rebased repository execution rules onto `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`; the normalization execution flow used one numbered step per turn.
- 2026-06-27: Repository normalization plan is complete; future work should start from the plan that matches the requested product area, not from the completed normalization record.

## Capability Runtime Follow-on Plan

When the user explicitly asks to implement or advance the capability runtime, use:

- [PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md](D:/AstraBridge/PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md)

Execution rule for the capability runtime follow-on plan:

1. Start from the next incomplete numbered step in that plan unless the user explicitly redirects to another numbered step.
2. Complete exactly one full numbered step per round; do not stop on partial progress inside that step.
3. After completing that step, update that plan's current progress and completion record before stopping.
4. Keep web search as a standalone web lane rather than a model-backed capability unless the user explicitly asks to merge them.
