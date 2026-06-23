# AstraBridge Handoff

## Product Identity

- Product name: AstraBridge 鏄熸ˉ
- Positioning: a local multi-provider coding-agent workbench based on Codex CLI/app-server runtime patterns.
- Non-goal: being the official Codex App or depending on official OpenAI account login.

## What Was Copied

- `apps/codex-shell-desktop` -> `apps/astrabridge-desktop`
- `apps/codex-shell-sidecar` -> `apps/astrabridge-sidecar`

Excluded: dependencies, build outputs, caches, dogfood artifacts, runtime logs, and secrets.

## Current Architecture

- Desktop: Tauri + React + Zustand/TanStack Query.
- Sidecar: Python service owning project/profile/runtime/tool APIs.
- Runtime: Codex app-server compatible execution through app-owned isolated state.
- Provider policy: API-key providers only; OpenAI is handled like any other compatible provider.

## Important Gaps To Close Next

1. Re-run the full unit test suite after dependency install in the new repo.
2. Finish product-name cleanup for all UI copy and tests.
3. Verify Tauri bundle resource paths for `astrabridge-sidecar.exe`.
4. Run clean-user install/uninstall checks.
5. Revisit right-sidebar panes, shared API/UI state, and project file browser from the previous productization plan.
6. Resume dogfood projects only after AstraBridge project state and provider handoff pass regression tests.

## Safety Rules

- Do not copy real Desktop key files into this repo.
- Do not write official Codex `~/.codex/config.toml` during normal use.
- Do not create project `.codex*` files.
- Do not reintroduce `openai_account` as a user session mode.

## Validation Status From Migration Session

Passed:

- `openai_account`, `openai-account`, `codex_managed_auth`, and `Use OpenAI official` are absent from `apps/`.
- Project constants smoke passed: `.abproj`, `.astrabridge`, `astrabridge-project-v1`, `AstraBridge` app data, and AstraBridge CODEX_HOME env overrides.
- Python AST parse passed for sidecar source.
- Tauri and package JSON parse passed.
- Local git repository initialized and committed.

Not yet green:

- Earlier legacy migration failures are resolved. Current periodic checks should continue to run both full sidecar and desktop suites before major branch merges.

Recommended next test work:

1. Add a test fixture that sets both `ASTRABRIDGE_APPDATA` and `ASTRABRIDGE_CODEX_HOME` to temp paths for every sidecar test.
2. Keep stale state-directory expectations aligned to `.astrabridge` in any new or touched migration tests.
3. Rewrite legacy project tests around explicit rejection of old project formats; AstraBridge no longer imports `.lcrproj`, `.lcr`, `.codexproj`, or `.codex-shell` state.
4. Keep provider/profile truth drift checks active around catalog/prefs and runtime/router usage.
## Private credentials handoff

AstraBridge can point developers to local private-property credential locations, but actual secrets must remain outside public git history.

- See `PRIVATE/README.md` for local-only paths and rules.
- Store durable provider keys in the encrypted app vault when possible: `%APPDATA%/AstraBridge/llm_api_manager/users/<username>/vault.abvault`.
- Use environment variables for automation or CI-like local runs.
- Never push `PRIVATE/secrets/`, real provider keys, `Authorization` headers, cookies, bearer tokens, or raw provider responses to a public remote.
## Current operator baseline

The old stabilization handoff is no longer the only useful planning entrypoint. Current operators should use these as the active baseline:

- [PLAN/30_NEAR_TERM_PRODUCT_FOCUS_AND_NON_TRIVIAL_PRIORITIES.md](/D:/AstraBridge/PLAN/30_NEAR_TERM_PRODUCT_FOCUS_AND_NON_TRIVIAL_PRIORITIES.md)
- [docs/DEMO_RUNBOOK.md](/D:/AstraBridge/docs/DEMO_RUNBOOK.md)
- [docs/SECURITY_AND_ISOLATION.md](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)
- [docs/RELEASE_CHECKLIST.md](/D:/AstraBridge/docs/RELEASE_CHECKLIST.md)

`PLAN/02_PRODUCT_STABILIZATION_HANDOFF.md` remains useful as historical context, but it is no longer the main operator handoff for product-ready work.
