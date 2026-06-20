# AstraBridge Product Stabilization Handoff

This is the first execution plan for agents continuing AstraBridge after the product split from Local Codex Router.

The split is complete enough to stop using the old Research OS thread for feature development. Future work should happen inside `D:\AstraBridge`.

## Mission

Stabilize AstraBridge as an independent product before resuming game dogfood or adding major features.

AstraBridge is a local multi-provider coding-agent workbench based on Codex CLI/app-server runtime patterns. It is not the official Codex App. OpenAI is supported only as an API-key provider, not through official account login.

## Non-Negotiable Product Rules

- New project files use `.abproj`.
- New workspace state uses `.astrabridge/`.
- Do not create or import `.lcrproj`, `.lcr/`, `.codexproj`, `.codex-shell/`, or project `.codex*` state.
- Do not write official Codex `~/.codex/config.toml` during normal app use.
- Do not reintroduce `openai_account`, `openai-account`, `codex_managed_auth`, or official OpenAI account login UI.
- Do not commit real provider keys, bearer tokens, cookies, auth headers, vault files, raw provider responses, or screenshots containing secrets.
- `PRIVATE/**` is local private property and ignored by git except `PRIVATE/README.md`.

## Current Baseline

Completed in the migration session:

- Active predecessor source copied into:
  - `apps/astrabridge-desktop`
  - `apps/astrabridge-sidecar`
- Product identity changed to `AstraBridge 星桥`.
- Tauri identifier changed to `app.astrabridge.desktop`.
- Sidecar package/module renamed to `astrabridge_sidecar`.
- New constants smoke passed for `.abproj`, `.astrabridge`, `astrabridge-project-v1`, AstraBridge appdata, and AstraBridge CODEX_HOME overrides.
- Static scan passed for absence of official-account login strings in `apps/`.
- Python AST parse passed for sidecar source.
- JSON parse passed for Tauri config and desktop package metadata.
- Local git repo initialized.

Known not-yet-green items:

- Full inherited sidecar unittest suite still fails after rename.
- Desktop TypeScript/Vite build was not run because Node was not available in the previous shell PATH and dependencies were intentionally not copied.
- PyInstaller sidecar build and Tauri NSIS installer have not been run in the new repo.
- Clean-user install/uninstall and official Codex non-interference checks have not been run.

## Phase 0: Guardrails Before Coding

Before changing code, run:

```powershell
cd D:\AstraBridge
git status --short
rg -n "openai_account|openai-account|codex_managed_auth|Use OpenAI official|OpenAI official" apps
rg -n -- "PROJECT_FILE_SUFFIX = \"\.lcrproj\"|WORKSPACE_STATE_DIRNAME = \"\.lcr\"|vault\.lcrvault|productName.*Local|identifier.*local\.codex|\.codexproj|\.codex-shell" apps
```

Expected:

- `git status --short` is clean unless you intentionally changed files.
- official account login scan has no matches.
- legacy project/state scan has no product-path matches except explicit rejection tests.

If these scans fail, fix before continuing.

## Phase 1: Test Fixture Migration

Goal: make sidecar tests run against temp AstraBridge appdata and CODEX_HOME, never real user appdata.

Tasks:

1. Add a shared test fixture/helper that sets both:
   - `ASTRABRIDGE_APPDATA`
   - `ASTRABRIDGE_CODEX_HOME`
2. Ensure tests never write to:
   - `%APPDATA%/AstraBridge`
   - `%LOCALAPPDATA%/AstraBridge`
   - official Codex `~/.codex`
3. Replace stale path assertions:
   - old state-directory expectations -> `.astrabridge/`.
   - `vault.lcrvault` -> `vault.abvault`.
   - Keep old project/state names only in explicit rejection tests.
4. Update legacy project tests:
   - Product behavior should reject `.lcrproj`, `.lcr`, `.codexproj`, and `.codex-shell`; recreate AstraBridge projects from backups when needed.
   - Do not keep old `.codexproj` auto-migration.
5. Re-run:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m unittest discover -s tests -p test_sidecar_services.py
```

Acceptance:

- Sidecar tests pass or remaining failures are real product bugs, not rename/test-fixture fallout.
- No test writes into real appdata or official Codex config.

## Phase 2: Runtime And Project-State Smoke

Goal: prove AstraBridge can create and open a project using new state names.

Tasks:

1. Add/repair tests for project create/open:
   - project file suffix `.abproj`
   - workspace state `.astrabridge/`
   - schema `astrabridge-project-v1`
2. Verify old project formats are rejected:
   - `.lcrproj` and `.codexproj` inputs fail without writing a migrated `.abproj`.
   - `.lcr` and `.codex-shell` directories are not copied into `.astrabridge`.
3. Verify no `.codex*` project files are created.
4. Verify app-owned CODEX_HOME is under AstraBridge naming.

Acceptance:

- New project smoke passes.
- Legacy rejection smoke is explicit and documented.
- official Codex config timestamp unchanged during smoke.

## Phase 3: Desktop Dependency And Build

Goal: get the desktop app building in the new repo.

Tasks:

1. Confirm Node/npm availability. If not available, follow the project bootstrap docs or install Node through an explicit user-approved route.
2. Install dependencies:

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
npm install
```

3. Run:

```powershell
npm run build
```

4. Fix TypeScript/import/name fallout.
5. Confirm Tauri config points to:
   - productName `AstraBridge`
   - identifier `app.astrabridge.desktop`
   - sidecar resource `astrabridge-sidecar/astrabridge-sidecar.exe`

Acceptance:

- `npm run build` passes.
- UI has no user-facing Local Codex Router branding except migration docs.
- Official OpenAI account login button/text is absent.

## Phase 4: Sidecar Packaging

Goal: build the new sidecar binary with AstraBridge naming.

Tasks:

1. From `apps/astrabridge-sidecar`, build PyInstaller output:

```powershell
pyinstaller astrabridge-sidecar.spec
```

2. Confirm output path:
   - `apps/astrabridge-sidecar/dist/astrabridge-sidecar.exe`
3. Run a minimal server launch smoke on a non-conflicting port.
4. Confirm server reports AstraBridge app state and no old appdata paths for new state.

Acceptance:

- `astrabridge-sidecar.exe` exists.
- Server starts and responds to health/admin session APIs.
- No provider key is required for this smoke.

## Phase 5: Installer Build And Clean Install

Goal: build and test a Windows installer without touching official Codex.

Tasks:

1. Build Tauri NSIS installer from `apps/astrabridge-desktop`.
2. Install as current user.
3. First launch checks:
   - UI title says AstraBridge.
   - LLM API Manager has no official OpenAI account login path.
   - dependency/runtime setup pages use AstraBridge wording.
4. Create a test project and verify:
   - `.abproj`
   - `.astrabridge/`
   - no `.lcr`, `.lcrproj`, `.codex`, `.codexproj`, `.codex-shell`
5. Uninstall/reinstall smoke.

Acceptance:

- NSIS installer product name is AstraBridge.
- install/uninstall does not delete official Codex, WSL, Node, provider vaults, or user project files.
- official Codex `~/.codex/config.toml` timestamp unchanged.

## Phase 6: Provider And Secret Handling Regression

Goal: confirm the API-key provider model works after official-account removal.

Tasks:

1. Anonymous mode:
   - provider metadata visible.
   - user must paste key or use env var.
   - pasted/session key is not persisted after app exit.
2. Managed mode:
   - encrypted vault creates `vault.abvault`.
   - multiple provider keys per provider supported.
   - key fingerprint visible, secret never visible.
3. OpenAI API key provider:
   - OpenAI appears as a normal provider profile.
   - no official account login flow.
4. Secret scan:

```powershell
rg -n "Authorization: Bearer|sk-|api[_-]?key|cookie|token" D:\AstraBridge --glob '!PRIVATE/**' --glob '!node_modules/**' --glob '!dist/**'
```

Acceptance:

- No real secrets in tracked files.
- OpenAI API-key provider remains usable as ordinary provider metadata.
- official account mode remains absent.

## Phase 7: Product UI Stabilization Backlog

After tests/build/install are stable, implement these user-facing features from the product backlog:

1. Right sidebar switcher:
   - Status / Goal / Plan
   - Review recent file changes
   - Terminal / CLI surface
   - In-app browser
   - Project files tree and preview for text, Markdown, PDFs, images, and common source files
2. Settings UI cleanup:
   - LLM API Manager should not look like card soup.
   - Use compact tabs/navigation, calmer typography, fewer boxes.
   - Keep provider/model/key/MCP metadata clear and accessible.
3. API-driven operation with shared UI state:
   - Agent/API operations should update the same visible task/project state as the web UI.
   - Add websocket/SSE or polling invalidation as needed.
   - UI should show provider switch, plan update, tool events, save/load, and browser smoke caused by API calls.
4. Multi-provider task continuity:
   - New Chat = new task.
   - Provider switch = internal provider-thread handoff inside the same visible task.
   - Fork = official branch exploration semantics.
   - Save/Load = heavier workspace checkpoint.

Do not start this backlog until Phases 1-6 are stable enough for a new engineer to trust the app.

## Phase 8: Dogfood Re-entry Gate

Only resume game or coding dogfood after:

- Sidecar tests pass or known failures are explicitly waived.
- Desktop build passes.
- Sidecar binary and installer build pass.
- Clean project smoke creates only `.abproj/.astrabridge`.
- Provider secrets stay out of git/project state.
- Official Codex config non-interference check passes.

When dogfood resumes, use it to find AstraBridge bugs, not to hand-code the target app manually.

## Completion Definition For Stabilization

AstraBridge is ready for the next productization phase when a fresh engineer can:

1. Clone/open `D:\AstraBridge`.
2. Read `README.md`, `HANDOFF.md`, this plan, and `docs/RELEASE_CHECKLIST.md`.
3. Install dependencies.
4. Run sidecar tests.
5. Build desktop.
6. Build installer.
7. Create a new local project with `.abproj/.astrabridge`.
8. Configure at least one API-key provider without any official account login path.
9. Verify no official Codex state is modified.
