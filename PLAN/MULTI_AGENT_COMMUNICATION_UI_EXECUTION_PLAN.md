# Multi Agent Communication UI Execution Plan

## Total Objective

Turn AstraBridge's existing subagent, task-graph, artifact, and runtime-lane primitives into a product-grade multi-agent communication system that ordinary users can operate from the GUI: drag tasks, assign roles, inspect handoffs, review safety gates, and understand execution state through real click-driven flows rather than internal-only automation.

## Deliverables

- A durable product plan for turning current multi-agent prototypes into a user-facing workflow system.
- A concrete execution sequence that future agents can continue one step at a time without reconstructing chat history.
- Mandatory click-driven validation rules that force every GUI-facing slice to be exercised through simulated user actions in the in-app browser.

## Constraints And Attention Notes

1. Keep `Project -> Task` as the top-level user boundary. Subagents, worker threads, provider lanes, and handoff mechanics stay internal unless intentionally surfaced as workflow concepts.
2. Use structured contracts for inter-agent communication: node definitions, envelopes, artifact refs, context policy, run state, and review state. Do not depend on raw chat history as durable machine state.
3. Preserve artifacts, traces, screenshots, validation notes, raw summaries, and diagnostic records under `PRIVATE/**` by default. Do not clean them unless the user explicitly names cleanup targets.
4. Do not persist secrets, vault values, API keys, tokens, cookies, auth headers, or plaintext desktop key material in plans, code, screenshots, reports, or evidence packs.
5. Every GUI-affecting step must be validated through simulated clicks in the in-app browser against the running app. Direct API calls may help diagnose issues, but they do not satisfy UX acceptance on their own.
6. The plan must bias toward user-friendly behavior: visible status, recoverable errors, explicit approvals, inspectable artifacts, and low-friction task assignment.
7. Prefer extending the existing task-graph and worker-lane foundations already in the repository over inventing a parallel orchestration product.

## Adjustment Policy

Agents may reasonably adjust filenames, substeps, sequencing, commands, implementation details, and evidence paths when repository facts require it. Adjustments must not change the total objective, weaken safety boundaries, skip simulated-click validation, or replace user-facing workflow work with backend-only scaffolding. If a core objective becomes infeasible, record the blocker, evidence, attempted approaches, and a substitute path that preserves the original intent.

## Execution Rules

1. Each execution turn should complete one numbered step unless the user explicitly asks otherwise.
2. Each turn must begin by reading this plan and the related files needed for the current step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all of its acceptance criteria are satisfied.
5. For every GUI-facing step, the validating agent must use the in-app browser to simulate actual clicks, drags, and selections. Evidence must include screenshots and a short validation note under `PRIVATE/**`.
6. If a UI action only works through direct API calls, keyboard shortcuts, or developer tools but not through simulated clicks, the step is not complete.
7. If blocked, record the exact blocker, evidence, attempted paths, and next-step entry point.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Inventory Existing Multi-Agent Primitives
- Next step: Step 1, Inventory Existing Multi-Agent Primitives
- Last updated: 2026-07-07

## Execution Steps

### 0. Create Durable Plan

Goal: Create this plan and make the next entry point unambiguous.

Main actions:

- Define the concrete product objective.
- Record constraints, adjustment policy, execution rules, step sequence, and acceptance criteria.
- Make simulated-click validation mandatory for GUI-facing work.

Acceptance criteria:

- Plan file exists on disk.
- Plan contains objective, constraints, adjustment policy, execution rules, current progress, numbered steps, and progress log.
- The next step is clearly identified.

Status: completed

### 1. Inventory Existing Multi-Agent Primitives

Goal: Establish what AstraBridge and the Codex runtime already provide so future work reuses real primitives instead of rebuilding them.

Main actions:

- Audit current task-graph, worker-lane, artifact, approval, and runtime-thread code paths in sidecar and desktop.
- Record what already exists for subagent spawning, parent-child linkage, artifact-first handoff, review gates, and cancellation.
- Map any usable Codex subagent concepts that are already represented in generated protocol files or runtime adapters.

Acceptance criteria:

- An inventory artifact exists under `PLAN/` or `docs/` with file-level references.
- The artifact distinguishes reusable primitives, missing primitives, and misleading half-complete surfaces.
- The next implementation step is obvious from the inventory.

Status: not started

### 2. Freeze The Product Slice And User Journeys

Goal: Decide exactly which user-visible workflows this system will support first.

Main actions:

- Define the initial supported journeys: task decomposition, role assignment, artifact-based handoff, approval gating, cancellation, and recovery.
- Define explicit non-goals for v1, such as generic swarm chat, autonomous external writeback, and invisible cross-task memory sharing.
- Write target user journeys from the GUI point of view, not just backend capabilities.

Acceptance criteria:

- A scope artifact exists on disk.
- The artifact names supported journeys, exclusions, and UX principles.
- Every supported journey can be expressed as a concrete click path in the running app.

Status: not started

### 3. Normalize The Communication Contract

Goal: Make inter-agent communication durable, provider-agnostic, and inspectable.

Main actions:

- Define or refine the structured contract for task assignment, message envelope, context policy, artifact refs, machine result, and review state.
- Separate human-readable summaries from machine-consumable state.
- Ensure the contract supports both internal worker lanes and later external A2A-style expansion without changing the task boundary.

Acceptance criteria:

- Contract artifacts or schema definitions exist on disk.
- The contract is sufficient for task assignment, artifact handoff, review gating, and cancellation recovery.
- Tests or validators reject invalid or underspecified communication objects.

Status: not started

### 4. Build Task-Assignment And Handoff APIs

Goal: Expose backend entry points for assigning work, routing bounded context, and recording structured results.

Main actions:

- Add or refine sidecar APIs for task assignment, worker creation, structured handoff, and task-graph run updates.
- Ensure every worker run records parent-child lineage, context policy, artifacts, and status.
- Preserve diagnostics for assignment failure, routing failure, and schema mismatch.

Acceptance criteria:

- APIs exist and are covered by focused tests.
- A worker can be assigned bounded work without inheriting full raw history by default.
- Failed assignments produce durable, secret-free diagnostic artifacts.

Status: not started

### 5. Surface Assignment And Communication In The GUI

Goal: Let users create and inspect multi-agent work allocation from the desktop app.

Main actions:

- Add GUI surfaces for adding workers, assigning roles, and wiring dependencies or handoff paths.
- Make communication and context policy visible in the inspector rather than hidden in code-only state.
- Keep the UI dense and operational, with stable dimensions and clear controls.

Acceptance criteria:

- Users can assign at least one worker role and inspect its planned input/output contract from the GUI.
- The visible state persists after reload.
- A simulated-click flow proves the user can perform the assignment without falling back to direct API calls.

Status: not started

### 6. Add Drag-And-Drop Task Allocation

Goal: Make the system feel like a real orchestration tool rather than a static detail panel.

Main actions:

- Support drag-and-drop or equivalent direct-manipulation placement and reassignment for task nodes.
- Add clear visual feedback for ownership, dependencies, and blocked states.
- Ensure the controls are usable in realistic viewport sizes without overlap or hidden hit targets.

Acceptance criteria:

- A user can drag or reassign task nodes and see the new state persist.
- Task ownership and dependency changes are reflected in structured task state.
- Simulated-click-and-drag validation proves the interaction works in the running app.

Status: not started

### 7. Add Artifact-First Communication Review

Goal: Make handoffs inspectable and auditable for users.

Main actions:

- Add GUI review surfaces for worker output bundles, summaries, machine results, and downstream handoff payloads.
- Show what context will flow to the next worker and what is intentionally excluded.
- Preserve previewable artifacts and review notes under task-owned paths.

Acceptance criteria:

- Users can open a worker's artifacts and inspect its downstream handoff payload from the GUI.
- Handoff previews reflect the active context policy rather than raw full-history dumps.
- Simulated-click validation proves artifact review works through visible controls.

Status: not started

### 8. Add Human Review, Safety Gates, And Rollback Cues

Goal: Keep multi-agent orchestration usable without becoming unsafe or opaque.

Main actions:

- Surface approvals for high-risk actions such as source mutation, installs, paid provider calls, and external writeback.
- Record approval decisions, rejections, expirations, and rollback cues in structured run state.
- Make the UI clearly show why the system is waiting and what the user can do next.

Acceptance criteria:

- Users can approve or reject a gated action from the GUI.
- Review state is durable across reloads.
- Simulated-click validation proves approval actions are hittable and visibly change run state.

Status: not started

### 9. Add Cancellation, Recovery, And Diagnostics UX

Goal: Make interrupted or failed orchestration understandable and recoverable.

Main actions:

- Surface run timeline, cancellation, resumability rules, and diagnostic artifacts in the GUI.
- Record durable diagnostics for interrupted, blocked, and failed runs.
- Ensure the UI can recover after reload and reopen the latest communication state.

Acceptance criteria:

- Users can cancel a bounded run and inspect the resulting diagnostics.
- Reloading the app restores the latest visible state without relying on stale memory.
- Simulated-click validation proves start, cancel, reload, and recovery through the GUI.

Status: not started

### 10. Add Multi-Agent Activity Timeline And Observability

Goal: Help users understand what each worker is doing and why.

Main actions:

- Add a timeline or activity feed that records assignment, start, progress, artifact emission, review events, warnings, and termination state.
- Keep activity rows attributable to worker identity and task role.
- Preserve activity summaries under `PRIVATE/**` for debugging and QA.

Acceptance criteria:

- The GUI shows meaningful run activity for each worker.
- Timeline entries are attributable and durable.
- Simulated-click validation proves users can inspect timeline details in the running app.

Status: not started

### 11. Dogfood A Real GUI-Only Task

Goal: Prove the system works for a realistic internal use case using visible app interactions.

Main actions:

- Run a realistic multi-agent task through the GUI: planning, assignment, worker execution, artifact review, approval, cancellation or completion, and final synthesis.
- Preserve screenshots, validation notes, and resulting artifacts under `PRIVATE/**`.
- Record observed UX defects and whether they block productization.

Acceptance criteria:

- A preserved dogfood evidence pack exists.
- The recorded workflow is driven primarily through simulated clicks in the running app.
- The final report names what passed, what remains risky, and what follow-up work is required.

Status: not started

### 12. Package The Maintainer Runbook And Follow-On Backlog

Goal: Leave the system maintainable for future agents and human contributors.

Main actions:

- Document the contracts, APIs, validation rules, evidence layout, and expected debugging paths.
- Convert discovered UX or runtime defects into an explicit backlog.
- Point future agents to the next unfinished product slice.

Acceptance criteria:

- A maintainer runbook exists on disk.
- Follow-on items are explicit and mapped to owned files or plans.
- A new agent can continue from the recorded next step without chat reconstruction.

Status: not started

## Progress Log

### 2026-07-07 - Step 0

- Completed: Created the durable execution plan for productizing AstraBridge's multi-agent communication system with GUI-first orchestration and mandatory simulated-click validation.
- Files changed: `PLAN/MULTI_AGENT_COMMUNICATION_UI_EXECUTION_PLAN.md`
- Validation: Verified the plan includes objective, constraints, execution rules, step acceptance criteria, and an unambiguous next step.
- Blockers: None.
- Next step: Step 1, Inventory Existing Multi-Agent Primitives.
