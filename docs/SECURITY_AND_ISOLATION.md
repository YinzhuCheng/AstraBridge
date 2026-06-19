# Security And Isolation

## Secrets

- No API keys in `.abproj`, `.astrabridge/`, git, reports, screenshots, or logs.
- Managed mode stores provider keys in an encrypted per-user vault.
- Anonymous mode uses pasted/session keys or environment variables only.
- OpenAI API keys are provider credentials, not official account login.

## Codex Isolation

Normal AstraBridge use must not write:

- `~/.codex/config.toml`
- project `.codex/`
- project `.codex*` files
## Private Credential Paths

Credential material is private property. AstraBridge may document local paths for operator-owned keys, but those files are not product source and must not be pushed to public git remotes.

Allowed local-only locations:

- `PRIVATE/secrets/provider-keys/` for optional developer-owned plaintext key files on one machine.
- `PRIVATE/vault-backups/` for encrypted `vault.abvault` backups.
- `%APPDATA%/AstraBridge/llm_api_manager/users/<username>/vault.abvault` for the normal encrypted user vault.
- Environment variables for automation, for example `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `KIMI_API_KEY`, `DASHSCOPE_API_KEY`, or `YUNWU_API_KEY`.

`PRIVATE/**` is ignored by git except `PRIVATE/README.md`. Real `Authorization` headers should never be stored; if a request example is needed, redact it to `Authorization: Bearer <redacted>`.
