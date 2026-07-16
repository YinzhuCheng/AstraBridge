# Multi Agent Task Graph Canvas And Dogfood Handoff Plan

## Total Objective

Finish the remaining multi-agent task graph product work by combining the main plan's final end-to-end dogfood with a dedicated canvas-first UI pass. The finished surface should feel like an operator graph editor: users can open the real app, enter the task graph through visible controls, manipulate nodes and edges directly on the canvas, inspect only the details they need, run a realistic multi-agent workflow, and verify artifacts, approvals, cancellation, and recovery without relying on hidden API calls.

This plan is the concrete execution contract for `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md` Step 19 plus the canvas/UI backlog left after Step 18. Future agents should treat this as the single governing plan for all remaining task-graph work until the master Step 19 is closed, rather than splitting execution into separate "dogfood" and "UI polish" tracks.

## Deliverables

- A more user-friendly task graph canvas with clearer node selection, edge interaction, fit/navigation controls, and reduced non-canvas visual noise.
- A refined task graph sidebar and inspector that keep secondary detail behind disclosure controls while preserving full capability.
- A visible-click dogfood run for a realistic code-task workflow: planner, code worker, test worker, review worker, and synthesizer.
- Preserved screenshots, click traces, validation notes, run state, worker outputs, artifact links, and final report under `PRIVATE/**`.
- A final completion update in `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md` only after the UI and dogfood acceptance criteria are met.

## Related Context Files

- `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SCOPE_AND_UX_PRINCIPLES.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SURFACE_MAP.md`
- `PLAN/STEP17_GUI_USABILITY_CLICK_HANDOFF_PLAN.md`
- `docs/TASK_GRAPH_MAINTAINER_RUNBOOK.md`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
- `apps/astrabridge-desktop/src/App.tsx`
- `apps/astrabridge-desktop/src/styles.css`
- `apps/astrabridge-desktop/src/api.ts`
- `apps/astrabridge-desktop/src/types.ts`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`

## Evidence Roots

- Canvas/UI evidence:
  - `PRIVATE/task-graph/canvas-dogfood/20260707/`
- Step 17 prior UI QA:
  - `PRIVATE/task-graph/step17-gui-usability/20260707/`
- Step 18 docs/help evidence:
  - `PRIVATE/task-graph/step18-docs-help/20260707/`

Future agents should create a dated subfolder if the work continues on a later date.

## Constraints And Attention Notes

1. Keep `Project -> Task` as the user-visible boundary. Worker lanes, provider lanes, Codex subagents, and raw thread IDs stay internal unless represented as bounded graph nodes, run activity, or artifact refs.
2. The graph editor must become more canvas-first. Do not solve user confusion by adding more visible explanatory text to the main workflow.
3. UI-facing acceptance requires simulated clicks, typing, scrolling, dragging, and screenshots in the real app. Unit tests, code inspection, DOM inspection, and direct API calls are not enough.
4. Do not use direct task-graph API calls such as `/api/task-graphs/instantiate`, `/api/task-graphs/edge/update`, `/api/task-graphs/fixture-run`, `/api/task-graphs/run/cancel`, or `/api/task-graphs/approval/resolve` to satisfy a user-flow acceptance item. These are allowed only for diagnosis after a visible failure screenshot has been preserved.
5. Do not mutate hidden frontend stores, inject graph state, force internal routes, or seed state through debug globals to claim success. The proving path must start from a visible app surface.
6. Every UI-facing step must preserve at least one before or entry screenshot and one after-result screenshot under `PRIVATE/**`.
7. Every UI-facing validation note must include the visible click recipe: starting surface, clicked controls, typed values, drag path if applicable, observed result, and remaining friction.
8. Preserve all diagnostics, screenshots, traces, run summaries, and validation reports by default. Do not clean `PRIVATE/**` unless the user explicitly names targets.
9. Never persist API keys, bearer tokens, cookies, auth headers, vault contents, provider raw secrets, or secret-bearing raw payloads.
10. Human review gates remain part of the product contract. Do not hide approval, rejection, cancellation, or recovery states behind logs only.
11. Future agents must prefer the in-app browser as the primary proving surface. API inspection is diagnosis-only and can happen only after a visible failure or ambiguity has already been captured.
12. Every remaining UI or UX step must preserve enough screenshots to let a later reviewer judge interaction quality without rerunning the app.
13. Agents must inspect the screenshots they just captured before ending the step and record whether the images still show crowding, clipping, weak hierarchy, or dead interaction zones. Capturing screenshots without reviewing them does not satisfy this plan.
14. For remaining execution, simulated interaction is not just a proof method but the default operating mode for task-graph work. If the app supports a user-visible action, agents must perform that action through simulated click, type, drag, scroll, or keyboard input first.

## Simulated Interaction Contract

For every UI-facing step, the agent must:

1. Open or reuse the running AstraBridge app in the in-app browser or Playwright.
2. Navigate by visible controls, starting from the normal app shell.
3. Enter the task graph by clicking the visible `Task graph` control or its localized equivalent.
4. Select templates, nodes, edges, toolbar actions, approvals, artifact links, and recovery actions by simulated user input.
5. Drag graph nodes or canvas surfaces when the step claims drag or canvas manipulation.
6. Capture screenshots before the key action, after the result, and after any fix that changes the UI.
7. Preserve a validation note that states explicitly whether any direct API calls were used. If any API call was used for diagnosis, state why it was not part of acceptance evidence.
8. Prefer real pointer interaction over programmatic state changes even when the same effect would be faster through code or HTTP calls.
9. Re-check the visible result after reload or re-entry whenever the step changes persistent state, layout, selection behavior, or run-state presentation.

Forbidden acceptance shortcuts:

- starting or cancelling graph runs through HTTP calls
- directly setting selected graph or selected node state
- editing persisted graph JSON to avoid using the UI
- claiming visual quality from source code alone
- counting a screenshot as interaction evidence when no click, type, scroll, or drag occurred

## Step Execution Checklist

Every remaining numbered step from Step 9 onward must follow this checklist:

1. Re-read this handoff plan and the master plan before acting.
2. Open the running app and reach the task graph from the normal visible shell.
3. Perform the step through simulated interaction first, not through HTTP calls or internal state mutation.
4. Capture and review screenshots during the step, not only after implementation.
5. If the UI still looks crowded or awkward in the screenshots, continue iterating within the same step until the acceptance bar is met or a concrete blocker is recorded.
6. Only use direct API or code-level inspection after visible evidence has already captured the failure or ambiguity.
7. Update this plan and the master plan before ending the turn, with exact screenshot paths and the next entry point.

## Mandatory Evidence Rhythm

For every remaining step from Step 7 onward, agents must preserve at least:

1. One entry screenshot showing the surface before the main interaction.
2. One in-progress screenshot showing the actual interaction state, such as selection, drag, expanded disclosure, running status, approval state, or error state.
3. One result screenshot showing the visible outcome after the action or fix.
4. One post-reload or post-reentry screenshot whenever the step changes persisted state or workflow continuity.

The validation note for each step must list:

- starting URL and viewport
- visible click path
- typed values if any
- drag path if any
- screenshot filenames
- whether API calls were used for diagnosis
- remaining friction or backlog observed during the replay

## Cross-Agent Enforcement Addendum

This handoff plan is now the mandatory single execution contract for all remaining master-plan work and all remaining canvas beautification or UI optimization work under Step 19.

1. Future agents may not split the remaining work into separate "main-plan execution", "canvas polish", "UI cleanup", or "API debugging" tracks.
2. The remaining execution sequence stays unified as Step 12 through Step 15 in this document.
3. For every remaining step, the proving path must begin from the visible AstraBridge shell in the in-app browser and proceed by simulated click, type, drag, scroll, or keyboard input.
4. Direct API calls, local state mutation, seeded graph JSON, debug globals, or route forcing are diagnosis-only tools after visible failure evidence has already been preserved.
5. If browser automation surfaces disagree with the screenshot-visible UI, the agent must treat that as part of the step's blocker or diagnosis work. The agent may not bypass the app by switching acceptance to HTTP requests.
6. Each remaining step must preserve and review at least four screenshots whenever persistence or workflow continuity is involved: entry, in-progress, result, and post-reload or post-reentry.
7. Each remaining step's validation note must explicitly say that screenshots were reviewed during execution and must name any remaining crowding, clipping, hierarchy weakness, or interaction awkwardness still visible in those images.
8. If a UI flow fails, the agent must first preserve the failure screenshot, then fix code, then replay the same visible click path. Fixing code without re-running the same visible path does not satisfy acceptance.
9. If a step remains blocked, the blocker record must name the exact visible click path attempted, the exact screenshot files captured, the diagnosis-only tools used afterward, and the exact next entry point for the next agent.

## Adjustment Policy

Agents may reasonably adjust specific substeps, filenames, selectors, commands, implementation details, or sequencing when evidence from the workspace requires it. Adjustments must not change the total objective, weaken the canvas-first direction, remove simulated-click gates, reduce artifact-first safety, hide remaining friction, or replace real user workflows with API-only validation. If a core objective becomes infeasible, record the blocker, evidence, attempted paths, and a substitute path that preserves the user-facing intent.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must begin by reading this plan and the context files needed for the current step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all acceptance criteria are met.
5. If a step changes UI behavior, local tests are required but not sufficient; visible simulated-click evidence is also required.
6. If a UI action fails, preserve the failure screenshot or trace before fixing code.
7. Each turn must end with a concise handoff: completed work, files changed, validation run, evidence path, blockers, and exact next step.
8. If a step can be exercised through the visible app, agents must use simulated clicks first and may not substitute internal APIs merely because they are faster or more deterministic.
9. Screenshot review is part of execution, not a final cosmetic check. Agents should inspect screenshots during the step and iterate if the UI is still crowded, clipped, or visually confusing.

## Current Progress

- Current status: Completed
- Completed steps: Step 0, Create Combined Handoff Plan; Step 1, Baseline Current Canvas And Dogfood State; Step 2, Define Canvas UX Target And Acceptance Checklist; Step 3, Add Canvas Navigation Controls; Step 4, Improve Node Visual States And Hit Targets; Step 5, Improve Edge Visual States And Direct Selection; Step 6, Add Canvas-First Edge Creation Or Connection Affordance; Step 7, Refine Sidebar And Inspector As Secondary Surfaces; Step 8, Improve Run Status And Timeline Presentation Around The Canvas; Step 9, Desktop Viewport Canvas QA; Step 10, Narrow-Width And Scroll-Ergonomics QA; Step 11, Prepare Final Dogfood Run Contract; Step 12, Execute Code-Task Dogfood Through Visible UI; Step 13, Inspect Artifacts, Handoffs, And Review Gates Through UI; Step 14, Prove Reload, Recovery, And Persistence; Step 15, Publish Final Report And Close Master Step 19
- Remaining unified steps under this contract: None
- Current step: None
- Next step: None
- Last updated: 2026-07-07

## Execution Steps

### 0. Create Combined Handoff Plan

Goal: Create this persistent handoff plan and make the next entry point clear.

Main actions:

- Combine the main Step 19 dogfood objective with the canvas/UI backlog left after Step 18.
- Record the no-API-substitution click contract and screenshot requirements.
- Link this plan from the master task graph execution plan.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes objective, deliverables, constraints, simulated interaction contract, execution rules, current progress, steps, acceptance criteria, and progress log.
- Master plan points Step 19 execution to this handoff plan.

Status: completed

### 1. Baseline Current Canvas And Dogfood State

Goal: Capture the current visible state before making further canvas changes.

Main actions:

- Read the current task graph workspace code, styles, tests, and relevant sidecar surfaces.
- Open the real app and enter the task graph through visible controls.
- Capture desktop and narrow-width screenshots of the current canvas, sidebar, inspector, docked run panel, and any visible friction.
- Write a baseline note under `PRIVATE/task-graph/canvas-dogfood/<date>/`.

Acceptance criteria:

- Baseline screenshots exist for desktop and narrow width.
- Baseline note lists current canvas, sidebar, inspector, and dogfood blockers.
- The note states the exact visible click path used to reach the task graph.
- No API-only setup is counted as baseline acceptance.

Status: completed

### 2. Define Canvas UX Target And Acceptance Checklist

Goal: Turn "more like a circuit editor" into concrete UI acceptance criteria.

Main actions:

- Define the desired canvas interaction model: fit view, pan, zoom, visible selection, edge focus, node handles, edge labels, and compact status signals.
- Define what should live on the canvas, what belongs in a collapsible side surface, and what should be hover-only.
- Write a short acceptance checklist under `PLAN/` or `PRIVATE/**`.

Acceptance criteria:

- A canvas UX target note exists on disk.
- The note defines visible states for normal, hover, selected, dragging, running, blocked, failed, completed, and review-gated nodes or edges.
- The note includes screenshot checkpoints and a click recipe for proving each major interaction.

Status: completed

### 3. Add Canvas Navigation Controls

Goal: Give users basic canvas navigation without relying on scrollbars alone.

Main actions:

- Add visible icon controls for fit-to-content, reset view, zoom in, zoom out, and optionally pan mode.
- Keep controls compact and canvas-local.
- Persist only what is useful; avoid storing noisy transient viewport state unless needed.
- Add focused tests for view state and control availability.

Acceptance criteria:

- Users can click visible controls to fit, zoom, and reset the graph view.
- The controls use familiar icons and tooltips, not explanatory text blocks.
- A simulated-click validation opens the graph, clicks the controls, and preserves before/after screenshots.
- Local tests and build pass.

Status: completed

### 4. Improve Node Visual States And Hit Targets

Goal: Make nodes easier to read, select, drag, and understand at a glance.

Main actions:

- Refine node card sizing, typography, status badges, selected state, hover state, and drag affordance.
- Keep node layout stable so labels and status do not resize the graph.
- Add stronger visual distinction for planner, worker, synthesizer, validator, reviewer, and gate roles without a one-note palette.

Acceptance criteria:

- Node selected, hover, dragging, and status states are visually distinct in screenshots.
- A simulated drag starts from a visible node and ends with the node persisted after reload.
- The validation note records the drag path and any remaining friction.
- Local tests and build pass.

Status: completed

### 5. Improve Edge Visual States And Direct Selection

Goal: Make edges feel like first-class graph objects rather than hard-to-click lines.

Main actions:

- Improve edge stroke, active state, hover target, arrow direction, and label placement.
- Add or refine a visible edge label/chip on the canvas when it helps selection.
- Ensure clicking an edge on the canvas opens the edge inspector without needing the left sidebar.

Acceptance criteria:

- A user can select an edge from the canvas through simulated clicking.
- Active, warning, blocked, and pass edge states are visually distinguishable.
- Screenshots prove the selected edge state and corresponding inspector state.
- Local tests and build pass.

Status: completed

### 6. Add Canvas-First Edge Creation Or Connection Affordance

Goal: Reduce reliance on sidebar controls for creating or wiring edges.

Main actions:

- Add a visible node-level connection affordance or a clear canvas-local create-edge flow.
- Keep context policy editing in the inspector, but make choosing source and target feel direct.
- Preserve validation for duplicate edges, same-node edges, and missing context policy.

Acceptance criteria:

- A simulated user can create or begin creating an edge from visible canvas controls.
- Invalid edge creation is blocked with a clear UI state.
- The created or edited edge persists after reload.
- No direct edge-update API calls are used for acceptance evidence.
- Local tests and build pass.

Status: completed

### 7. Refine Sidebar And Inspector As Secondary Surfaces

Goal: Keep the canvas dominant while preserving power-user detail access.

Main actions:

- Review the left sidebar and right inspector after the canvas changes.
- Collapse or move secondary metadata behind disclosure controls.
- Fix remaining text clipping, long enum compression, and cramped checkbox groups.
- Keep important safety settings discoverable.
- Use screenshot review during the step to judge whether the canvas now reads as the primary work surface.

Acceptance criteria:

- Desktop screenshots show the canvas as the dominant area.
- Entry, in-progress, and result screenshots are preserved for the sidebar and inspector interaction path.
- Inspector core fields fit without obvious text clipping in the tested viewport.
- Advanced settings remain reachable by simulated clicks.
- Local tests and build pass.

Status: completed

### 8. Improve Run Status And Timeline Presentation Around The Canvas

Goal: Make graph execution state visible without burying the canvas.

Main actions:

- Refine latest-run dock, status badges, timeline expansion, worker output links, and approval state placement.
- Keep default state compact; expand only when users need detail.
- Ensure running, cancelled, failed, blocked, waiting-for-review, and completed states are distinguishable.
- Review screenshots during the step and keep the graph canvas readable even when the run panel is expanded.

Acceptance criteria:

- A simulated fixture run shows visible running and terminal states without covering the graph.
- Cancellation and latest-run details are reachable by visible clicks.
- Screenshots capture compact and expanded run states.
- Validation note records the exact click path for expanding and collapsing run detail.
- Local tests and build pass.

Status: completed

### 9. Desktop Viewport Canvas QA

Goal: Verify the refined editor under the primary desktop viewport.

Main actions:

- Use the real app at a desktop viewport.
- Enter the task graph by visible controls.
- Exercise template selection, node drag, edge selection or creation, inspector edit, dry-run, fixture run, latest-run expansion, artifact link open, and reload.
- Preserve screenshots and a click recipe.
- Review screenshots mid-step and record any remaining layout friction instead of only pass/fail.

Acceptance criteria:

- A desktop validation note exists under `PRIVATE/**`.
- The note includes screenshots before/during/after the key graph interactions.
- The tested path has no critical overlap, inaccessible primary controls, or dead-end states.
- API calls are not used to substitute any user action.

Status: completed

### 10. Narrow-Width And Scroll-Ergonomics QA

Goal: Ensure the graph remains usable when space is constrained.

Main actions:

- Repeat the core open/select/inspect/edit flow at a narrow viewport.
- Capture where the canvas, sidebar, inspector, and run dock appear.
- Fix critical overlap or hidden primary actions; record non-blocking friction separately.
- Use screenshots, not code inspection alone, to decide whether any remaining density is acceptable.

Acceptance criteria:

- Narrow-width screenshots and validation note exist under `PRIVATE/**`.
- Primary actions remain reachable by simulated clicks.
- Any remaining vertical travel or density friction is recorded with screenshots.
- Local tests and build pass if code changes are made.

Status: completed

### 11. Prepare Final Dogfood Run Contract

Goal: Define the realistic end-to-end dogfood run before executing it.

Main actions:

- Select or create the code-task workflow to dogfood: planner, code worker, test worker, review worker, synthesizer.
- Define the task prompt, expected artifacts, approval gates, cancellation/recovery expectations, and final report shape.
- Define the exact visible-click setup path.
- Define the screenshot checkpoints that later execution steps must capture.

Acceptance criteria:

- A dogfood run contract exists under `PRIVATE/task-graph/canvas-dogfood/<date>/`.
- The contract lists expected nodes, edges, context policies, artifacts, gates, and screenshots.
- The contract explicitly forbids hidden API setup for acceptance.

Status: completed

### 12. Execute Code-Task Dogfood Through Visible UI

Goal: Run the realistic multi-agent workflow through the GUI.

Main actions:

- Open the real app and enter the task graph through visible controls.
- Select or configure the code-task workflow through simulated clicks, typing, and dragging.
- Start the run from visible UI controls.
- Capture running state, worker state, approval state if any, and terminal state.
- Review screenshots during execution so visual regressions are caught before closing the step.
- If the visible setup path fails, preserve the failure screenshot first, then diagnose, fix code, and replay the same visible click path before claiming progress.

Acceptance criteria:

- The dogfood run is started from visible UI controls.
- Screenshots prove setup, start, running, and terminal states.
- Validation note records the full click path and whether any retry was needed.
- Run state and worker outputs are preserved under `PRIVATE/**`.
- No direct fixture-run, worker-start, approval, or cancellation API calls are used for acceptance.
- The validation note explicitly records that the screenshots were reviewed during execution and whether the canvas or inspector still felt crowded in the proved path.

Status: completed

### 13. Inspect Artifacts, Handoffs, And Review Gates Through UI

Goal: Prove users can understand the result without reading internal logs.

Main actions:

- Use visible UI to inspect worker outputs, handoff summaries, artifacts, timeline events, diagnostics, and approvals.
- Open at least one artifact link through the UI.
- Approve or reject a review gate if the dogfood run includes one.
- Preserve screenshots for both the compact run view and the expanded artifact or approval view.
- Review the captured screenshots before ending the step and record whether the artifact or approval surfaces still hide important context behind awkward layout.

Acceptance criteria:

- Artifact and handoff inspection screenshots exist.
- The validation note records clicked artifact links and observed content.
- Approval or rejection evidence is preserved if a gate exists.
- Private reasoning and secrets are not exposed in captured evidence.
- No API-only artifact open, approval, or review action is used to replace a visible UI action.

Status: completed

### 14. Prove Reload, Recovery, And Persistence

Goal: Ensure the user can leave and return without losing the graph workflow.

Main actions:

- Reload the running app after the dogfood run.
- Re-enter task graph through visible controls.
- Confirm selected graph, latest run, moved nodes, edited edges, artifacts, and terminal state are still visible.
- Capture evidence before and after reload.
- Treat reload proof as a visible user journey, not as a state inspection exercise.
- Review the post-reload screenshots before ending the step and record any continuity break, stale panel state, or hidden recovery affordance.

Acceptance criteria:

- Reload evidence shows no `No task yet` dead-end in the tested path.
- Run state and artifact links remain reachable after reload.
- Entry, reload, and re-entry screenshots are preserved.
- The validation note records the visible re-entry path.
- No direct API rescue path is used.
- The validation note explicitly states whether the post-reload UI still feels user-friendly or still requires awkward recovery behavior.

Status: completed

### 15. Publish Final Report And Close Master Step 19

Goal: Produce the final evidence-backed conclusion and close the master plan only if acceptance is met.

Main actions:

- Write a final dogfood report under `PRIVATE/task-graph/canvas-dogfood/<date>/`.
- Summarize UI improvements, dogfood outcome, passed gates, remaining risks, and follow-up ownership.
- Update this plan's progress and mark completed steps.
- Update `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md` Step 19 only if all master acceptance criteria are met.
- Explicitly report whether the click-driven and screenshot-driven execution contract was honored throughout the remaining steps.
- Explicitly summarize whether later agents honored the simulated-click-first rule or tried to bypass it, with links to the preserved evidence.

Acceptance criteria:

- Final report exists and links all relevant screenshots, validation notes, run records, and artifacts.
- This handoff plan records completion and exact remaining risks.
- Master plan Step 19 is marked completed only when the dogfood evidence pack exists and visible-click acceptance is satisfied.

Status: completed

## Progress Log

### 2026-07-07 - Step 15 Completed

- Completed:
  - wrote the final evidence-backed dogfood closure report for the combined canvas/UI and end-to-end workflow pass
  - audited the remaining Step 12 through Step 14 evidence against the simulated-click-first contract
  - confirmed the master Step 19 acceptance criteria are now satisfied
- Files changed:
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step15-final-dogfood-report.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - re-read the Step 19 master acceptance criteria in `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
  - re-read the Step 15 closure criteria in this handoff plan
  - re-audited the preserved Step 12, Step 13, and Step 14 validation notes plus screenshot inventory under `PRIVATE/task-graph/canvas-dogfood/20260707/`
  - confirmed the final report links the code-task run evidence, artifact and approval evidence, and reload continuity evidence
- Outcome:
  - this combined handoff contract is complete
  - the visible-click and screenshot-first closure path was honored for the remaining execution slice
- Remaining risks:
  - browser automation around some artifact clicks remains viewport-sensitive
  - the latest-run dock is improved but still visually dense
  - some preserved evidence still shows mojibake from earlier UI states and notes
- Exact next entry point:
  - none; this handoff plan is complete
- Next step: None.

### 2026-07-07 - Handoff Hardened For Unified Remaining Work

- Completed: Tightened this handoff into a stricter multi-round execution contract that keeps the remaining master-plan work and the remaining canvas/UI optimization work unified under one screenshot-first, simulated-click-first path.
- Files changed:
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - Re-read the active handoff and master Step 19 plan instead of creating a parallel plan.
  - Added a cross-agent enforcement addendum that forbids splitting the remaining work into separate execution tracks.
  - Added stronger per-step obligations for failure screenshots, screenshot review, simulated-click replay after fixes, and blocker logging discipline.
- Blockers: None.
- Exact next entry point:
  - continue Step 12, `Execute Code-Task Dogfood Through Visible UI`, under the stricter screenshot-first and simulated-click-first execution contract
- Next step: Step 12, Execute Code-Task Dogfood Through Visible UI.

### 2026-07-07 - Step 12 Blocked

- Completed: Reproduced the real-app code-task dogfood entry path, preserved the template-switch failure through visible clicks, applied two frontend graph-selection fixes plus one instantiate-success fallback-state fix, and reran the same UI path.
- Files changed:
  - `apps/astrabridge-desktop/src/App.tsx`
  - `apps/astrabridge-desktop/src/api.ts`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-code-task-dogfood-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - real in-app-browser replay from the normal shell into `任务图`
  - visible click attempts on the `Code Fix / Test / Review` template card through DOM-based clicks and unique Playwright locator clicks
  - preserved entry and failure screenshots under `PRIVATE/task-graph/canvas-dogfood/20260707/`
  - diagnosis-only shell checks against sidecar instantiate and current-task routes after visible failure evidence was preserved
  - `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `npm.cmd run build`
- Observed blocker:
  - the `Code Fix / Test / Review` template does not become the visible current graph in the real app after the user-visible click path
  - template cards enter a pending/disabled phase and later recover, but the canvas remains on `Fan-out / Fan-in Research`
  - direct authenticated sidecar instantiate succeeds from shell, so the remaining fault is in the live browser-side instantiate completion path or its follow-on graph-selection state transition
- Additional blocker evidence:
  - later browser replays showed screenshot-visible task-graph controls that were not consistently present in automation-readable DOM surfaces
  - `dom_cua` and Playwright test-id discovery disagree about the presence of the template cards, which weakens automated click certainty until that DOM visibility mismatch is resolved
- Exact next entry point:
  - continue Step 12 by first resolving the browser-automation DOM visibility mismatch for the task-graph workspace, then trace the instantiate request and post-success graph-selection state until the code-task graph actually replaces the fan-out graph on screen
- Next step: Step 12, Execute Code-Task Dogfood Through Visible UI.

### 2026-07-07 - Step 11

- Completed: Wrote the concrete final dogfood run contract so future agents can execute the remaining master Step 19 work without reconstructing intent from chat history.
- Files changed:
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step11-final-dogfood-run-contract.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - Re-read the active handoff plan, master Step 19 contract, desktop fallback template definitions, and sidecar fixture/runtime behavior.
  - Verified the new contract combines the remaining master-plan dogfood work with the remaining canvas/UI acceptance work in one execution artifact.
  - Verified the contract makes simulated clicks, screenshot review, reload proof, and no-hidden-API acceptance explicit.
  - Verified the contract reflects current repository reality: `code_fix_test_review` is the primary code-task dogfood path, while `provider_update_smoke_gate` is required as the supplemental approval-proof path because it is the current fixture that reaches `waiting_on_approval`.
- Blockers: None.
- Next step: Step 12, Execute Code-Task Dogfood Through Visible UI.

### 2026-07-07 - Step 12 Blocker Narrowed

- Completed: Narrowed the Step 12 failure from a possible instantiate failure to a later post-success graph-selection overwrite in the real app.
- Files changed:
  - `apps/astrabridge-desktop/src/App.tsx`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-code-task-dogfood-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - `npm.cmd run build`
  - real in-app-browser replay from the normal shell into `任务图`
  - visible click proof that the code-task graph now appears briefly after clicking `Code Fix / Test / Review`
  - screenshot review confirmed that the same graph later falls back to `Fan-out / Fan-in Research`
  - preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass2-before-code-template-click.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass2-after-code-template-click.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass2-after-code-template-wait8s.png`
- Blockers:
  - `open_template_success` is reached, but a later state source still overwrites the visible current graph back to the research graph after a short delay
  - some full-reload browser replays can land in a workspace setup shell instead of returning to the same task shell
- Exact next entry point:
  - continue Step 12 by tracing which state source wins after `open_template_success`: `taskGraph.data?.graph`, `currentTask.graph_definitions`, persisted fallback graph, or another shell restore path
- Next step: Step 12, Execute Code-Task Dogfood Through Visible UI.

### 2026-07-07 - Step 12.1 Sidebar Project Tree Refinement

- Completed: Landed the user-requested project-tree follow-up inside the active Step 12 surface so the left sidebar now shows clearer project/task hierarchy and caps each expanded project at five visible tasks until explicitly expanded.
- Files changed:
  - `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.tsx`
  - `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-code-task-dogfood-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - `npm.cmd test -- src/features/navigation/ProjectTaskTree.test.tsx`
  - `npm.cmd run build`
  - real in-app-browser replay against `127.0.0.1:4181` with sidecar `127.0.0.1:8802`
  - visible replay path:
    - reloaded the app from the normal shell
    - reviewed the left project/task tree
    - verified the default expanded project stops at five visible tasks
    - clicked the visible `展开显示（还有 25 个）` control
    - reviewed the expanded task list state
  - preserved screenshots:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-sidebar-project-tree-entry-after-indent.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-sidebar-project-tree-expanded.png`
  - screenshots were reviewed during execution, not only captured
- Outcome:
  - task rows now read as a second-level list under each project instead of a flatter stack
  - the default state is visibly capped at five tasks for the expanded project
  - overflow remains reachable through an explicit expand/collapse control
- Remaining friction:
  - long task titles still make the sidebar visually dense, but the hierarchy and overflow behavior are now correct
  - the separate Step 12 blocker remains the code-task graph continuity overwrite, not the sidebar tree
- Exact next entry point:
  - continue Step 12 by returning to the `Code Fix / Test / Review` visible replay and tracing why the graph falls back after `open_template_success`
- Next step: Step 12, Execute Code-Task Dogfood Through Visible UI.

### 2026-07-07 - Step 12 Completed

- Completed: Closed the Step 12 dogfood start path through the visible UI for `Code Fix / Test / Review`.
- Files changed:
  - `apps/astrabridge-desktop/src/App.tsx`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-code-task-dogfood-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `npm.cmd run build`
  - real in-app-browser replay against `127.0.0.1:4181` with sidecar `127.0.0.1:8802`
  - visible replay outcome:
    - entry into `任务图` now returns to the code-task graph
    - a first replay of `夹具运行` produced terminal `COMPLETED` evidence
    - a second replay of the same visible click path, after a minimal pending-visibility fix, produced a clear `RUNNING` screenshot with the visible cancel action
  - preserved screenshots:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass5-shell-before-task-graph.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass5-after-task-graph-entry.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass5-before-code-run.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass5-run-button-locator-failure.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass5-terminal-code-run-after-coordinate-click.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass5b-shell-before-task-graph.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass5b-after-task-graph-entry.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step12-pass5b-running-code-run.png`
  - screenshots were reviewed during execution
- Outcome:
  - Step 12 is no longer blocked on the earlier code-task graph overwrite
  - the visible run-start path for the code-task workflow now has setup, start, running, and terminal evidence
  - no direct fixture-run or worker-start API call was used for acceptance
- Remaining risk:
  - full reload can still fall back to the launcher or setup surface; that continuity problem is explicitly deferred to Step 14
- Exact next entry point:
  - start Step 13 and inspect worker outputs, artifacts, handoffs, and any review-gate evidence through the UI
- Next step: Step 13, Inspect Artifacts, Handoffs, And Review Gates Through UI.

### 2026-07-07 - Step 13 Completed

- Completed:
  - added a top-level primary-artifact row to the expanded run dock so the report entry is reachable without extra internal scrolling
  - fixed `FilesInspectorPanel` so externally provided artifact paths are no longer overwritten by the first sidebar file
  - replayed the visible code-task artifact path in the in-app browser and proved that `Run summary` opens the correct `report.md` in the right-side `Files` inspector
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/InspectorPanels.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/InspectorPanels.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-artifact-handoff-approval-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx src/features/runtime/InspectorPanels.test.tsx`
  - `npm.cmd run build`
  - live success screenshot preserved:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-code-task-primary-artifact-opened-files-inspector-success.png`
- Outcome:
  - Step 13 acceptance is now met with visible artifact-open proof, preserved approval evidence, and no API-only substitution for artifact open or gate resolution
- Exact next entry point:
  - continue with Step 14, `Prove Reload, Recovery, And Persistence`
- Next step: Step 14, Prove Reload, Recovery, And Persistence.

### 2026-07-07 - Step 14 Completed

- Completed:
  - reloaded the app from the live task-graph workflow and proved the app returns to the normal chat shell instead of a `No task yet` dead-end
  - re-entered the task graph through the visible `任务图` control and confirmed the same persisted graph, latest run id, node labels, and edge labels remain visible
  - reopened the visible `Run summary` artifact after reload and confirmed the right-side `Files` inspector still opens the correct `report.md`
- Files changed:
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step14-reload-recovery-persistence-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - live screenshots preserved:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step14-pre-reload-task-graph-state.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step14-post-reload-shell.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step14-reentered-task-graph.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step14-expanded-run-after-reload.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step14-artifact-open-after-reload.png`
- Outcome:
  - Step 14 acceptance is met; reload continuity, re-entry, and post-reload artifact reachability are now preserved through the visible app path
- Exact next entry point:
  - continue with Step 15, `Publish Final Report And Close Master Step 19`
- Next step: Step 15, Publish Final Report And Close Master Step 19.

### 2026-07-07 - Step 10

- Completed: Narrowed the mobile-width blocker from "first viewport is dominated by non-graph UI" to a smaller remaining scroll-model issue, then preserved the resulting narrow-width evidence pack.
- Files changed:
  - `apps/astrabridge-desktop/src/App.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-width-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - Ran `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - Ran `npm.cmd run build`
  - Replayed the narrow-width path at `390 x 844` in the real in-app browser
  - Collapsed the visible left sidebar, reopened `任务图`, selected a visible edge, and triggered the visible `Dry-run` control
  - Reloaded the app, re-collapsed the visible sidebar, reopened `任务图`, and waited for the narrow task-graph surface to recover
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-shell-entry.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-shell-fullpage.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-after-task-graph-entry.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-after-hide-sidebar.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-after-fix-shell.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-after-fix-hide-sidebar.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-after-fix-task-graph-entry.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-entry-usable.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-edge-selected.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-after-dry-run.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-post-reentry.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step10-narrow-post-reentry-after-wait.png`
  - No direct task-graph API call was used for acceptance evidence
- Outcome:
  - task-graph primary actions now enter the first narrow viewport after the user collapses the left sidebar
  - the narrow task-graph toolbar, template rail, and upper canvas are now visible together instead of being buried under long task metadata
  - reload plus narrow re-entry recovered after a short wait in the tested path
- Remaining friction:
  - pointer-wheel scrolling still did not move the narrow task-graph workspace in this browser session, so lower canvas and dock regions remain awkward to reach
  - the user still has to collapse the left sidebar to make the narrow layout comfortable
- Next step: Step 11, Prepare Final Dogfood Run Contract.

### 2026-07-07 - Step 9

- Completed: Finished the real-app desktop viewport replay for the current canvas-first task-graph editor, including template selection, node drag, edge-policy edit, dry-run, fixture run, latest-run expansion, artifact open, reload, and visible re-entry.
- Files changed:
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-desktop-viewport-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - Reused the visible app at `127.0.0.1:4181` with sidecar `127.0.0.1:8802`
  - Clicked `Fan-out / Fan-in Research`, `适配视图`, `Dry-run`, `夹具运行`, and the visible dry-run `打开报告` link
  - Dragged `Research Branch B` on the visible canvas
  - Edited the visible edge inspector for `Research Planner -> Research Branch B` to `History mode = explicit_refs_only` and `History length = 2`
  - Reloaded the app and re-entered task graph by the visible `任务图` control
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-desktop-entry.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-after-template-fit.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-after-node-drag.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-edge-selected.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-after-edge-edit.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-after-dry-run.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-after-fixture-run.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-after-latest-run-expand.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-opened-dry-run-report.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-back-from-report.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-after-reload.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step9-after-reentry-task-graph.png`
  - No direct task-graph API call was used for acceptance evidence
- Outcome:
  - the desktop path no longer shows a critical dead-end in the exercised flow
  - moved node position and edited edge history policy both persisted across reload and visible re-entry
  - dry-run and fixture paths are both reachable by visible controls, and the dry-run report artifact can be opened from the UI
- Remaining friction:
  - the report artifact still opens as a raw file-read response rather than a polished report surface
  - after reload and re-entry, a transient `正在加载任务图...` overlay can still appear while the canvas is already becoming visible
  - the desktop surface remains dense, which is acceptable for Step 9 but should guide Step 10 and later dogfood refinement
- Next step: Step 10, Narrow-Width And Scroll-Ergonomics QA.

### 2026-07-07 - Handoff Reaffirmed As Single Remaining Execution Contract

- Completed: Tightened the active Step 19 handoff so the remaining master-plan work and the canvas beautification/UI optimization work stay unified under one execution contract with stronger screenshot-review and simulated-click obligations.
- Files changed:
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - Re-read the master plan and the active Step 19 handoff.
  - Verified the handoff now explicitly states it is the single governing plan for all remaining task-graph work before Step 19 closure.
  - Added a step execution checklist requiring screenshot review during execution and simulated interaction as the default operating mode.
- Blockers: None.
- Next step: Step 9, Desktop Viewport Canvas QA.

### 2026-07-07 - Step 0

- Completed: Created the combined canvas-and-dogfood handoff plan for the remaining multi-agent task graph work.
- Files changed:
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation: Read `durable-handoff-plan` skill instructions and template, read the current master task graph plan, and aligned this plan with the Step 19 dogfood objective plus the Step 18 canvas/UI backlog.
- Blockers: None.
- Next step: Step 1, Baseline Current Canvas And Dogfood State.

### 2026-07-07 - Step 1

- Completed: Captured the current task-graph canvas and dogfood baseline from the real app before further canvas-first UI work.
- Files changed:
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step1-baseline-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
- Validation:
  - Reloaded the real AstraBridge app in the in-app browser at `127.0.0.1:4181`
  - Observed the shell baseline before entering task graph
  - Clicked the visible top-bar `任务图` control to enter task graph
  - Preserved desktop and narrow-width screenshots:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step1-shell-before-task-graph-desktop.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step1-task-graph-desktop-baseline.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step1-task-graph-narrow-baseline.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step1-task-graph-narrow-fullpage-baseline.png`
  - No direct task-graph API call was used for acceptance evidence
- Blockers:
  - no hard blocker for the plan, but the baseline records three concrete friction areas: reload-to-shell empty state, missing canvas navigation controls, and poor narrow-width composition
- Next step: Step 2, Define Canvas UX Target And Acceptance Checklist.

### 2026-07-07 - Step 2

- Completed: Defined the concrete canvas-first UX target and acceptance checklist for the remaining task-graph UI and dogfood work.
- Files changed:
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_UX_TARGET_AND_ACCEPTANCE.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
- Validation:
  - Re-read the Step 1 baseline note and the task-graph UX principles to ground the target in current evidence rather than preference alone.
  - Verified the new target document covers the required interaction model, information placement rules, visible state definitions, screenshot checkpoints, and click-driven proof recipes.
  - Verified the acceptance checklist maps directly onto upcoming handoff steps 3 through 15.
- Blockers: None.
- Next step: Step 3, Add Canvas Navigation Controls.

### 2026-07-07 - Step 3

- Completed: Added compact canvas-local fit, reset, zoom out, and zoom in controls with real app click validation.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step3-canvas-navigation-validation-note.md`
- Validation:
  - Ran `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - Ran `npm.cmd run build`
  - Reloaded the real AstraBridge app in the in-app browser
  - Clicked the visible top-bar `任务图` control to open the task graph
  - Simulated visible clicks on the canvas header controls for zoom out, fit view, and reset view
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step3-canvas-before-controls.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step3-canvas-after-zoom-out.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step3-canvas-after-fit-view.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step3-canvas-after-reset-view.png`
  - Verified visible scale state transitions: `1.00 -> 0.85 -> 0.55 -> 1.00`
  - No direct task-graph API call was used for acceptance evidence
- Blockers: None for Step 3. Remaining UI debt is now concentrated in node/edge readability and canvas dominance rather than missing navigation mechanics.
- Next step: Step 4, Improve Node Visual States And Hit Targets.

### 2026-07-07 - Step 4

- Completed: Refined node cards for stronger role/status readability, confirmed real node dragging, and proved persisted node position across reload.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step4-node-visual-and-drag-validation-note.md`
- Validation:
  - Ran `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - Ran `npm.cmd run build`
  - Reloaded the real AstraBridge app in the in-app browser
  - Clicked the visible top-bar `任务图` control to open the task graph
  - Clicked `Dry-run` and `Fit view` through visible controls
  - Clicked a visible node to capture selected state, moved the pointer across another visible node to capture hover, and preserved the status-rendered canvas screenshot
  - Dragged `Research Branch B` from the visible left grip area on the canvas
  - Verified persisted position change from `left: 412px; top: 296px;` to `left: 486px; top: 344px;`
  - Reloaded the app and confirmed `Research Branch B` remained at `left: 486px; top: 344px;`
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step4-node-selected-hover-status.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step4-node-mid-drag-slow.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step4-node-after-drag.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step4-node-after-reload.png`
  - No direct task-graph API call was used for acceptance evidence
- Blockers: None for Step 4. The main remaining graph UX bottleneck is now edge selection and edge affordance rather than node readability.
- Next step: Step 5, Improve Edge Visual States And Direct Selection.

### 2026-07-07 - Step 5

- Completed: Promoted edges to first-class canvas objects with directional rendering, larger hit targets, midpoint edge chips, and real click-based selection proof.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step5-edge-visual-and-selection-validation-note.md`
- Validation:
  - Ran `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - Ran `npm.cmd run build`
  - Reloaded the real AstraBridge app in the in-app browser
  - Clicked the visible top-bar `任务图` control to open the task graph
  - Clicked `Dry-run` and `Fit view` through visible controls
  - Clicked a visible node first to establish node-mode baseline in the inspector
  - Hovered and clicked the visible canvas edge chip for `edge_b_merge`
  - Clicked the visible edge line hit area for `edge_plan_b`
  - Verified inspector edge mode switched by canvas-only selection:
    - after chip click, inspector `edge_type = fanin_merge`
    - after line hit click, inspector `edge_type = fanout_branch`
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step5-edge-before-selection.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step5-edge-hover-chip.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step5-edge-after-chip-select.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step5-edge-after-path-select.png`
  - No direct task-graph API call was used for acceptance evidence
- Blockers: None for Step 5. The main remaining UX gap is now canvas-first edge creation rather than edge targeting.
- Next step: Step 6, Add Canvas-First Edge Creation Or Connection Affordance.

### 2026-07-07 - Step 6

- Completed: Added a canvas-first node-to-node edge creation flow, proved invalid same-node validation, and restored created-edge persistence across reload by preferring newer persisted fallback graph state for the active graph.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `apps/astrabridge-desktop/src/App.tsx`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step6-canvas-edge-creation-validation-note.md`
- Validation:
  - Ran `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - Ran `npm.cmd run build`
  - Reloaded the real AstraBridge app in the in-app browser
  - Clicked the visible top-bar `任务图` control and `Fit view`
  - Invalid flow proof:
    - clicked the visible connection affordance on `Research Branch A`
    - clicked `Research Branch A` again as the target
    - observed validation text `Source and target must be different nodes.` and disabled save state
  - Valid flow proof:
    - clicked the visible connection affordance on `Research Synthesizer`
    - clicked `Research Planner` as the target
    - clicked the visible edge save action
    - observed a new fifth edge chip `fallback_edge_6` with text `artifact_handoff`
  - Reload proof:
    - reloaded the page and reopened `任务图`
    - verified the edge-chip inventory still included `fallback_edge_6`
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step6-edge-create-before.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step6-edge-create-start-invalid.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step6-edge-create-invalid-same-node.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step6-edge-create-before-save.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step6-edge-create-after-save.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step6-edge-create-after-reload.png`
  - No direct task-graph API call was used for acceptance evidence
- Blockers: None for Step 6. The remaining canvas UX debt is now more about layout dominance and information density than wiring mechanics.
- Next step: Step 7, Reduce Sidebar Dependence And Increase Canvas Dominance.

### 2026-07-07 - Handoff Tightening

- Completed: Tightened the remaining Step 19 handoff so future agents must execute the rest of the work through screenshot-heavy simulated interaction instead of API-first shortcuts.
- Files changed:
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
- Validation:
  - Re-read the current combined handoff plan and aligned all remaining steps with a stricter screenshot cadence.
  - Verified the plan now requires entry, in-progress, result, and post-reload screenshots where applicable.
  - Verified the plan now states more explicitly that API calls are diagnosis-only after visible evidence has been captured.
- Blockers: None.
- Next step: Step 7, Refine Sidebar And Inspector As Secondary Surfaces.

### 2026-07-07 - Step 7

- Completed: Refined the sidebar and inspector into secondary surfaces so the canvas regains clear desktop dominance without losing direct access to detailed edge configuration.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step7-sidebar-inspector-validation-note.md`
- Validation:
  - Ran `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - Ran `npm.cmd run build`
  - Reloaded the real AstraBridge app in the in-app browser
  - Re-entered task graph from the visible top-bar `任务图` control
  - Clicked the visible `更多设置` disclosure in the edge inspector to prove advanced settings remained reachable after the layout change
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step7-entry-before-layout-fix.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step7-result-after-layout-fix.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step7-in-progress-advanced-settings.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step7-in-progress-advanced-settings-scrolled.png`
  - No direct task-graph API call was used for acceptance evidence
- Outcome:
  - the left rail is lighter and less visually dominant because node and edge collections are no longer forced open by default
  - the canvas regains width in the desktop layout
  - the edge inspector core fields no longer show the obvious enum clipping that motivated this step
  - advanced settings remain available by real simulated click
- Blockers:
  - no Step 7 blocker remains
  - minor remaining friction: the lower portion of expanded advanced edge settings still requires scroll travel at the default desktop viewport
- Next step: Step 8, Improve Run Status And Timeline Presentation Around The Canvas.

### 2026-07-07 - Step 8

- Completed: Refined the latest-run dock into a compact-by-default status surface with clearer summary chips plus secondary disclosure sections for timeline, diagnostics, and worker outputs, then proved the running and cancelled states through visible fixture-run clicks.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step8-run-status-timeline-validation-note.md`
- Validation:
  - Ran `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - Ran `npm.cmd run build`
  - Reloaded the real AstraBridge app in the in-app browser
  - Re-entered task graph from the visible top-bar `任务图` control
  - Clicked the latest-run summary row to move between expanded and compact dock states
  - Clicked the visible `可取消夹具` action to start a real running fixture
  - Clicked the visible `取消运行` action to drive the same dock into terminal cancelled state
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step8-entry-expanded-before-run-fix.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step8-expanded-dock-before-running-fixture.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step8-compact-dock-before-running-fixture.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step8-running-fixture-expanded-dock.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step8-cancelled-fixture-expanded-dock.png`
  - No direct task-graph API call was used for acceptance evidence
- Outcome:
  - compact and expanded run states are both visible and reachable by direct click
  - running and cancelled states remain legible without the dock overtaking the canvas
  - timeline and diagnostics now read as secondary expandable slices rather than one continuous detail wall
- Blockers:
  - no Step 8 blocker remains
  - minor remaining friction: the live fixture replay did not expose worker-output artifacts, so that subsection remained empty in the real app proof even though the UI structure is now in place
- Next step: Step 9, Desktop Viewport Canvas QA.

### 2026-07-07 - Step 13 Sidebar Follow-up

- Completed: Landed the user-requested sidebar tree follow-up during the active Step 13 window so second-level task rows read closer to the official app while preserving the five-task preview rule.
- Files changed:
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-sidebar-project-tree-indent-followup-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - Ran `npm.cmd test -- src/features/navigation/ProjectTaskTree.test.tsx`
  - Reloaded the real app in the in-app browser at `127.0.0.1:4181` with sidecar `127.0.0.1:8802`
  - Reviewed the visible left sidebar before expansion
  - Clicked the visible `展开显示（还有 25 个）` control through simulated browser interaction
  - Preserved screenshot evidence:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-sidebar-project-tree-indent-before-expand.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-sidebar-project-tree-indent-after-expand.png`
- Outcome:
  - second-level task rows now sit further inside their parent project grouping
  - each project still defaults to at most five visible tasks until the user explicitly expands overflow
  - the requested hierarchy was validated through the live UI rather than an internal shortcut
- Exact next entry point:
  - continue Step 13 and inspect task-graph artifacts, handoffs, and review-gate evidence through the UI
- Next step: Step 13, Inspect Artifacts, Handoffs, And Review Gates Through UI.

### 2026-07-07 - Step 13 Progress Update

- Completed:
  - captured live code-task run-dock evidence for worker outputs, artifact links, and handoff surfaces
  - captured live provider-gate evidence for pending approval and approval resolution through visible UI actions
  - landed a product fix so task-graph artifact clicks now route into the existing right-side file inspector instead of depending only on raw sidecar file-read navigation
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/App.tsx`
  - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-artifact-handoff-approval-validation-note.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`
  - `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- Validation:
  - `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `npm.cmd run build`
  - live screenshots preserved:
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-code-task-graph-entry.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-code-task-expanded-run-panel.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-provider-gate-template-selected.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-provider-gate-pending-approval.png`
    - `PRIVATE/task-graph/canvas-dogfood/20260707/step13-provider-gate-approved.png`
- Remaining blocker:
  - the post-fix live artifact-open replay still needs one more browser pass because the in-app browser automation session became unstable during reload
- Exact next entry point:
  - reload the app, reopen `任务图`, click a visible code-task artifact, and capture the right-side `文件` inspector proving the new in-app artifact preview path
- Next step: Step 13, Inspect Artifacts, Handoffs, And Review Gates Through UI.
