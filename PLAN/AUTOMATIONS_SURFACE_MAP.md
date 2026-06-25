# Automations Surface Map

Last updated: 2026-06-25

## Scope

This document maps the Step 1-10 automation surface that AstraBridge now owns. It is the operator-facing index for routes, desktop panels, event types, storage locations, and explicit non-goals.

## Sidecar Routes

Read:

- `GET /api/automations`
- `GET /api/automations/runs?automation_id=...`
- `GET /api/automations/run?run_id=...`
- `GET /api/automations/inbox?automation_id=...&include_archived=true|false`
- `GET /api/automations/scheduler/status`

Write:

- `POST /api/automations/create`
- `POST /api/automations/update`
- `POST /api/automations/delete`
- `POST /api/automations/pause`
- `POST /api/automations/resume`
- `POST /api/automations/run-now`
- `POST /api/automations/runs/cancel`
- `POST /api/automations/inbox/update`
- `POST /api/automations/inbox/promote`

## Desktop Surfaces

Primary desktop entry point:

- `apps/astrabridge-desktop/src/App.tsx`
  - setup tab key: `automations`
  - query keys:
    - `["automations", projectId]`
    - `["automations-runs", projectId]`
    - `["automations-inbox", projectId]`
    - `["automations-scheduler", projectId]`

Main UI module:

- `apps/astrabridge-desktop/src/features/automations/AutomationsPanel.tsx`
  - automation list
  - create/edit form
  - schedule editor
  - runtime/profile/model/permission controls
  - workspace mode and cleanup policy controls
  - inbox/triage panel
  - run history panel
  - promote/archive/review actions

API client and type contracts:

- `apps/astrabridge-desktop/src/api.ts`
- `apps/astrabridge-desktop/src/types.ts`

## Event Types

The automation layer emits onto the existing runtime event surface. Current event types:

- `automation_scheduler_started`
- `automation_scheduler_stopped`
- `automation_created`
- `automation_updated`
- `automation_run_queued`
- `automation_run_started`
- `automation_run_progress`
- `automation_run_completed`
- `automation_run_failed`
- `automation_inbox_item_created`
- `automation_inbox_item_archived`
- `automation_promoted_to_task`

Planned-but-not-separate transport event names from the design contract:

- `automation_due`

`automation_due` is represented today by scheduler claim plus queue events rather than a separate public route.

## Storage Paths

Workspace-visible metadata:

- `<workspace>/.astrabridge/automations/automations.json`
- `<workspace>/.astrabridge/automations/runs/index.json`
- `<workspace>/.astrabridge/automations/inbox/index.json`

Runtime execution roots:

- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/automations/<automation-id>/<run-id>/manifest.json`
- `%APPDATA%/AstraBridge/runtime/<project-runtime-id>/automation-worktrees/<automation-id>/<run-id>/`

Related state roots resolved through `ProjectService`:

- `project_runtime_root`
- `codex_home_root`
- `downloads_root`
- `caches_root`
- `tmp_root`

## Execution Ownership

Current sidecar-owned modules:

- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/specs.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/store.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/scheduler.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/workspace.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/runner.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/triage.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/service.py`

## Security Boundaries

- No secret values should persist into automation specs, runs, inbox items, manifests, or reports.
- `full-access` is blocked unless `dangerous_opt_in=true` and workspace mode is `dedicated_worktree`.
- Automation subprocess env is filtered rather than inheriting the full desktop shell env.
- Finding/failure worktrees may be retained; no-signal worktrees may be cleaned depending on policy.

## Legacy And Non-goals

Out of scope for this 10-step loop:

- official Codex App private automation APIs
- writing normal product state into `~/.codex/config.toml` or project `.codex*`
- official OpenAI account login as a product auth path
- automatic merge/push on automation completion
- OS-native scheduling as the primary automation source of truth

Historical references may still exist in docs/tests as negative checks, but they are not valid current product paths.
