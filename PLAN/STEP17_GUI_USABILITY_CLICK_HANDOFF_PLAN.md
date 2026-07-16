# Step 17 GUI Usability Click Handoff Plan

## Total Objective

Drive the multi-agent task graph UI through manual-equivalent simulated clicks until the product behaves like a usable operator surface rather than an API demo. The immediate target is Step 17 of `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`.

## Constraints And Attention Notes

1. The agent must operate the real running app in the in-app browser, not only unit tests or direct HTTP calls.
2. Every defect claim must be backed by click evidence: screenshot, trace note, DOM observation, or preserved console/network symptom.
3. Preserve evidence under `PRIVATE/task-graph/step17-gui-usability/<date>/`.
4. Do not delete existing task-graph artifacts, logs, screenshots, or fixture outputs.
5. Keep fixes scoped to tested usability defects. Do not mix in unrelated refactors.
6. If a path is blocked by environment configuration, record the exact user-visible blocker and continue with the next click path instead of silently skipping coverage.
7. The current hard blocker is reload restoration after `cancellable fixture -> cancel -> reload`; the remaining plan centers on closing that user-visible dead-end first.

## Adjustment Policy

Agents may adjust selectors, viewport sizes, exact fixture choices, screenshot filenames, or the browser-control mechanism when the live app changes, but they must not weaken the click-driven proof. The required interaction classes remain mandatory: open, select, drag, wire, configure, dry-run, fixture-run, inspect, cancel, reload, and review gate handling where available.

## Current Progress

- Current status: completed
- Current step: completed
- Next step: hand off to `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md` Step 18
- Last updated: 2026-07-07

## Execution Steps

### 1. Establish click-validation environment

Goal: Bring up a current-source sidecar and a visible dogfood app session that the agent can operate repeatedly.

Main actions:

- Start or reuse a current-source sidecar on a fresh port.
- Open the dogfood app in the in-app browser with the sidecar query parameter.
- Confirm the browser is visible and the `Task graph` entry can be reached.
- Create the evidence directory for this run.

Acceptance criteria:

- A live app URL and sidecar URL are recorded.
- The in-app browser is visible and interactive.
- The evidence directory exists under `PRIVATE/task-graph/step17-gui-usability/<date>/`.

Status: completed

### 2. Execute baseline operator flow by simulated clicks

Goal: Prove the primary workflow can be completed from the GUI without hidden API assistance.

Main actions:

- Click into `Task graph`.
- Select a template from the template cards.
- Drag at least one node and verify the position persists after refresh.
- Create or edit at least one edge and set its context policy through the inspector.
- Run `Dry-run` and capture the readiness state.
- Run `Fixture run` or `Cancellable fixture` from the visible toolbar.

Acceptance criteria:

- Screenshots show each major waypoint.
- No step depends on direct API execution to advance the visible UI.
- Any failure is captured as a user-visible dead-end with evidence.

Status: completed

### 3. Inspect run-state usability and artifact discoverability

Goal: Verify that users can understand what happened after a run starts or fails.

Main actions:

- Open the latest run panel after a fixture run.
- Check timeline readability, worker cards, artifact links, diagnostics, and status badges.
- Open at least one artifact from the UI and verify the preview page is legible.
- If a run is cancellable, cancel it through the visible control and verify durable state after reload.

Acceptance criteria:

- The run panel exposes enough information to diagnose progress or failure without reading logs.
- At least one artifact is opened from a visible UI control.
- Cancellation and reload behavior is either proven or recorded as a concrete defect with evidence.

Status: completed

### 4. Reproduce reload regression by pure simulated clicks

Goal: Force the current blocker to appear from the visible product surface so the bug and the eventual fix are both user-real.

Main actions:

- From the visible app, click into `Task graph`.
- Select the `Fan-out / Fan-in Research` template from the visible template cards.
- Start `Cancellable fixture` from the visible toolbar or a manual-equivalent coordinate click inside the visible button bounds.
- Wait for visible `running`, then cancel from the visible `Cancel run` control.
- Reload the app in the in-app browser.
- Re-enter `Task graph` only through visible navigation.
- Record whether the app lands on `No task yet`, reopens an older graph, or restores the cancelled run correctly.

Acceptance criteria:

- A preserved note records the exact click recipe, the run id seen before reload, and the post-reload visible state.
- At least one screenshot exists for pre-reload and post-reload states.
- No hidden API call is used to advance the UI path.

Status: completed

### 5. Diagnose restoration mismatch with preserved frontend and sidecar evidence

Goal: Isolate whether the dead-end comes from task restoration, selected-graph restoration, latest-run selection, or hit-target layering.

Main actions:

- Preserve the visible broken UI state with screenshots.
- Capture the relevant frontend state assumptions from the code paths that restore current task, current graph, and latest run.
- Capture sidecar state snapshots that prove whether `current_task`, `graph_definitions`, and `graph_run_refs` are still present after reload.
- Write a short mismatch summary that states exactly which layer disagrees with the visible UI.

Acceptance criteria:

- Evidence clearly separates frontend-visible failure from sidecar-persisted state.
- The next code change target is narrowed to concrete files and functions.
- The diagnosis can be handed to another agent without replaying the whole investigation.

Status: completed

### 6. Land the smallest restoration fix that can close the dead-end

Goal: Remove the reload-time user dead-end without broad refactors.

Main actions:

- Change only the code paths needed for current-task, selected-graph, latest-run, or hit-target restoration.
- Keep the fix scoped to the tested defect family.
- Add or update focused regression tests where the local test surface can cover the repaired logic.
- Build the desktop app and rerun the affected local tests.

Acceptance criteria:

- The intended fix is in the repo with narrowly scoped file changes.
- Local tests covering the changed behavior pass.
- The live click path has not yet been claimed fixed until Step 7 re-proves it.

Status: completed

### 7. Re-prove the blocked path in the visible app

Goal: Verify the fix from a user perspective, not just from code or tests.

Main actions:

- Repeat Step 4 exactly from the visible app.
- Use simulated clicks for template selection, fixture start, cancellation, reload, and workspace re-entry.
- Confirm that the same run id remains visible after reload and that the app does not fall into `No task yet`.

Acceptance criteria:

- Before/after screenshots exist for the repaired path.
- The visible app restores the expected task, graph, and cancelled run.
- No direct API call is used to rescue the UI path.

Status: completed

### 8. Run viewport and density pass on the repaired path

Goal: Catch layout failures that only appear outside one desktop size.

Main actions:

- Repeat the key click flow at at least two viewport sizes.
- Capture screenshots for template cards, canvas, inspector, and latest-run panel.
- Record any text overlap, clipped controls, hidden actions, or unstable layout shifts.

Acceptance criteria:

- Evidence includes at least two viewport sizes.
- Any layout defect is either fixed in the same step or logged as actionable backlog with screenshot proof.

Status: completed

### 9. Re-prove graph manipulation ergonomics by simulated clicks

Goal: Ensure the editor surface is actually operable for a normal user after the restoration fix.

Main actions:

- Move at least one node through manual-equivalent pointer interaction.
- Create or edit at least one edge through visible controls.
- Change one context-policy setting through the inspector.
- Refresh and verify the edited state persists.

Acceptance criteria:

- Screenshots or trace notes prove drag, edge edit, and inspector edit paths.
- Persisted state survives refresh.
- Any browser-control limitation is explicitly distinguished from a product bug.

Status: completed

### 10. Publish the preserved UI QA report and master-plan update

Goal: Leave a future agent with a clear evidence-backed state of the GUI.

Main actions:

- Write or update `validation-note.md` under the Step 17 evidence directory.
- Record app URL, sidecar URL, tested templates, viewport sizes, click recipe, defects found, fixes landed, remaining risks, and next recommended action.
- Update the master execution plan with the completed Step 17 result and exact next entry point.

Acceptance criteria:

- A preserved QA report exists on disk.
- The report names exact screenshots and artifact paths.
- The next agent can continue from the report without reading chat history.

Status: completed

## Mandatory Click Contract

The following actions must be executed from the visible app surface, using browser automation that is equivalent to user behavior:

1. Open `Task graph`.
2. Select a template card.
3. Start `Dry-run`, `Fixture run`, or `Cancellable fixture`.
4. Approve or reject a review gate when that path is in scope.
5. Open an artifact link from the run panel.
6. Cancel a running fixture when that path is in scope.
7. Reload the app and re-enter the workspace.

Allowed assistance:

- DOM inspection to locate visible controls.
- Playwright or in-app-browser selector clicks.
- Coordinate clicks when a visible control exists but the normal selector click path is unreliable.
- Read-only sidecar calls for diagnosis after the user-visible path has already failed.

Forbidden substitutions:

- Starting, cancelling, approving, or restoring a run by direct API call instead of through the UI.
- Claiming a bug fixed from tests or code inspection alone.
- Skipping a dead-end path because it is inconvenient to automate.

## Hard Acceptance Gate

Step 17 is not complete unless the agent has personally driven the app by simulated clicks and preserved evidence. Unit tests, API success, or code inspection alone are insufficient.

## Progress Log

### 2026-07-07 - Plan Created

- Created this handoff plan as the execution contract for the next usability-focused slice.
- The plan explicitly forces simulated-click operation in the in-app browser so later agents must validate from the user surface instead of stopping at APIs or local tests.
- Next step: 1. Establish click-validation environment.

### 2026-07-07 - Mid-step Progress And Blocker

- Completed in the visible app:
  - opened `Task graph`
  - switched templates
  - edited node configuration
  - created an edge through GUI controls
  - ran dry-run
  - exercised provider approval reject/approve paths
  - opened a worker artifact from the latest-run panel
  - exercised a fresh cancellable fan-out run through visible `running` and `cancelled`
- Landed scoped fixes while validating:
  - mouse drag compatibility in `TaskGraphWorkspace.tsx`
  - active-graph targeting and selected-graph persistence in `App.tsx`
- Preserved evidence under `PRIVATE/task-graph/step17-gui-usability/20260707/`.
- Current blocker:
  - reload can still reopen into `No task yet` or an older graph/run even while sidecar `GET /api/project/tasks` still reports a valid `current_task`
  - because of that, the final reload-proof usability acceptance for Step 17 is not yet satisfied
- Exact next entry point:
  - debug reload-time current-task restoration in `apps/astrabridge-desktop/src/App.tsx`, then rerun the live `fanout template -> cancellable fixture -> cancel -> reload` proof from the visible UI

### 2026-07-07 - Plan Tightening For User-Friendly Enforcement

- Reworked the remaining Step 17 work into a stricter execution contract centered on the current reload dead-end.
- Split the remaining work into explicit slices: reproduce by clicks, diagnose mismatch, land minimal fix, re-prove by clicks, then run viewport and ergonomics passes.
- Added a mandatory click contract so later agents must perform the critical operator actions from the visible app surface and cannot substitute direct API calls for run start, cancel, approval, artifact open, or reload recovery.
- Next step: 4. Reproduce reload regression by pure simulated clicks.

### 2026-07-07 - Step 4 Reproduced By Clicks

- Completed the pure-click reproduction contract from the visible app surface.
- Reproduced the reload dead-end with this visible path:
  - opened `Task graph`
  - selected `Fan-out / Fan-in Research`
  - started `Cancellable fixture`
  - cancelled the running fixture
  - reloaded the app
  - observed visible `No task yet`
  - re-entered `Task graph` through the visible topbar control
- Preserved the visible run id from the run surface before reload:
  - `graph-run-fixture-20260707T081549221850-353f31`
- Preserved screenshots for before-run, running-before-cancel, after-cancel, after-reload-before-reentry, and after-reentry.
- Important validation note:
  - no direct API call was used to start, cancel, or restore the run path in this reproduction
  - the dead-end is user-real and now freshly evidenced under `PRIVATE/task-graph/step17-gui-usability/20260707/validation-note.md`
- Exact next entry point:
  - diagnose why reload lands on visible `No task yet` even while the page still shows the current Step 11 task title and the graph can be reopened immediately afterward
- Next step: 5. Diagnose restoration mismatch with preserved frontend and sidecar evidence.

### 2026-07-07 - Step 5 Diagnosis Complete

- Compared the reproduced visible dead-end against current frontend restore code and current sidecar snapshots.
- Proven on the sidecar:
  - `current_task_id`, `current_thread_id`, the active provider-thread entry, the newest selected graph, and the reproduced cancelled run all remain persisted after reload
  - the reproduced run `graph-run-fixture-20260707T081549221850-353f31` still exists as `cancelled`
- Narrowed the frontend mismatch to reload sequencing in `apps/astrabridge-desktop/src/App.tsx`:
  - `currentTask` is derived only from `projectTasks.data?.current_task`
  - when `currentTask` is temporarily null during reload, `selectedThreadId` can still fall back to `project.current_thread_id`
  - but `selectedThreadProfileId` does not have an equally strong reload-safe fallback, so `selectedThread` can remain disabled until later query state arrives
  - while that gap exists, the shell can render the generic `No task yet` fallback even though the sidecar still has a valid current task and active lane
- Diagnosis outcome:
  - this is no longer a sidecar graph-persistence issue
  - this is not primarily a task-graph selection issue either
  - the next code change should target frontend task/thread restoration sequencing and misleading empty-state fallback behavior during reload convergence
- Exact next entry point:
  - implement a minimal reload-safe restoration fix in `apps/astrabridge-desktop/src/App.tsx`, centered on `selectedThreadId`, `selectedThreadProfileId`, and the empty-state/header fallback while current-task restoration is still in flight
- Next step: 6. Land the smallest restoration fix that can close the dead-end.

### 2026-07-07 - Step 6 Minimal Restoration Fix Landed

- Landed a scoped reload-restoration repair in the desktop frontend only.
- Added `apps/astrabridge-desktop/src/features/runtime/taskThreadRestore.ts` with two focused helpers:
  - `resolveCurrentProjectTask()` restores the active task from `project.current_task_id` and the cached task list when `current_task` is temporarily null during reload
  - `resolveSelectedThreadProfileId()` restores a usable profile for a known thread id from task provider-thread metadata, thread summary metadata, or `project.default_profile_id`
- Wired those helpers into `apps/astrabridge-desktop/src/App.tsx` so the reload path no longer depends exclusively on `projectTasks.data?.current_task` and no longer leaves the thread query disabled just because the task payload lags the project-level thread id.
- Tightened the shell title fallback so the chat header prefers `selectedThreadSummary.displayName` or `currentTask.title` before rendering the generic empty label.
- Added focused regression coverage in `apps/astrabridge-desktop/src/features/runtime/taskThreadRestore.test.ts`.
- Local validation completed:
  - `npm.cmd test -- src/features/runtime/taskThreadRestore.test.ts src/features/runtime/taskGraphRunRefs.test.ts src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `npm.cmd run build`
- Important boundary:
  - this step intentionally does not claim the live click path is fixed yet
  - the repaired path must still be proven in the visible app by simulated clicks in Step 7
- Next step: 7. Re-prove the blocked path in the visible app.

### 2026-07-07 - Step 7 Live Path Re-Proved

- Replayed the repaired path from the visible app surface:
  - opened `Task graph`
  - selected `Fan-out / Fan-in Research`
  - started `Cancellable fixture`
  - waited for visible `RUNNING`
  - cancelled the run from the visible `Cancel run` action
  - reloaded the app
  - inspected the post-reload first screen before reopening `Task graph`
  - reopened `Task graph` from the visible topbar
- Proven visible run id for this repaired replay:
  - `graph-run-fixture-20260707T084635122346-bcdedc`
- Proven visible outcomes:
  - before reload, the run reached visible `RUNNING`
  - after cancel, the same run id settled to visible `CANCELLED`
  - after reload, the first screen did not fall into `No task yet`
  - after reopening `Task graph`, the same run id remained visible and still showed `CANCELLED`
- Important method note:
  - the browser-control session timed out during the reload wait and had to reconnect to the same in-app browser tab
  - after reconnect, the first visible screen was inspected before reopening `Task graph`
  - no direct API call was used to start, cancel, restore, or rescue the UI path
- Preserved evidence:
  - `task-graph-step17-reprove-before-run.png`
  - `task-graph-step17-reprove-running-before-cancel.png`
  - `task-graph-step17-reprove-after-cancel.png`
  - `task-graph-step17-reprove-after-reload-before-reentry.png`
  - `task-graph-step17-reprove-after-reconnect.png`
  - `task-graph-step17-reprove-after-reentry.png`
- Outcome:
  - the original reload-time dead-end is cleared for the repaired path
  - Step 17 can now move on to viewport and density verification instead of restoration debugging
- Next step: 8. Run viewport and density pass on the repaired path.

### 2026-07-07 - Step 8 Viewport And Density Pass

- Exercised the repaired task-graph path at two viewport sizes:
  - `1280 x 720`
  - `390 x 844`
- Proven in both sizes:
  - the workspace still rendered `Fan-out / Fan-in Research`
  - the latest-run state still showed the cancelled fan-out fixture
  - the app did not fall into `No task yet`
- Preserved screenshots:
  - `task-graph-step17-viewport-desktop.png`
  - `task-graph-step17-viewport-mobile.png`
  - `task-graph-step17-viewport-mobile-mid.png`
  - `task-graph-step17-viewport-mobile-lower.png`
  - `task-graph-step17-viewport-mobile-canvas-clip.png`
  - `task-graph-step17-viewport-mobile-inspector-clip.png`
- Findings:
  - desktop width no longer shows critical overlap or hidden primary actions
  - desktop inspector density still clips long enum values such as `required_output_only` and `human_and_machine`; this is logged as actionable backlog with screenshot proof
  - narrow/mobile width stacks the task-graph surface vertically rather than overlapping, but canvas/run/inspector content sits far below the first viewport and requires substantial vertical travel
  - attempted internal-surface clip screenshots for the mobile canvas and inspector returned blank images, so the narrow-layout placement proof relies on the successful mobile screenshot plus live geometry reads
- Outcome:
  - Step 8 is complete because viewport evidence now exists for at least two sizes and the remaining density issues have been logged with preserved screenshot proof
- Next step: 9. Re-prove graph manipulation ergonomics by simulated clicks.

### 2026-07-07 - Step 9 Graph Manipulation Ergonomics Re-Proved

- Replayed the graph-editing surface from the visible app:
  - opened `Task graph`
  - selected `Fan-out / Fan-in Research`
  - brought the visible `Research Branch A` node card into view
  - dragged that node card through manual-equivalent pointer movement
  - selected the visible edge chip `Research Planner -> Research Branch A`
  - changed edge context settings in the visible inspector to:
    - `History mode = explicit_refs_only`
    - `History length = 2`
  - saved the edge
  - reloaded the app
  - reopened `Task graph` and verified the same node position and edge settings persisted
- Proven persisted values:
  - `Research Branch A` moved from `left: 320px; top: 80px;` to `left: 408px; top: 121px;`
  - after reload, `Research Branch A` still rendered at `left: 408px; top: 121px;`
  - `edge_plan_a` still showed `History mode = explicit_refs_only` and `History length = 2` after reload
- Preserved evidence:
  - `task-graph-step17-ergonomics-before-move.png`
  - `task-graph-step17-ergonomics-node-visible.png`
  - `task-graph-step17-ergonomics-after-drag.png`
  - `task-graph-step17-ergonomics-edge-edited.png`
  - `task-graph-step17-ergonomics-after-reload.png`
- Important note:
  - unrelated Statsig browser-console networking noise appeared during some browser operations but did not block or alter the visible task-graph workflow
- Outcome:
  - the remaining graph-manipulation ergonomics path is now live-proven rather than only unit-tested
- Next step: 10. Publish the preserved UI QA report and master-plan update.

### 2026-07-07 - Step 10 Report Published And Step 17 Closed

- Published the final preserved QA result into:
  - `PRIVATE/task-graph/step17-gui-usability/20260707/validation-note.md`
- Recorded the latest layout repair that makes the graph canvas the primary middle-column surface instead of burying it under stacked cards.
- Final UI repair scope:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
- Local validation for the latest repair:
  - `npm.cmd test -- src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `npm.cmd run build`
- Final evidence added:
  - `task-graph-ui-after-canvas-priority-fix.png`
- Final acceptance call:
  - the earlier reload dead-end is cleared in live click proof
  - the graph editor is now visually prioritized in the tested desktop flow
  - remaining issues are backlog-level density and narrow-layout ergonomics, not tested-path blockers
- Next step:
  - hand off to master-plan Step 18, `Add Documentation And In-App Help That Does Not Replace UX`
