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
5. Revisit right-sidebar panes, shared API/UI state, and project file browser from the previous LCR plan.
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

- Full inherited sidecar unittest suite still needs migration cleanup. Current failures are mostly stale LCR assertions (`.lcr`, `vault.lcrvault`, old asset-context wording), old legacy `.codexproj` behavior, and test environment assumptions around `ASTRABRIDGE_CODEX_HOME`.
- Windows `node` is not on the current shell PATH, so desktop TypeScript/Vite build was not run in this session.

Recommended next test work:

1. Add a test fixture that sets both `ASTRABRIDGE_APPDATA` and `ASTRABRIDGE_CODEX_HOME` to temp paths for every sidecar test.
2. Rename stale `.lcr` expectations to `.astrabridge` except explicit legacy-import tests.
3. Rewrite legacy project tests around explicit `.lcrproj/.lcr` import, not old `.codexproj` auto-migration unless the product keeps that path.
4. Install desktop dependencies in the new repo and run `npm run build`.
