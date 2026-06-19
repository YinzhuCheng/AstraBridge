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
