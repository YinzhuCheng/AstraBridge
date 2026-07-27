# Architecture

Last updated: 2026-07-27

## Public Product Boundary

Public product wording must follow
[OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md](OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md).
The core coding-runtime integration, external provider routes, and
GUI/code-facing orchestration contracts are distinct evidence layers:

- Codex CLI/app-server runtime patterns are integrated through AstraBridge-owned
  isolation, task, permission, and policy boundaries; this is not an official
  Codex App or official account-login path.
- External provider/model/endpoint routes are evidence-qualified and cannot
  acquire tool or coding-route authority from an OpenAI-compatible transport
  response alone.
- A deterministic graph import/export or code fixture result proves only its
  stated subset. It does not prove universal GUI/code parity or live provider
  behavior.

## Core Layers

AstraBridge currently has four practical layers:

1. Desktop UI
   - Tauri + React shell
   - user-facing project, chat, provider, runtime, extensions, capability, review, saves, dogfood, and automations surfaces
2. Sidecar
   - Python HTTP/JSON control plane
   - owns project state, provider/model APIs, capability routing, kernel compatibility probes, plugin/skill inventory, runtime supervision, checkpoints, browser-smoke helpers, and automation endpoints
3. Runtime
   - Codex-compatible execution paths plus AstraBridge native-kernel routing
   - app-owned isolated state rather than official Codex product state
4. Automation layer
   - sidecar-owned scheduler, store, runner, workspace isolation, and triage flow
   - desktop-owned create/edit/run/inbox surfaces

## Main Boundaries

Desktop is responsible for:

- project/task navigation and task-level conversation display
- provider/model selection
- runtime kernel status visibility
- plugin/skill inventory, install-plan preview/apply, enablement, and project preset surfaces
- capability route, smoke, artifact, MCP preset, and redacted credential management
- review and checkpoint surfaces
- automation setup, inbox triage, and run inspection

Sidecar is responsible for:

- `.abproj` and `.astrabridge/` project state
- provider/profile/model APIs
- kernel probe, compatibility snapshot, smoke, and matrix-gate support
- plugin/skill discovery, registry normalization, install planning/apply, enablement, and project preset state
- capability registry, route snapshots, dry-run smoke, artifact listing, and MCP preset config
- runtime orchestration and supervisor status
- automation CRUD, scheduler status, run history, inbox state, and promotion actions

Runtime is responsible for:

- bounded coding turns
- provider-thread execution
- isolated runtime roots
- event production consumed by supervisor and desktop

## Codex Kernel Compatibility Architecture

Kernel compatibility backend modules:

- `codex_kernel_probe.py`: binary locator and `--version` discovery across Windows and WSL
- `codex_app_server_probe.py`: read-only app-server protocol probe
- `codex_mcp_probe.py`: app-owned MCP visibility probe
- `codex_plugin_probe.py`: plugin discovery probe
- `codex_skill_probe.py`: skill discovery probe
- `codex_kernel_snapshot.py`: aggregated secret-free snapshot contract builder
- `codex_kernel_smoke.py`: deterministic no-key kernel smoke
- `codex_kernel_matrix_gate.py`: verification gate for compatibility matrix promotion

Kernel compatibility HTTP surface:

- `/api/runtime/kernel-probe`

Desktop kernel compatibility surface:

- setup tab `runtime`
- `RuntimeKernelStatusPanel`

Operator and evidence boundary:

- compatibility truth lives in [PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md](/D:/AstraBridge/PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md)
- kernel upgrade procedure lives in [docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md](/D:/AstraBridge/docs/CODEX_KERNEL_UPGRADE_RUNBOOK.md)
- preserved probe and smoke artifacts belong under `PRIVATE/demo-runs/codex-kernel-*`
- future agents should update the matrix only after matching probe and smoke evidence exists for the exact binary locator and lane

## Extensions Architecture

Extensions backend modules:

- `codex_plugin_skill_registry.py`: normalized plugin/skill inventory snapshot builder
- `codex_plugin_skill_icon_pipeline.py`: icon provenance and generated fallback path
- `codex_plugin_install_plan.py`: read-only install/update preview
- `codex_plugin_install_apply.py`: isolated plugin install/update executor with rollback snapshots
- `codex_skill_enablement.py`: global/project skill enablement state
- `codex_plugin_skill_project_presets.py`: project-local plugin/skill preset state
- `codex_plugin_install_smoke.py`: deterministic plugin install/update smoke
- `codex_plugin_skill_smoke.py`: deterministic plugin/skill inventory plus UI smoke

Extensions HTTP surface:

- `/api/runtime/plugin-skill-registry`
- `/api/runtime/plugin-install-plan`
- `/api/runtime/plugin-install-apply`
- `/api/runtime/skill-enablement`
- `/api/projects/plugin-skill-presets`

Desktop extensions surface:

- setup tab `extensions`
- `PluginSkillInventoryPanel`

Extensions boundary rules:

- plugin and skill discovery is metadata-first and must not imply trust or auto-enablement
- install/apply writes stay inside isolated Codex-home roots such as `plugins/`, `plugin-staging/`, and `plugin-rollbacks/`
- plugin-owned skills use explicit enablement flow; inventory alone must not activate them
- generated fallback icons and other unvalidated provenance stay visible to operators as warning-bearing metadata
- project plugin/skill presets stay separate from MCP preset routing and separate from official Codex project state

## Capability Runtime Architecture

Capability backend modules:

- `capabilities/specs.py`: capability contracts and adapter contracts
- `capabilities/capability_registry.py`: capability ids, standalone web lane, and provider/model candidates
- `capabilities/capability_routes.py`: saved route normalization and candidate resolution
- `capabilities/smoke.py`: deterministic no-key smoke fixtures and explicit provider-backed guard
- `capabilities/artifacts.py`: sanitized workspace-local artifact listing
- provider adapters such as image generation, vision analysis, speech transcription, and speech synthesis adapters
- `astrabridge_capabilities_mcp_server.py`: MCP-style runtime tools backed by capability routing

Capability HTTP surface:

- `/api/runtime/capability-management`
- `/api/runtime/capability-routes`
- `/api/runtime/capability-routes/save`
- `/api/runtime/capability-smoke`
- `/api/runtime/capability-artifacts`
- `/api/router/mcp/preset/astrabridge-capabilities`
- `/api/runtime/mcp/status`

Desktop capability surface:

- setup tab `capabilities`
- `CapabilityRoutesPanel`
- route controls, candidate details, dry-run smoke, recent artifacts, MCP preset health, runtime visibility, and redacted safety/credential states

Capability boundary rules:

- `web.search` is a standalone web lane and does not enter model-backed route selection.
- Image generation and web search legacy/direct interfaces remain available; the capability runtime adds a unified management and MCP-style tool layer.
- Provider-backed smoke or calls must be explicit and must never persist raw provider secrets.
- Automation attachment uses `runtime.mcp_preset_ids`, with `astrabridge_capabilities` discoverable as a controlled preset chip.

## Automation Architecture

Automation backend modules:

- `automations/specs.py`: normalized contracts and status rules
- `automations/store.py`: JSON persistence under `.astrabridge/automations/`
- `automations/scheduler.py`: due calculation, claiming, retries, and daily run limits
- `automations/workspace.py`: current-workspace vs dedicated-worktree execution roots
- `automations/runner.py`: standalone exec and thread wake-up adapter
- `automations/triage.py`: finding/no-signal/failure classification, manifests, inbox items
- `automations/service.py`: API-facing orchestration entry point

Automation HTTP surface:

- `/api/automations`
- `/api/automations/runs`
- `/api/automations/run`
- `/api/automations/inbox`
- `/api/automations/scheduler/status`
- create/update/delete/pause/resume/run-now/cancel/promote write routes

Desktop automation surface:

- setup tab `automations`
- `AutomationsPanel`
- list/form/inbox/run history panels

## Storage Model

Workspace-visible automation state:

- `<workspace>/.astrabridge/automations/automations.json`
- `<workspace>/.astrabridge/automations/runs/index.json`
- `<workspace>/.astrabridge/automations/inbox/index.json`

Runtime-owned large artifacts:

- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/automations/<automation-id>/<run-id>/`
- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/automation-worktrees/<automation-id>/<run-id>/`

Runtime-owned kernel and extensions state:

- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/codex_home/astrabridge-managed/skill-enablement.global.json`
- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/codex_home/plugins/`
- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/codex_home/plugin-staging/`
- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/codex_home/plugin-rollbacks/`
- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/codex_home/.astrabridge/registry-icons/`

Workspace-visible capability artifacts:

- `<workspace>/.astrabridge/capabilities/<capability-id-slug>/<artifact-id>/`

Preserved evidence roots:

- `PRIVATE/demo-runs/codex-kernel-smoke-*`
- `PRIVATE/demo-runs/plugin-install-*`
- `PRIVATE/demo-runs/plugin-skill-smoke-*`

## Project Model

- Project: workspace boundary plus `.abproj`.
- Task: user-visible work unit inside a project. A project contains many tasks.
- Conversation view: center-pane task transcript and activity surface. Chinese UI may call the composer/input control `对话框`, but `会话` must not be used as a task synonym.
- Execution lane: internal provider/model/runtime line inside a task, backed by a Codex runtime `thread_id`.
- Provider handoff: switching the active execution lane while staying in the same task.
- Branch task: a user-visible task created from an existing task's context.
- Save/Load: heavier file-state checkpoint.
- Automation: repeatable scheduled or manual runtime entry bound to the current project.

User navigation should present `Project -> Task`. Provider threads, Codex kernel thread ids, and handoff lanes remain internal runtime details. When multiple provider lanes exist for one task, the main conversation should merge them into the task-level conversation and show lane changes as activity rows rather than as separate left-sidebar conversations.

Codex CLI/app-server terminology must be adapted at the product boundary:

- Codex `new thread` maps to AstraBridge `new task`.
- Codex `fork thread` or `branch thread` maps to AstraBridge `branch task`.
- Codex `thread_id` remains an internal execution-lane identifier.
- Codex thread status/events are surfaced as task activity, diagnostics, or developer evidence.

## Legacy Compatibility Shims

Compatibility shims may exist only to keep older private imports or preserved evidence runnable. They must not become the implementation source of truth.

- Canonical web MCP implementation: `apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_web_mcp_server.py`
- Compatibility shim: `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_mcp_server.py`
- Canonical web service: `apps/astrabridge-sidecar/astrabridge_sidecar/web_tool_service.py`
- Compatibility service alias: `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_service.py`

When touching web-lane code or tests, import canonical `astrabridge_web_*` modules. Treat `lcr_*` modules as archived compatibility entry points only.

## Non-goals

The architecture deliberately does not treat these as normal product paths:

- official Codex `~/.codex/config.toml`
- project `.codex*`
- official OpenAI account login as a normal product path is not supported
- official Codex App private automation APIs
