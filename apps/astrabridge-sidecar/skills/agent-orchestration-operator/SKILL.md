---
name: agent-orchestration-operator
description: Design, modify, validate, and operate bounded AstraBridge Agent Graph workflows through the canonical graph contract, code-first graph files, fixture or dry-run validation, and click-verified GUI execution. Use when AstraBridge needs a reusable graph-backed workflow instead of a single-agent task, when an existing task graph or orchestration graph must be migrated or changed, when subagent policies or typed handoff rules must be reviewed, or when a graph-backed runtime path must be proven in the real app without relying on API-only shortcuts.
---

# Agent Orchestration Operator

Use this skill to handle AstraBridge Agent Graph work without rebuilding the operating rules from chat history.

This skill is for bounded orchestration work. It is not a license to create deep recursive agent stacks, mutate runtime state ad hoc, bypass the canonical graph contract, or claim GUI success from backend traces alone.

## Read Before Acting

1. Read `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md` when the task is executing the active durable Agent Graph plan.
2. Read `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md` when the task is advancing the GUI/runtime execution path.
3. Read `PLAN/AGENT_GRAPH_GUI_RUNTIME_EXECUTION_CHECKLIST.md` when the task touches visible UI, run inspection, cancellation, or recovery behavior.
4. Read `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`.
5. Read `references/operating-surfaces.md`.

## Preserve First

1. Preserve `PRIVATE/**`, run manifests, dry-run bundles, screenshots, validation notes, and recovery artifacts by default.
2. Never persist API keys, bearer tokens, cookies, auth headers, vault contents, desktop plaintext key contents, or provider raw secrets.
3. Treat the visible in-app browser surface as the acceptance path whenever the product already exposes the workflow there.

## Decision Rules

### Stay Single-Agent By Default

Do not introduce orchestration when one agent can complete the task with ordinary tools and normal review discipline.

Prefer a single agent when:

- the task is a straightforward code change, document edit, or one-pass investigation;
- the work does not need explicit artifact handoff or intermediate review contracts;
- the value of the graph would be only cosmetic.

### Use Orchestration Only When It Adds Real Structure

Use a graph when at least one of these is true:

- the workflow naturally splits into planner, worker, validator, reviewer, or synthesizer lanes;
- artifact handoff needs to be explicit and reviewable;
- a gate, approval dependency, or bounded branch merge is part of the real workflow;
- the user needs a reusable template or graph file that can be linted, diffed, dry-run, imported, exported, and replayed later.

### Depth And Safety Limits

1. Default to shallow orchestration:
   - one supervisor or planner layer,
   - one or more workers,
   - optional validator, reviewer, synthesizer, or gate.
2. Treat graph depth `2` as the default maximum.
3. Require explicit user approval and a recorded reason before designing or promoting depth greater than `2`.
4. Require explicit user approval before enabling:
   - risky filesystem writes,
   - dependency installation,
   - external writes,
   - live provider execution,
   - broad or unclear permission escalation.
5. Keep context isolation explicit:
   - do not pass full conversation history across edges by default;
   - do not share private scratchpads, provider reasoning, or unrelated worker outputs unless the edge contract allows a sanitized summary or artifact;
   - do not weaken `exclude_private_memory=true` expectations without an explicit reason.

## Canonical Surfaces

Use existing repository surfaces instead of inventing parallel graph logic:

- Active durable plans:
  - `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
  - `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`
  - `PLAN/AGENT_GRAPH_GUI_RUNTIME_EXECUTION_CHECKLIST.md`
- Canonical contract: `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`
- CLI entrypoint: `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py`
- Task-graph runtime and recovery surface:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- Task-graph contract and fixtures:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`
- Example graphs:
  - `examples/agent-orchestration/code_fix_review.json`
  - `examples/agent-orchestration/provider_update_smoke.json`
  - `examples/agent-orchestration/fanout_research_synthesis.json`
- Product workspace:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`

Do not claim orchestration support by mutating runtime state directly when the canonical graph file, sidecar runtime, or visible UI already provides the right path.

## Standard Workflow

### 1. Choose The Working Mode

Choose one of these and say which one you are using:

- `design_new_graph`
- `modify_existing_graph`
- `review_existing_graph`
- `operate_existing_graph`
- `repair_runtime_compatibility`

### 2. Start From A Canonical Graph File

When possible, start from one of these instead of inventing graph JSON from scratch:

- an existing example graph;
- an exported canonical orchestration graph file;
- the current task graph as rendered by the app and exported or inspected through the sidecar.

Use code-first graph files as the source of truth for reviewable changes. The graph file should be the thing that gets linted, dry-run validated, diffed, imported, exported, and rolled back.

If the task starts from an older saved task graph, treat migration and compatibility repair as first-class work instead of hand-editing runtime memory.

### 3. Validate Before Any Live Operation

Run the canonical checks from `apps/astrabridge-sidecar`:

```powershell
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli lint <graph.json>
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli dry-run <graph.json>
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli diff <old-graph.json> <new-graph.json>
```

Rules:

1. Run `lint` after any meaningful graph edit.
2. Run `dry-run` before claiming the graph is ready for runtime use.
3. Run `diff` whenever the task involves changing an existing graph or template.
4. Do not skip `dry-run` just because the graph "looks right".
5. When runtime compatibility is the issue, add the smallest focused automated regression that proves the repaired path.

For task-graph runtime work, prefer focused validations such as:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_task_graph_worker_runtime.py -k "<focused-case>"
.\.venv\Scripts\python.exe -m pytest tests/test_task_graph_api.py -k "<focused-case>"
```

### 4. Keep UI Proof Separate From Backend Proof

When the task changes visible product behavior:

1. Use the in-app browser as the primary proof surface when the app is already running there.
2. Operate the real surface by visible clicks, typing, dragging, hover, scroll, expand/collapse, and reload.
3. Capture screenshots before the change, during the interaction path, after the expected change, and after reopen or reload.
4. Inspect those screenshots during the step, not only at the end.
5. Explicitly call out card stacking, oversized fonts, low-semantic text, redundant metadata, detached controls, unclear icons, cramped inspectors, and wasted canvas area.
6. Do not count API calls, store mutation, fixture preload, or `page.evaluate(...)` state mutation as GUI acceptance evidence when a click path exists.
7. When graph runtime is involved, prefer a visible operator path like:
   - `任务图`
   - run fixture or dry-run control
   - inspector open
   - run inspection workspace
   - cancel, recover, rerun, partial rerun, or approval action
   - return to conversation
   - reopen graph
8. If Playwright click reliability is poor on the shell layer, use visible-coordinate clicks against the real rendered controls and preserve screenshots showing the target state.

When the task is backend-only or skill-only, say that clearly and keep UI claims narrow.

### 5. Record Approval Boundaries

Before promoting a graph for real use, record:

- whether depth is still within the shallow default,
- whether any node can write code or install dependencies,
- whether any edge or node requires human approval,
- whether live provider execution is still disabled or explicitly approved.

## Standard Recipes

### Recipe: Create Or Tailor A Graph

1. Start from an example graph or exported graph file.
2. Rename graph title, node labels, and task-specific prompt templates.
3. Tighten output schemas, artifact expectations, and handoff contracts.
4. Run `lint`.
5. Run `dry-run`.
6. If replacing an existing graph, preserve a `diff`.
7. Import or instantiate in the app only after the contract-level checks pass.

### Recipe: Migrate Or Repair A Legacy Graph

1. Start from the saved task graph or exported graph that exhibits the failure.
2. Identify whether the failure is in:
   - contract shape,
   - orchestration graph sync,
   - runtime policy defaults,
   - GUI-only rendering,
   - or artifact loading.
3. Repair the smallest canonical surface.
4. Add a focused regression test for the exact legacy failure mode.
5. Re-run the focused test plus any nearby contract or API coverage.
6. Only then return to visible GUI validation.

### Recipe: Dry-Run And Fixture Validation

1. Run canonical `lint`.
2. Run canonical `dry-run`.
3. If runtime behavior matters, run a fixture path through the app or sidecar.
4. Preserve:
   - command outputs,
   - dry-run summary,
   - compiled plan,
   - run manifest,
   - validation note.

### Recipe: GUI Cancel And Recovery Validation

1. Open the app in the in-app browser.
2. Enter `任务图`.
3. Start a fixture run from visible controls.
4. Open the inspector.
5. Switch to the run-inspection workspace.
6. Cancel the run through the visible button.
7. Expand the visible recovery section.
8. Trigger one recovery path such as `Resume run`.
9. Capture the rerun and reused state from the visible UI.
10. Return to conversation and reopen `任务图` to confirm the recovered state persists.

### Recipe: Evidence Preservation

For UI-facing graph work, preserve:

- `step-report.md`
- `validation-note.md`
- `commands.txt`
- `screenshots/`
- any `recovery-summary.json`, run manifest, diff report, or compiled-plan artifact required by the step

Default artifact root:

- `PRIVATE/agent-graph-dynamic-workflow/<step-slug>/<YYYYMMDD>/`

## Code-First Examples

### Example: Tailor A New Graph From The Code-Fix Example

1. Copy `examples/agent-orchestration/code_fix_review.json` to a task-local or evidence-local graph file.
2. Rename `graph_id`, `title`, and any node labels that must become task-specific.
3. Tighten prompt templates, schemas, and handoff contracts to the current task.
4. Run:

```powershell
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli lint <graph.json>
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli dry-run <graph.json>
```

5. Only after those pass should you import or instantiate the graph in the app.

### Example: Modify An Existing Provider-Update Graph

1. Start from `examples/agent-orchestration/provider_update_smoke.json` or an exported graph file.
2. Adjust only the relevant nodes, edges, or prompt contracts.
3. Preserve a before/after diff:

```powershell
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli diff <old-graph.json> <new-graph.json>
```

4. Re-run `lint` and `dry-run`.
5. If the graph changes visible product behavior, prove that path from the real app with screenshots.

## Output Expectations

When using this skill, produce artifacts that another agent can review and continue:

- the plan step that owns the work,
- the graph file path,
- lint output,
- dry-run output,
- diff output when relevant,
- focused regression output when runtime compatibility changed,
- run id and run artifact paths when fixture or recovery execution occurred,
- screenshot evidence paths for visible product work,
- the exact approval boundary still in force,
- the exact next step.

## Forbidden Shortcuts

Do not:

- replace canonical graph files with hidden runtime mutation;
- claim GUI success from backend responses alone;
- introduce depth greater than `2` without user approval;
- enable risky permissions or live provider execution without explicit approval;
- weaken typed handoff or context-isolation rules just to make a graph pass quickly;
- skip visible reopen or reload verification when the step claims persisted GUI behavior;
- leak secrets into graph files, screenshots, notes, or validation artifacts.
