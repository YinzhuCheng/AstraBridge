# Security And Isolation

Last updated: 2026-06-25

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

### Safe default storage model

Default per-project storage is intentionally split into:

- Workspace state (visible to users): `<workspace>/.astrabridge/`
  - `attachments`, `captures`, `downloads`, `caches`, `reviews`, `runtime-cwd`, `tmp`
  - `storage_policy.json`
  - runtime events and thread state snapshots
- Runtime execution roots (large/cross-run artifacts): `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/`
  - `project_runtime_root` (shared runtime workspace bucket)
  - `project_runtime_root/codex_home`
  - `project_runtime_root/downloads`
  - `project_runtime_root/caches`
  - `project_runtime_root/tmp`
- Temporary process env injected at launch:
  - `ASTRABRIDGE_PROJECT_RUNTIME_ROOT`
  - `ASTRABRIDGE_DOWNLOADS_ROOT`
  - `ASTRABRIDGE_CACHES_ROOT`
  - `ASTRABRIDGE_TMP_ROOT`
  - `ASTRABRIDGE_CODEX_HOME`

These roots must not be inside the user workspace.

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
- capability smoke summaries and artifact previews
- release evidence notes

Not allowed in durable artifacts:

- plaintext credentials
- real auth headers
- raw secret payloads

## Capability Runtime Safety

MCP-style capabilities follow the same secret and artifact policy as the rest of AstraBridge:

- `web.search` is a standalone web lane. It must not be merged into model-backed capability routing because the caller LLM judges search results.
- `astrabridge_capabilities` exposes model-backed image, vision, speech transcription, and speech synthesis tools through capability routing.
- The desktop Capabilities tab may show only redacted credential states: configured, missing, env ref, session required, or disabled.
- Missing/session-required/disabled provider credentials should block pinned provider route saves.
- Dry-run capability smoke must be deterministic and no-key.
- Provider-backed capability smoke must require explicit user approval for the exact run.
- Provider-backed smoke evidence may persist only sanitized request metadata, sanitized response metadata, route status, and artifact references.
- Raw provider secrets, bearer tokens, cookies, authorization headers, and plaintext keys must never be persisted in smoke evidence, artifacts, reports, logs, or screenshots.
- Artifact-producing capabilities should warn that image/audio outputs can be large and retained locally.

Capability artifact roots:

- `<workspace>/.astrabridge/capabilities/**`
- `PRIVATE/demo-runs/**` for release/demo evidence

Capability artifacts may include image previews, audio outputs, text summaries, JSON summaries, relative paths, provider/model labels, and timestamps. They must not include raw secret-bearing transport payloads.

## Plugin And Skill Trust Boundaries

Plugin and skill discovery is intentionally metadata-first. Discovery must not be treated as trust.

- `.codex-plugin/plugin.json`, `marketplace.json`, remote marketplace entries, and `SKILL.md` frontmatter are untrusted input until an operator reviews them.
- Inventory reads may parse these files and expose normalized metadata, but inventory alone must not execute plugin code, start MCP servers, or auto-enable skills.
- Remote or curated catalogs may be shown in AstraBridge as source metadata, but they remain advisory until a user explicitly previews and applies an install/update plan.
- Plugin install and update writes must stay inside AstraBridge-managed isolated runtime roots only:
  - `ASTRABRIDGE_CODEX_HOME/plugins/**`
  - `ASTRABRIDGE_CODEX_HOME/plugin-staging/**`
  - `ASTRABRIDGE_CODEX_HOME/plugin-rollbacks/**`
- Plugin inventory and enablement state must not write workspace `.codex*` files or official Codex user state during normal AstraBridge use.

### Declared side effects

Plugin metadata may declare MCP servers, apps, hooks, and skills. These declarations are disclosures, not approvals.

- Declared MCP servers must be shown before install/apply because they can introduce filesystem, network, or subprocess side effects once enabled in a runtime.
- Declared apps and hooks must be treated as additional execution surface, even if a plugin install plan itself is read-only.
- Plugin-owned skills must default to explicit approval flow; a newly installed skill should not silently become active just because the owning plugin was installed.

### Skill prompt safety

Skills are prompt material, not trusted code.

- `SKILL.md` content can steer the model, so it must be treated as prompt-injection-capable input until reviewed.
- Enabling a skill does not bypass AstraBridge sandbox, approval, or runtime-secret policy. It only makes the instructions available to the model.
- Skill ownership mismatches, blocked owners, malformed manifests, and missing descriptions should remain visible as compatibility or enablement warnings instead of being silently ignored.

### Icon provenance and remote assets

Plugin and skill icons are also untrusted input.

- Prefer approved official icon URLs or safe local manifest-relative raster assets.
- If icon provenance cannot be validated, AstraBridge should use a generated fallback icon under isolated runtime state such as `ASTRABRIDGE_CODEX_HOME/.astrabridge/registry-icons/**`.
- Remote icon fetching must not silently establish trust in the rest of a plugin or skill package.
- Generated fallback or unvalidated icon states should remain user-visible warnings so operators know they are not looking at an approved brand asset.

### Artifact retention and redaction

Plugin and skill evidence should be preserved, but only in redacted form.

- Keep plan/apply/smoke evidence under:
  - `PRIVATE/demo-runs/plugin-install-*`
  - `PRIVATE/demo-runs/plugin-skill-smoke-*`
  - isolated `ASTRABRIDGE_CODEX_HOME/astrabridge-managed/**` state when required for runtime bookkeeping
- Allowed durable metadata includes manifest paths, source catalog ids, declared MCP/apps/skills, warning codes, icon provenance, rollback metadata, and structured UI assertions.
- Not allowed in durable artifacts:
  - remote archive contents copied outside isolated roots
  - cookies
  - auth headers
  - raw secret-bearing manifest/config values
  - plaintext provider credentials embedded in plugin or skill evidence

### Required user-visible warnings

The product should make these risk categories visible to operators in UI and release evidence:

- plugin source is remote, curated, manual, or otherwise not implicitly trusted
- plugin manifest or skill manifest is malformed or incomplete
- icon provenance is generated fallback or otherwise unvalidated
- plugin declares MCP servers, apps, hooks, or skills that can introduce side effects
- skill enablement is blocked, inherited, disabled, or pending explicit approval
- skill content is operator-reviewed instructions, not trusted executable code

## Automation Safety

Automations inherit the same product isolation rules, with extra guardrails:

- default automation permission must stay on `read-only` or `workspace-write`
- `full-access` requires explicit `dangerous_opt_in=true`
- `full-access` runs must use dedicated worktree isolation rather than the current workspace
- automation subprocess env should forward only safe system env plus the selected provider env key
- automation stdout, stderr, summaries, URLs, manifests, and inbox items must be redacted before persistence
- finding or failure worktrees may be retained for review; no-signal worktrees may be cleaned automatically
- stale running runs must be marked failed and become explainable recovery evidence instead of remaining stuck forever
- retry/backoff and daily run limits must keep transient failure recovery bounded rather than creating unbounded spend loops

Automation evidence for release gates should be written only to:

- `PRIVATE/demo-runs/**`
- `<workspace>/.astrabridge/**`

The deterministic automation smoke path is:

- `scripts/run_automation_smoke.py`

Its outputs must remain sanitized and must not be staged from `PRIVATE/**`.

## Scanning Expectations

Before a release candidate or public push:

- run a secret scan excluding `PRIVATE/**`, `node_modules/**`, `dist/**`, and generated binaries
- run a legacy scan to confirm old project/state paths are not exposed as normal product behavior
- confirm official Codex config remains untouched

The release gate reference is [RELEASE_CHECKLIST.md](/D:/AstraBridge/docs/RELEASE_CHECKLIST.md).

Current operator entry points:

- [README.md](/D:/AstraBridge/README.md)
- [HANDOFF.md](/D:/AstraBridge/docs/HANDOFF.md)
- [Project Summary](/D:/AstraBridge/docs/PROJECT_SUMMARY.md)
- [Project Log](/D:/AstraBridge/docs/PROJECT_LOG.md)

## Operator Guidance

If a workflow fails:

- preserve secret-safe evidence
- prefer browser captures, supervisor status, and sanitized summaries over raw transport dumps
- use `docs/DEMO_RUNBOOK.md` and `docs/RELEASE_CHECKLIST.md` guidance for repeatable recovery checks

Do not solve failures by hand-editing `.astrabridge/` state unless a dedicated recovery tool explicitly requires it.
