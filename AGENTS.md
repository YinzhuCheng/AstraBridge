# AstraBridge Agent Rules

AstraBridge is a product split from the Research OS Local Codex Router prototype. Keep the product independent and do not rely on Research OS project state.

- Do not store API keys, bearer tokens, cookies, auth headers, or provider raw secrets in git, project files, reports, or logs.
- New projects use `.abproj` and workspace-local `.astrabridge/` state only.
- Legacy `.lcrproj/.lcr` may be imported explicitly; do not create them for new projects.
- Do not write official Codex `~/.codex/config.toml` or project `.codex*` files during normal use.
- OpenAI is a normal API-key provider. Do not reintroduce official OpenAI account login as a product path.
- Preserve diagnostics and validation reports, but redact secrets before saving anything durable.
