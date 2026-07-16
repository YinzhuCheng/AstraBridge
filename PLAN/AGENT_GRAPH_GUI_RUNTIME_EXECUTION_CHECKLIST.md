# Agent Graph GUI Runtime Execution Checklist

## Purpose

This checklist is the concrete execution contract for the remaining GUI/runtime productization work owned by:

- `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`

Use this file together with those plans. This file does not replace them. It makes the remaining work directly handoffable, executable, and auditable by another agent without relying on chat history.

## Non-Negotiable Execution Contract

1. Work from the earliest incomplete numbered step in `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`, unless the user explicitly redirects.
2. Complete exactly one numbered step per turn.
3. For every UI-facing step, use the visible product surface in the in-app browser as the primary validation path.
4. Do not use hidden API mutation, store injection, direct console state mutation, or fixture preload tricks as acceptance evidence when a visible click path exists.
5. Use simulated clicks, typing, scrolling, expanding, collapsing, hovering, dragging, resizing, and reload/reopen flows.
6. Take screenshots frequently enough to catch obvious UI regressions:
   - starting state;
   - after each major interaction;
   - final state;
   - constrained-width or stressed-sidebar state when layout changed.
7. Preserve all evidence under `PRIVATE/agent-graph-dynamic-workflow/**`.
8. Do not persist secrets in logs, screenshots, reports, or artifacts.

## Required Evidence Layout

For each executed step, create:

- `PRIVATE/agent-graph-dynamic-workflow/<step-slug>/<YYYYMMDD>/step-report.md`
- `PRIVATE/agent-graph-dynamic-workflow/<step-slug>/<YYYYMMDD>/validation-note.md`
- `PRIVATE/agent-graph-dynamic-workflow/<step-slug>/<YYYYMMDD>/screenshots/`
- `PRIVATE/agent-graph-dynamic-workflow/<step-slug>/<YYYYMMDD>/commands.txt`

Recommended optional artifacts:

- `headless-*.png`
- `headless-*-actions.json`
- `dom-*.json`
- `run-*.json`
- `compiled-plan.json`
- `recovery-manifest.json`

## Required Validation Baseline

Unless a step proves these are irrelevant, run and preserve:

```powershell
node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx
node .\node_modules\typescript\bin\tsc --noEmit
```

Working directory:

```text
D:\AstraBridge\apps\astrabridge-desktop
```

## Step-Specific Acceptance Contract

### Step 8 - Build A Real Run Monitor Path

Required product path:

1. Open a representative task graph from the running app.
2. Enter graph mode from the visible UI.
3. Click at least one node and inspect node-scoped run state.
4. Click at least one edge and inspect edge-scoped handoff state.
5. Confirm runtime indicators stay compact on the canvas.

Required screenshots:

- graph default state with runtime indicators
- node selected with node run details
- edge selected with edge run details
- constrained-width pass

Do not mark complete unless:

- node and edge runtime inspection are both proven from the visible product path;
- tests pass or failures are concretely recorded;
- evidence distinguishes canvas indicators from inspector detail.

### Step 9 - Validate Cancellation, Retry, Resume, And Partial Rerun Through The GUI

Required product path:

1. Start a fixture run from the GUI.
2. Cancel a run through the GUI.
3. Trigger one recovery path through the GUI.
4. Show which nodes are rerun and which outputs are reused.

Do not mark complete unless:

- at least one cancel path and one recovery path are actually exercised;
- the mapping between GUI action and durable recovery artifacts is preserved.

### Step 10 - Create The Main-Agent Graph Operation Skill

Required deliverables:

- one repository-local skill or runbook;
- explicit rules for shallow orchestration, typed communication, secret safety, provider-call boundaries, and click-driven UI validation.

Do not mark complete unless:

- another agent can execute a representative graph task using only the skill/runbook plus repository files.

### Step 11 - Run End-To-End Fixture Dogfood From The Visible UI

Do not mark complete unless:

- one coherent end-to-end path is proven from authoring to execution to inspection to recovery;
- graph spec, compiled plan, run manifest, screenshots, and validation note are all preserved.

### Step 12 - Run Human-Approval Boundary Dogfood

Do not mark complete unless:

- approval boundary behavior is visibly understandable to an operator;
- durable run-state evidence matches the visible behavior.

### Step 13 - Package Templates, Reuse Paths, And Operator Documentation

Do not mark complete unless:

- at least one template instantiation path is click-validated;
- operator documentation matches actual product behavior.

### Step 14 - Final Verification Gate And Release Handoff

Do not mark complete unless:

- future agents can resume work without reconstructing chat history;
- the final report clearly separates proven, blocked, and deferred paths.

## Plan Update Protocol

After each completed step:

1. Update `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`.
2. Update `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`.
3. If the route changed, record a short plan-review entry with evidence, diagnosis, route change, preserved quality bar, and exact next step.

## Refusal Conditions

Pause and record a blocker instead of claiming completion when:

- the visible product path is broken and only API-side validation works;
- screenshots cannot prove the claimed UI outcome;
- test failures remain unexplained;
- the work drifts into polish while required runtime behavior is still absent;
- a step would require unauthorized provider-backed or paid execution.
