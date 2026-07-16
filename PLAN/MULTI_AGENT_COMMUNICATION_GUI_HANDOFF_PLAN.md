# Multi Agent Communication GUI Handoff Plan

## Total Objective

Turn AstraBridge's existing task-graph and subagent foundations into a product-grade multi-agent communication workbench: users can visually assign work, inspect node-to-node handoff, review artifacts, approve risky actions, and understand execution state from the GUI. The result must be operable and verifiable through simulated user actions rather than code inspection alone.

## Priority Slice

The preferred first slice for this plan is a GUI-first operator path, not backend breadth. A future agent should be able to open the real app, enter the multi-agent workspace from a visible entry point, create or open a graph, assign work through GUI controls, inspect the resulting handoff, and verify the outcome through simulated clicks, typing, dragging, screenshots, and preserved evidence.

If later agents need to trade off scope, they should preserve this slice first and defer lower-value breadth work.

## Deliverables

- A bounded internal contract for agent communication envelopes, handoff artifacts, review gates, and run-state visibility.
- Sidecar APIs and desktop surfaces for viewing task-graph execution, node communication, approvals, and recovery actions.
- A click-driven validation flow that uses the real app to create, configure, run, inspect, and intervene in multi-agent workflows.
- A Codex-subagent-aware operator flow where users can visually assign work and then verify the resulting execution path from the GUI rather than hidden runtime state.
- Preserved evidence under `PRIVATE/**` for screenshots, traces, validation notes, and failure captures.
- A short operator-facing runbook that explains how users assign work, inspect communication, and recover from failures.

## Related Context Files

- `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_CLICK_DRIVEN_PRODUCTIZATION_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SCOPE_AND_UX_PRINCIPLES.md`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_conversation_service.py`
- `apps/astrabridge-desktop/src/App.tsx`
- `apps/astrabridge-desktop/src/features/runtime/`
- `apps/astrabridge-desktop/src/api.ts`
- `apps/astrabridge-desktop/src/types.ts`

## Constraints And Attention Notes

1. Keep `Project -> Task` as the user-visible product boundary. Worker agents, provider lanes, and Codex subagents remain internal machinery unless surfaced as bounded workflow nodes or activity records.
2. Communication must be artifact-first and state-first. Do not rely on raw chat history as the only durable handoff store.
3. Do not expose provider-private reasoning, hidden scratchpads, API keys, vault contents, cookies, bearer tokens, or raw secret-bearing payloads in UI, traces, screenshots, or reports.
4. Preserve screenshots, traces, raw validation notes, click logs, and failure captures under `PRIVATE/**` by default. Do not clean them unless the user explicitly names target paths.
5. UI-facing work is not complete until the agent has used simulated clicking, typing, and dragging against the real app and preserved evidence.
6. DOM inspection, component tests, and screenshots alone are insufficient for UX claims. The agent must perform the user flow.
7. Prefer bounded templates and explicit review checkpoints over generic free-form agent group chat.
8. High-risk actions such as source mutation, installs, paid provider calls, or external writeback must stay behind human-visible review gates.
9. For any GUI claim about "user can do X", the proving path must start from a visible app surface and reach the outcome through simulated clicks, typing, and dragging. Direct state injection, hidden store mutation, or URL-forcing alone does not count as acceptance evidence.
10. For the first product slice, "user-friendly" means the core task-assignment path can be completed by an agent acting like a normal operator. If a flow still depends on hidden route forcing, internal debug knowledge, or state poking, the UX bar is not met even if the API works.

## Adjustment Policy

Agents may reasonably adjust filenames, substeps, commands, selectors, scripts, implementation details, or sequencing when repository facts require it. Such adjustments must not change the total objective, weaken the click-driven UX gate, hide communication state behind internal-only logs, or replace real user flows with mock-only validation. If a core interaction proves infeasible, record the blocker, evidence, attempted paths, and the narrowest substitute that preserves the user-facing intent.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must begin by reading this plan and the files relevant to the current step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all acceptance criteria are met.
5. For every UI-facing step, the agent must use simulated actions in the real app:
   - open AstraBridge in the in-app browser or Playwright,
   - navigate from a visible app entry point by clicking rather than only forcing URLs,
   - type into real inputs,
   - drag nodes or panes where the feature requires it,
   - capture at least one screenshot before or during the key interaction and one after the expected result,
   - preserve at least one concise validation note that states what was clicked, what was typed, what the app showed, and whether any extra friction remained.
6. If a UI action fails, the agent must preserve the failing screenshot or trace before fixing code.
7. If automation cannot perform a required interaction, the agent must record the automation gap and either fix the automation path or narrow the step without lowering the user-facing bar.
8. A UI-facing step is not complete if it is only proven by API output, DOM inspection, unit tests, or screenshots captured without interaction.
9. Each turn must end with a precise handoff: completed work, files changed, validation run, evidence path, blockers, and exact next step.
10. Any UI-facing validation note must include an explicit click recipe: starting surface, clicked controls, typed values, drag path if any, observed result, and remaining friction.

## Simulated Interaction Contract

Future agents executing this plan must treat simulated interaction as a product gate, not a documentation step:

1. Start from the running AstraBridge app whenever feasible.
2. Reach the changed surface by clicking visible controls instead of relying on hidden internal state.
3. Perform the claimed workflow through real inputs, buttons, lists, drag paths, and review actions.
4. Preserve success evidence and, when encountered, pre-fix failure evidence under `PRIVATE/**`.
5. Record any remaining friction that would matter to a normal user, even if the underlying API is already correct.
6. Treat simulated clicking as a forcing function for UX quality: if the agent struggles to find, click, or understand the workflow, that friction must be fixed or recorded as a product defect before the step can be called complete.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Baseline Current Multi Agent Communication Surfaces
- Next step: Step 1, Baseline Current Multi Agent Communication Surfaces
- Last updated: 2026-07-07

## Execution Steps

### 0. Create Durable Plan

Goal: Create this handoff plan and make the next entry point unambiguous.

Main actions:

- Define the focused objective around multi-agent communication and GUI task assignment.
- Record constraints, execution rules, simulated-click gates, and per-step acceptance criteria.
- Set the initial next step.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, deliverables, constraints, adjustment policy, execution rules, current progress, steps, acceptance criteria, and progress log.
- Simulated clicking is a hard requirement for UI-facing steps.

Status: completed

### 1. Baseline Current Multi Agent Communication Surfaces

Goal: Produce a source-backed inventory of what already exists in task graph, subagent, message, run-state, and GUI surfaces.

Main actions:

- Read the current task-graph plans, contracts, desktop runtime files, and sidecar task services.
- Identify what is already implemented, what is partially implemented, and what is missing for user-visible communication.
- Record the baseline as a short gap note under `PLAN/` or `PRIVATE/**`.

Acceptance criteria:

- A written baseline inventory exists on disk.
- The inventory clearly separates existing surfaces, partial surfaces, and missing surfaces.
- The next agent can start Step 2 without reconstructing chat history.

Status: not started

### 2. Freeze Operator Workflows And UX States

Goal: Define the concrete user workflows that the GUI must support before deeper implementation starts.

Main actions:

- Specify the primary flows: create graph, assign work, inspect handoff, approve/reject risky actions, retry failed nodes, and review artifacts.
- Define the minimum visible states for idle, queued, running, blocked, waiting for review, failed, and completed nodes.
- Record what must be visible in the workspace, inspector, run timeline, and review surface.
- For each primary flow, record the expected click-driven proving path from the visible app surface.

Acceptance criteria:

- A durable workflow and state note exists on disk.
- Each core workflow has visible entry, in-progress, and completion states defined.
- Each core workflow includes a concrete click-driven proving path rather than only state diagrams or API notes.
- Ambiguous “we will decide in code” UX gaps are explicitly removed for the first slice.

Status: not started

### 3. Define The Communication Envelope And Handoff Contract

Goal: Freeze the internal data contract for node-to-node communication and human review.

Main actions:

- Define a structured envelope for sender, receiver, intent, artifact refs, context policy, review requirement, and failure metadata.
- Define which fields are durable state, which are display summaries, and which must never be shown to users.
- Add or extend fixtures and validators for the contract.

Acceptance criteria:

- The contract is documented in a tracked file and matched by fixtures or validators.
- The contract covers success, blocked, retryable, and review-gated handoff cases.
- The contract explicitly excludes raw private reasoning and secret-bearing fields from user-facing surfaces.

Status: not started

### 4. Add Readable Sidecar Surfaces For Communication Inspection

Goal: Expose the minimum API/state needed for the app to inspect multi-agent communication without scraping internal logs.

Main actions:

- Add or extend sidecar read APIs for graph run state, node communication events, review checkpoints, and artifact-linked handoff summaries.
- Keep write paths bounded and explicit.
- Add focused backend tests for the new surfaces.

Acceptance criteria:

- The app can read structured communication state from sidecar APIs or task state.
- Backend tests cover the new fields and response shapes.
- Failure and review-gated states are observable without reading raw internal logs.

Status: not started

### 5. Build The Run Timeline And Communication Inspector Shell

Goal: Give users a first real UI for understanding multi-agent execution and handoff.

Main actions:

- Add a run timeline surface that shows node status and major communication events.
- Add an inspector area for selected node details, latest handoff summary, linked artifacts, and review requirements.
- Keep the layout dense, operational, and scannable rather than decorative.

Acceptance criteria:

- The desktop app renders the timeline and inspector shell using live or fixture-backed data.
- The layout works on desktop and narrow widths without overlapping text.
- A simulated-click validation proves the user can open the surface, select a node, and read its communication summary from the real app.
- Evidence includes at least one before/after screenshot pair and a short note describing the actual clicks and observed state.

Status: not started

### 6. Make Task Assignment And Node Configuration Click Operable

Goal: Let users assign or reconfigure work through direct manipulation instead of editing hidden state.

Main actions:

- Implement node selection, provider/model or role assignment, context policy selection, and review policy controls.
- Support drag or other explicit positioning only where it improves task comprehension.
- Preserve task-graph edits safely through the intended persistence path.

Acceptance criteria:

- A simulated-click-and-type flow can configure at least one node end to end.
- A simulated-drag flow works for the intended positioning interaction and persists after refresh if persistence is part of the surface.
- Validation evidence includes screenshots before and after configuration plus the typed values and observed persisted result.

Status: not started

### 7. Add Edge And Handoff Editing With User Visible Safeguards

Goal: Let users define who hands work to whom and under what review policy.

Main actions:

- Add bounded edge creation or edge configuration for supported templates and flows.
- Surface handoff intent, required artifact expectations, and review gating in the GUI.
- Prevent invalid or unsafe configurations with immediate feedback.

Acceptance criteria:

- A simulated-click flow can create or edit a supported handoff path.
- Invalid configurations are blocked with user-visible guidance.
- Evidence shows the actual interaction rather than only code or DOM inspection, including which controls were clicked and what the app rendered afterward.

Status: not started

### 8. Add Human Review Gates And Recovery Actions

Goal: Make risky or failed paths visible and controllable by the user.

Main actions:

- Add review surfaces for approve, reject, retry, and cancel actions.
- Show why a node is blocked and what evidence or artifacts it produced.
- Keep actions bounded to the task graph and preserve auditability.

Acceptance criteria:

- A simulated-click flow can open a review state and execute at least one recovery or approval action.
- The resulting state transition is visible in the app.
- Evidence captures the before and after states, the action performed, and the visible reason for the gate or failure.

Status: not started

### 9. Map Codex Subagent Execution To User Understandable Status

Goal: Bridge internal subagent execution into a clean GUI without exposing unstable internal details.

Main actions:

- Map internal lane or subagent activity to stable user-facing status, timestamps, and summaries.
- Distinguish waiting, running, tool-using, review-blocked, and failed states.
- Keep raw provider-private internals hidden.

Acceptance criteria:

- The UI shows meaningful execution status derived from real runtime state.
- Users can tell which node is active, blocked, or finished without reading logs.
- The mapping is documented so later agents do not drift the semantics.

Status: not started

### 10. Build A Real Click Driven Validation Harness

Goal: Make user-level verification repeatable instead of ad hoc.

Main actions:

- Create or extend scripts, selectors, and evidence conventions for in-app browser or Playwright runs.
- Cover graph entry, template selection, node configuration, handoff inspection, and review action paths.
- Make the harness exercise the UI through simulated clicks by default instead of relying on hidden state injection, except where a preserved blocker explicitly justifies a narrower workaround.
- Record screenshots, concise notes, and any failing traces under a stable artifact root.

Acceptance criteria:

- A reusable validation harness exists on disk.
- The harness covers both success and at least one failure or blocked path.
- The harness documentation makes the click order and expected GUI checkpoints explicit enough that another agent can operate it without reconstructing chat history.
- Another agent can run the harness without reconstructing selectors or click order from chat history.

Status: not started

### 11. Dogfood Representative Multi Agent Scenarios Through The Real App

Goal: Prove the workbench supports actual operator tasks rather than isolated controls.

Main actions:

- Run representative scenarios such as planner -> worker -> reviewer and diagnose -> fix -> verify.
- Use simulated clicks, typing, and dragging only through the real app surfaces.
- Record rough edges, confusing copy, or friction that still harms usability.

Acceptance criteria:

- At least two end-to-end scenarios are executed through the GUI.
- Evidence includes screenshots, short validation notes, and any preserved failure captures.
- The report distinguishes product gaps from test-harness gaps.

Status: not started

### 12. Harden Failure Semantics, Empty States, And Recovery Copy

Goal: Remove the most obvious UX traps that appear during dogfood.

Main actions:

- Fix or narrow ambiguous empty states, hidden blockers, unclear recovery actions, and broken click paths found in Step 11.
- Add focused tests where the risk of regression is meaningful.
- Re-run the affected click-driven scenarios.

Acceptance criteria:

- The most severe usability failures found in Step 11 are either fixed or explicitly deferred with rationale.
- Re-run evidence shows the affected flow is now understandable.
- Tests and build validation pass for the touched surfaces.

Status: not started

### 13. Write The Operator Runbook And Final Handoff

Goal: Leave future agents and maintainers with one durable entry point for operating and evolving the feature.

Main actions:

- Write a short operator runbook for graph assignment, communication inspection, approvals, retries, and evidence lookup.
- Link the runbook to the validation harness, key artifact roots, and remaining known risks.
- Summarize the exact next recommended engineering step.

Acceptance criteria:

- A tracked runbook exists on disk.
- The runbook points to the validation harness and evidence locations.
- The final handoff names remaining risks and the next execution entry point.

Status: not started

## Progress Log

### 2026-07-07 - Step 0

- Completed: Created a focused durable handoff plan for turning AstraBridge's early multi-agent communication and task-assignment foundations into a click-driven GUI workbench.
- Files changed: `PLAN/MULTI_AGENT_COMMUNICATION_GUI_HANDOFF_PLAN.md`
- Validation: Read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md` and `C:\Users\cyz19\.codex\skills\durable-handoff-plan\references\plan-template.md`, then adapted the template into a 14-step execution plan with explicit simulated-click, drag, screenshot, and evidence gates for all UI-facing work.
- Blockers: None.
- Next step: Step 1, Baseline Current Multi Agent Communication Surfaces.

### 2026-07-07 - Plan Hardening

- Completed: Hardened the handoff plan around the part that matters most for product quality: future agents are now explicitly required to prove GUI claims through simulated clicking, typing, and dragging from visible app surfaces, with preserved success and pre-fix failure evidence. This closes the common loophole where an implementation is API-correct but still not operator-friendly.
- Files changed: `PLAN/MULTI_AGENT_COMMUNICATION_GUI_HANDOFF_PLAN.md`
- Validation:
  - Re-read the full plan after patching.
  - Verified that constraints, execution rules, acceptance criteria, and the new simulated interaction contract all consistently require real app interaction instead of hidden-state proof.
- Blockers: None.
- Next step: Step 1, Baseline Current Multi Agent Communication Surfaces.

### 2026-07-07 - Priority Slice Hardening

- Completed: Tightened the plan around the highest-value implementation slice: visible multi-agent task assignment and communication inspection through the real GUI. The plan now makes click-first operator validation more concrete by adding a priority slice, a stricter user-friendly bar, explicit click-recipe requirements, workflow-level proving paths, and stronger harness expectations.
- Files changed: `PLAN/MULTI_AGENT_COMMUNICATION_GUI_HANDOFF_PLAN.md`
- Validation:
  - Re-read the full plan after patching.
  - Verified that the new `Priority Slice`, constraints, execution rules, simulated interaction contract, Step 2 requirements, and Step 10 requirements consistently force simulated-click proof.
- Blockers: None.
- Next step: Step 1, Baseline Current Multi Agent Communication Surfaces.
