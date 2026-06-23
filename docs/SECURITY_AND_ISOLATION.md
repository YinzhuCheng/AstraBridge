# Security And Isolation

Last updated: 2026-06-21

## Product Boundaries

AstraBridge is a local coding-agent workbench with its own project and runtime state.

Normal AstraBridge product behavior must use:

- `.abproj`
- workspace-local `.astrabridge/`
- AstraBridge-managed app data
- AstraBridge-managed Codex home overrides when isolation is required

Normal AstraBridge product behavior must not use:

- official Codex `~/.codex/config.toml`
- project `.codex/`
- project `.codex*`
- official OpenAI account login as a product auth path

## Secrets

Plaintext secret material must not be written into:

- git-tracked files
- `.abproj`
- `.astrabridge/`
- docs
- reports
- screenshots
- logs
- browser captures
- checkpoint manifests

Protected secret types include:

- API keys
- bearer tokens
- `Authorization` headers
- cookies
- vault passwords
- provider raw secrets

OpenAI API keys are treated as normal provider credentials, not official account-login credentials.

## Allowed Credential Storage Paths

Preferred safe paths:

- encrypted AstraBridge vault:
  - `%APPDATA%/AstraBridge/llm_api_manager/users/<username>/vault.abvault`
- short-lived process environment variables

Documented local-only paths:

- `PRIVATE/secrets/provider-keys/`
- `PRIVATE/vault-backups/`

See [PRIVATE/README.md](/D:/AstraBridge/PRIVATE/README.md) for the local-only rules.

## Isolated Runtime Roots

Use these when testing or running a clean-user demo:

- `ASTRABRIDGE_APPDATA`
- `ASTRABRIDGE_CODEX_HOME`

Recommended use cases:

- sidecar tests
- browser-smoke runs
- clean-user preview runs
- demo artifact preservation under `PRIVATE/demo-runs/`

Isolation objective:

- keep AstraBridge state out of official Codex state
- make demo and smoke runs reproducible
- make cleanup optional rather than required

## Artifact Policy

Preserve diagnostics and experiment artifacts by default, but only in secret-safe form.

Allowed artifact roots:

- `<workspace>\.astrabridge\`
- `D:\AstraBridge\PRIVATE\demo-runs\`

Common allowed artifacts:

- browser captures
- sanitized health results
- checkpoint manifests
- catalog review artifacts
- release evidence notes

Not allowed in durable artifacts:

- plaintext credentials
- real auth headers
- raw secret payloads

## Scanning Expectations

Before a release candidate or public push:

- run a secret scan excluding `PRIVATE/**`, `node_modules/**`, `dist/**`, and generated binaries
- run a legacy scan to confirm old project/state paths are not exposed as normal product behavior
- confirm official Codex config remains untouched

The release gate reference is [RELEASE_CHECKLIST.md](/D:/AstraBridge/docs/RELEASE_CHECKLIST.md).

## Operator Guidance

If a workflow fails:

- preserve secret-safe evidence
- prefer browser captures, supervisor status, and sanitized summaries over raw transport dumps
- use `docs/DEMO_RUNBOOK.md` and `docs/RELEASE_CHECKLIST.md` guidance for repeatable recovery checks

Do not solve failures by hand-editing `.astrabridge/` state unless a dedicated recovery tool explicitly requires it.
