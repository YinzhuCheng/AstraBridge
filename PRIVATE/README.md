# PRIVATE Local Credential Area

This directory documents where AstraBridge developers may keep local private-property credential references during development.

Only this README is intended to be committed. Everything else under `PRIVATE/` is ignored by git and must never be pushed to a public remote.

Recommended local-only paths:

- `PRIVATE/secrets/provider-keys/`: optional plaintext key files for one developer machine only, if environment variables or the encrypted vault are not enough.
- `PRIVATE/secrets/authorization-samples/`: redacted request examples only. Never store a real `Authorization` header here.
- `PRIVATE/vault-backups/`: optional encrypted `vault.abvault` backups. Treat these as private property and never publish them.
- `%APPDATA%/AstraBridge/llm_api_manager/users/<username>/vault.abvault`: normal encrypted per-user vault location used by the app.
- Process environment variables such as `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `KIMI_API_KEY`, `DASHSCOPE_API_KEY`, or `YUNWU_API_KEY`: recommended automation path.

Rules:

1. Do not commit real API keys, bearer tokens, cookies, auth headers, SSH keys, provider raw responses, or key screenshots.
2. Do not paste real `Authorization: Bearer ...` headers into issues, docs, prompts, logs, reports, or screenshots.
3. If a test needs to describe a credential, use an environment variable name or vault key id, not the secret value.
4. If a private file is accidentally staged, stop and remove it from the index before any push.
