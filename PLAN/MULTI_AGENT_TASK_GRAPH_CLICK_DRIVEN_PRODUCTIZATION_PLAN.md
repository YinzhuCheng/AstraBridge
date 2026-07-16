# Multi Agent Task Graph Click Driven Productization Plan

## Total Objective

Turn AstraBridge's early multi-agent task graph work into a user-friendly, GUI-first product slice that can be exercised end to end through simulated user actions. The outcome is a graph workflow that agents can improve, verify, and regress-test by operating the real app through clicks, typing, dragging, screenshots, and preserved evidence rather than relying on code inspection or unit tests alone.

## Deliverables

- A usable graph workspace flow inside the desktop app for template selection, node editing, edge editing, dry-run validation, run inspection, and artifact review.
- A preserved click-driven validation harness and evidence pack under `PRIVATE/**` for every UI-facing milestone in this slice.
- A repeatable operator-style click recipe that future agents can execute from the visible app surface without relying on hidden state injection, direct store mutation, or code-only reasoning.
- A repeatable handoff protocol that forces future agents to validate behavior by simulated interaction before claiming UX work complete.

## Related Context Files

- `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SCOPE_AND_UX_PRINCIPLES.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SURFACE_MAP.md`
- `apps/astrabridge-desktop/src/App.tsx`
- `apps/astrabridge-desktop/src/api.ts`
- `apps/astrabridge-desktop/src/types.ts`
- `apps/astrabridge-desktop/src/features/runtime/`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`

## Constraints And Attention Notes

1. This plan is a focused execution slice under the broader task-graph objective. It must not weaken the product boundary defined in `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`.
2. UI work is not complete until the agent has operated the changed path through simulated clicks in the in-app browser or Playwright and preserved evidence under `PRIVATE/**`.
3. Every UI-facing step must leave behind at least one screenshot and one concise validation note that states what the agent clicked, what the app showed, and what still felt rough.
4. Unit tests, component tests, and builds remain necessary but are never sufficient evidence for user-facing behavior.
5. Preserve artifacts, traces, screenshots, raw reports, and failure captures by default. Do not clean them unless the user explicitly names target paths.
6. Do not persist secrets, vault contents, cookies, raw auth headers, or provider key material in screenshots, traces, logs, or reports.
7. Prefer incremental, task-shaped workflows over generic graph-editor completeness. The first goal is a product that guides users through real workflows, not a blank technical canvas.
8. If an agent cannot automate a required UI action, it must record the blocker with concrete evidence and then either fix the automation gap or reduce the step to a narrower, still-user-visible slice.
9. For every UI-facing step, the agent must prove the path through operator-style interaction in the real app: click visible entry points, type into real inputs, drag where required, and read back the resulting UI state. API success or DOM inspection alone does not satisfy the step.
10. If a step changes how a user reaches or saves a screen, the agent must preserve both a success screenshot and, when encountered, the failing pre-fix screenshot or trace that justified the change.

## Evidence Convention

- Default artifact root for this plan: `PRIVATE/task-graph/click-driven-productization/<step-id>/<YYYYMMDD>/`
- Minimum evidence per UI-facing step:
  - one screenshot before or during the key interaction,
  - one screenshot after the expected state change,
  - one concise validation note listing the exact clicked controls, typed values, observed result, and any remaining UX rough edge,
  - if the first attempt failed, one preserved failure screenshot or trace before the fix.
- Evidence must be readable by a later agent without replaying chat history.

## Adjustment Policy

Agents may reasonably adjust substeps, implementation details, file paths, commands, test selectors, viewport choices, or sequencing when repository facts require it. Such adjustments must not change the total objective, remove the simulated-click quality gate, lower the usability bar, or replace substantive GUI work with internal-only refactors. If a core interaction proves infeasible, record the blocker, evidence, attempted paths, and a substitute flow that preserves user-facing validation.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must start by reading this plan and the relevant files for the current step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all acceptance criteria are satisfied.
5. For every UI-facing step, the agent must:
   - open the real app,
   - start from the visible app surface when feasible and navigate by simulated clicks and typing instead of only forcing internal state,
   - perform the changed interaction path,
   - capture at least one screenshot,
   - preserve evidence under the step artifact root in `PRIVATE/**`,
   - and summarize the interaction in the progress log.
6. If a click flow fails, the agent must preserve the failing screenshot or trace before fixing code.
7. A UI-facing step is not complete if the agent only proved API behavior, unit tests, or component rendering. The simulated-click proof is mandatory.
8. Each turn must end with a precise handoff: completed work, files changed, validation run, evidence path, blockers, and the exact next step.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Stabilize Graph Workspace Entry And Evidence Harness
- Next step: Step 1, Stabilize Graph Workspace Entry And Evidence Harness
- Last updated: 2026-07-07

## Execution Steps

### 0. Create Durable Plan

Goal: Create this focused productization plan and make the next entry point explicit.

Main actions:

- Define the click-driven productization objective.
- Record constraints, adjustment policy, execution rules, steps, and evidence requirements.
- Set the first implementation step around real app entry and simulated-click proof.

Acceptance criteria:

- Plan file exists on disk.
- The plan includes total objective, constraints, adjustment policy, execution rules, current progress, numbered steps, acceptance criteria, and progress log.
- Simulated-click validation is a hard rule, not a suggestion.
- The plan defines an evidence convention that another agent can follow without reconstructing it from chat history.

Status: completed

### 1. Stabilize Graph Workspace Entry And Evidence Harness

Goal: Make the graph workspace reliably reachable from the running app and make screenshot preservation part of normal execution.

Main actions:

- Finish or repair the topbar entry into the graph workspace.
- Ensure the graph shell renders correctly at desktop and mobile-ish widths.
- Add or confirm deterministic selectors needed for automated clicking and screenshot capture.
- Create the step evidence location under the plan artifact convention and preserve the first successful entry screenshot there.

Acceptance criteria:

- A simulated-click flow opens the graph workspace from the real app.
- The graph workspace shows template list, canvas, and inspector without blocking text overlap at the tested widths.
- At least two screenshots and one short validation note are preserved under the step artifact root in `PRIVATE/**`.

Status: not started

### 2. Make Template Instantiation Feel Like A Product Action

Goal: Turn template selection into a clear, low-friction action rather than a raw API trigger.

Main actions:

- Refine template cards, loading states, empty states, and post-instantiation selection behavior.
- Ensure the newly instantiated graph becomes visible and focused without requiring the user to guess what changed.
- Add simulated-click coverage for choosing a template and confirming the resulting graph state.

Acceptance criteria:

- A user can click a template card and see a graph appear in the canvas with the correct initial selection state.
- The app shows clear loading or success behavior during instantiation.
- Evidence under the step artifact root includes screenshots before and after instantiation plus a short interaction summary.

Status: not started

### 3. Implement Direct Node Selection, Editing, And Persistence

Goal: Let users inspect and edit node configuration through normal GUI interactions.

Main actions:

- Wire node-card selection to the inspector.
- Support editing the node's role, provider, model, and context policy through GUI controls.
- Persist changes through the sidecar API and confirm refresh stability.

Acceptance criteria:

- A simulated-click flow selects a node, edits at least one configuration field, saves it, reloads, and sees the change persist.
- Validation and error states are visible in the inspector when input is invalid.
- Evidence under the step artifact root captures the edit flow and the refreshed persisted state.

Status: not started

### 4. Add Drag And Reposition With Stable Layout

Goal: Make graph manipulation spatial, stable, and testable.

Main actions:

- Implement node dragging with stable dimensions and predictable drop behavior.
- Persist node coordinates.
- Verify that hover states, labels, and validation messages do not shift node card sizes unexpectedly.

Acceptance criteria:

- A simulated click-and-drag flow moves a node and the new position survives refresh.
- No tested node card overlaps another card or causes label overflow after the drag.
- Evidence under the step artifact root includes before/after screenshots and a persisted-position check.

Status: not started

### 5. Add Edge Wiring And Explicit Context Policy Controls

Goal: Make information flow visible and configurable instead of implicit.

Main actions:

- Implement GUI edge creation and selection.
- Add edge inspector controls for context policy, artifact inclusion, and excluded memory.
- Validate missing or unsafe edge policies before save.

Acceptance criteria:

- A simulated-click flow creates or edits an edge and persists the updated policy.
- Invalid edge policy edits are blocked with a visible, actionable message.
- Evidence under the step artifact root includes an edge-edit screenshot and the saved graph state.

Status: not started

### 6. Build Dry-Run Validation Into The Real Workflow

Goal: Let users verify graph readiness before any paid or stateful execution.

Main actions:

- Add a dry-run action in the graph workspace.
- Surface node-level and graph-level readiness states in the UI.
- Preserve dry-run reports as artifacts and link to them from the interface.

Acceptance criteria:

- A simulated-click flow triggers dry-run from the real app and opens the resulting report.
- The report is secret-free and preserved under `PRIVATE/**`.
- The UI clearly distinguishes ready, warning, and blocked states.

Status: not started

### 7. Add Run Timeline And Artifact Review Surface

Goal: Make execution state legible to a normal user.

Main actions:

- Add a run timeline that shows node start, completion, warnings, blocks, approvals, and artifacts.
- Add artifact chips or previews for common outputs.
- Make navigation between graph canvas and run evidence direct and obvious.

Acceptance criteria:

- A simulated-click flow opens a run record, inspects an artifact, and returns to the graph without losing context.
- Timeline rows and artifact controls remain readable at tested widths.
- Evidence under the step artifact root includes timeline and artifact screenshots with a short interaction note.

Status: not started

### 8. Add Permission Gates And Human Review UX

Goal: Prevent risky automation from feeling hidden or irreversible.

Main actions:

- Reuse the repository's approval patterns for high-risk operations.
- Show pending approval, approve, and reject states directly in the run timeline and inspector.
- Preserve rejection and approval artifacts for later diagnosis.

Acceptance criteria:

- A simulated-click flow reaches a gated action, rejects it once, approves it once, and records both results.
- The reason for the gate is visible before the user acts.
- Evidence under the step artifact root captures both branches and the resulting run state.

Status: not started

### 9. Add Failure Capture And Recovery UX

Goal: Make broken runs diagnosable and resumable instead of opaque.

Main actions:

- Preserve failure screenshots, validation reports, or diagnostics automatically.
- Surface blocked and failed states with clear recovery options.
- Verify reload behavior after an interrupted run.

Acceptance criteria:

- A simulated-click flow encounters or injects a failure path, reloads the app, and still sees the diagnostic state.
- The user can identify what failed, where the evidence lives, and what action is possible next.
- Evidence under the step artifact root includes the failure capture and reload state.

Status: not started

### 10. Add Template-Specific Guided Defaults

Goal: Make the graph product useful for concrete workflows rather than only configurable.

Main actions:

- Refine the first supported templates with better labels, recommended providers/models, artifact expectations, and guidance text kept out of the main workspace chrome.
- Keep templates editable after instantiation.
- Validate the most useful templates through real app flows.

Acceptance criteria:

- At least three templates can be instantiated and inspected through simulated clicks.
- Template defaults clearly differ by workflow rather than looking like generic copies.
- Evidence under the step artifact root includes one screenshot per tested template plus a brief note on any rough edges.

Status: not started

### 11. Run A Full Click Driven Usability Sweep

Goal: Force the feature to withstand a realistic user session.

Main actions:

- Execute a full simulated session: open graph workspace, instantiate template, edit nodes, wire edges, dry-run, inspect outputs, handle a gate, and review diagnostics.
- Test at least two viewport sizes.
- Convert any critical usability defects into immediate fixes or explicit backlog items.

Acceptance criteria:

- A preserved usability evidence pack exists under `PRIVATE/**` with screenshots, trace summary, tested viewports, and defect list.
- No tested path ends in a dead end without feedback.
- The resulting report makes the next highest-risk UX gap obvious.

Status: not started

### 12. Publish Maintainer Runbook For Click Driven Development

Goal: Make future agents continue the same product discipline instead of falling back to internal-only validation.

Main actions:

- Write a maintainer runbook that explains selectors, evidence paths, click-flow expectations, and regression procedure.
- Link the runbook to the broader task-graph execution plan.
- Document how to add a new graph feature without bypassing simulated-click validation.

Acceptance criteria:

- A maintainer-facing runbook exists on disk.
- The runbook tells a future agent exactly how to verify GUI changes through simulated interaction and where to store evidence.
- The runbook references this plan and the broader task-graph plan.

Status: not started

## Progress Log

### 2026-07-07 - Step 0

- Completed: Created a focused execution plan for the part of the multi-agent task graph work that matters most for product quality: a click-driven, user-friendly graph workflow that agents must validate through the real app. This plan intentionally raises the bar from "API and component work exists" to "a future agent must click through the path, preserve evidence, and prove the UX is usable."
- Files changed: `PLAN/MULTI_AGENT_TASK_GRAPH_CLICK_DRIVEN_PRODUCTIZATION_PLAN.md`
- Validation:
  - Read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`
  - Read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\references\plan-template.md`
  - Read `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Blockers: None.
- Next step: Step 1, Stabilize Graph Workspace Entry And Evidence Harness.

### 2026-07-07 - Plan Hardening

- Completed: Hardened this handoff plan so future agents are explicitly forced to operate the real GUI through simulated clicks, typing, and dragging rather than proving behavior only through APIs, tests, or DOM inspection. Added a stable evidence convention, stronger UI-facing execution rules, and step-level acceptance wording that requires preserved before/after interaction evidence.
- Files changed: `PLAN/MULTI_AGENT_TASK_GRAPH_CLICK_DRIVEN_PRODUCTIZATION_PLAN.md`
- Validation:
  - Re-read the full plan after patching.
  - Verified the execution rules, evidence convention, Step 0 acceptance criteria, and all UI-facing acceptance sections consistently require simulated interaction and preserved evidence.
- Blockers: None.
- Next step: Step 1, Stabilize Graph Workspace Entry And Evidence Harness.
