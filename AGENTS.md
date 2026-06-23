# AstraBridge Agent Rules

AstraBridge is a product split from the Research OS Local Codex Router prototype. Keep the product independent and do not rely on Research OS project state.

- Do not store API keys, bearer tokens, cookies, auth headers, or provider raw secrets in git, project files, reports, or logs.
- In any commit/push path, ensure no secrets are logged, printed, persisted, or staged; run a quick secret scan before pushing and exclude any raw secret-bearing artifacts.
- New projects use `.abproj` and workspace-local `.astrabridge/` state only.
- Legacy `.lcrproj/.lcr` may be imported explicitly; do not create them for new projects.
- Do not write official Codex `~/.codex/config.toml` or project `.codex*` files during normal use.
- OpenAI is a normal API-key provider. Do not reintroduce official OpenAI account login as a product path.
- Preserve diagnostics and validation reports, but redact secrets before saving anything durable.

## Current Execution Focus

Near-term execution should prioritize the smallest set of non-trivial changes that most directly moves AstraBridge toward a dependable usable app. See:

- [PLAN/30_NEAR_TERM_PRODUCT_FOCUS_AND_NON_TRIVIAL_PRIORITIES.md](D:/AstraBridge/PLAN/30_NEAR_TERM_PRODUCT_FOCUS_AND_NON_TRIVIAL_PRIORITIES.md)

Baseline priorities already completed on this branch:

1. Isolation boundary hardening
2. ProviderProfile plus generated catalog as the single truth source
3. CodingEvent contract unification across chat/files/review/checkpoint/diagnostics

Current active priority order:

1. One release-grade end-to-end coding workflow
2. A minimal native-kernel cut only after the workflow above is reasonably stable

Until those priorities are substantially complete, do not let primary effort drift into overly trivial or low-leverage work such as:

- cosmetic UI polish without workflow impact
- metadata micro-tuning without contract or workflow impact
- broad new provider expansion before current contracts are stable
- installer/packaging work
- broad internal renaming with little product effect
- generalized non-coding agent features

When choosing the next slice, prefer work that improves:

1. isolation and contamination resistance
2. provider-truth consolidation
3. event and workflow unification
4. end-to-end reliability

Only after that should agents spend significant time on smaller polish items.

## Execution Loop Rule

For each round of execution:

For each user-facing conversation turn, execute and close exactly one major active step from the remaining plan (`Priority 4` or `Priority 5`) until those are finished.

1. Do not stop until that step is completed in code, tests, or docs that support the step.
2. Each step completed in a turn advances the cycle position.
3. The remaining cycle is complete when `Priority 4` and `Priority 5` have each been completed and retired from the active plan.
4. When a step is complete, remove or retire that step in the plan (or its active slice) so the next turn does not repeat it.
5. Record completion in the **Round Completion Log** below.

## Round Completion Log

- 2026-06-23: Priority 1 (Isolation Boundary Hardening) removed from active priority scope and execution loop to prevent priority cycling; plan now starts from Priority 2.
- 2026-06-23: Updated execution loop to require one full `Priority 2/3/4` advancement per turn, with explicit 3-turn completion target.
- 2026-06-23: Updated execution loop to include `Priority 5` and require one full `2/3/4/5` advancement per turn.
- 2026-06-23: Completed Priority 2 substep in turn: renamed MCP web verification status from legacy `verified_lcr_web` to `verified_astrabridge_web` in provider defaults (`astrabridge_sidecar.providers.registry`) and aligned desktop regression fixtures.
- 2026-06-23: Completed Priority 2 step in this turn: closed final metadata-truth gap pass by adding end-to-end catalog/metadata/health consistency assertions and user-visible metadata provenance smoke acceptance checks.
- 2026-06-23: Completed Priority 2 step in this turn: completed MCP web preset/route rename chain by adding `astrabridge_web` preset application path in sidecar (`/api/router/mcp/preset/astrabridge-web`), adding `astrabridge_web` compatibility support in runtime MCP server discovery, and adding sidecar tests for new preset and `astrabridge_web` server activation.
- 2026-06-23: Completed Priority 3 step in this turn: unified visible task evidence consumption by wiring workflow facts to the same task-inspector evidence path used by review/files/terminal panels, and refreshed `task-conversation` on runtime thread/turn/supervisor updates so provider handoff continuity stays visible.
