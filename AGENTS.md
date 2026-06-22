# AstraBridge Agent Rules

AstraBridge is a product split from the Research OS Local Codex Router prototype. Keep the product independent and do not rely on Research OS project state.

- Do not store API keys, bearer tokens, cookies, auth headers, or provider raw secrets in git, project files, reports, or logs.
- New projects use `.abproj` and workspace-local `.astrabridge/` state only.
- Legacy `.lcrproj/.lcr` may be imported explicitly; do not create them for new projects.
- Do not write official Codex `~/.codex/config.toml` or project `.codex*` files during normal use.
- OpenAI is a normal API-key provider. Do not reintroduce official OpenAI account login as a product path.
- Preserve diagnostics and validation reports, but redact secrets before saving anything durable.

## Current Execution Focus

Near-term execution should prioritize the smallest set of non-trivial changes that most directly moves AstraBridge toward a dependable usable app. See:

- [PLAN/30_NEAR_TERM_PRODUCT_FOCUS_AND_NON_TRIVIAL_PRIORITIES.md](D:/AstraBridge/PLAN/30_NEAR_TERM_PRODUCT_FOCUS_AND_NON_TRIVIAL_PRIORITIES.md)

Current priority order:

1. Isolation boundary hardening
2. ProviderProfile plus generated catalog as the single truth source
3. CodingEvent contract unification across chat/files/review/checkpoint/diagnostics
4. One release-grade end-to-end coding workflow
5. A minimal native-kernel cut only after the priorities above are reasonably stable

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
