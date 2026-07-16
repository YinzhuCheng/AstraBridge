## Total Objective

Close the remaining productization gap for AstraBridge Agent Graph after the major Step 11 buildout: finish human-approval-boundary dogfood, package the graph system into reusable operator-facing flows, and produce a final acceptance handoff that another agent can execute from the visible product surface without reconstructing prior chat history.

This plan is a focused execution slice for the remaining Agent Graph work. It does not replace:

- `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`
- `PLAN/AGENT_GRAPH_GUI_RUNTIME_EXECUTION_CHECKLIST.md`

It narrows the remaining route into concrete, auditable steps with explicit evidence and acceptance gates.

## Deliverables

- A repaired visible approval-gated graph path that shows waiting, approve, reject, and recovery behavior from the GUI.
- A preserved evidence pack for each remaining step under `PRIVATE/agent-graph-dynamic-workflow/**`.
- A click-validated template and reuse path that proves the graph system is reusable instead of demo-only.
- Operator-facing documentation that matches the live product surface.
- A final release-style handoff report that separates proven, blocked, and deferred paths.

## Constraints And Attention Notes

1. Use the visible product surface in the in-app browser as the primary validation path for every UI-facing step.
2. Simulated clicks, typing, hovering, dragging, resizing, scrolling, collapsing, expanding, reload, and reopen flows are mandatory where relevant.
3. Do not use hidden API writes, store mutation, fixture preload tricks, or console-side state mutation as acceptance evidence when the visible path exists.
4. Screenshots are mandatory and must be taken frequently enough to catch layout and interaction regressions:
   - starting state;
   - after each major interaction;
   - final state;
   - one constrained-width or sidebar-stressed state when layout is touched.
5. Preserve all evidence under `PRIVATE/agent-graph-dynamic-workflow/**`. Do not delete artifacts, logs, raw reports, or screenshots unless the user explicitly names cleanup targets.
6. Never persist API keys, bearer tokens, cookies, auth headers, vault secrets, or plaintext key-file contents in plans, screenshots, logs, or artifacts.
7. Keep one canonical graph contract across GUI authoring, code-first import/export, dry-run, fixture run, and runtime inspection.
8. Do not claim completion for a GUI step if the behavior is only proven by backend state and not by the visible product surface.
9. When adjusting the route, preserve the quality bar: click-driven validation, durable evidence, typed graph semantics, context isolation, and operator usability.
10. Official OpenAI direct live verification remains out of scope unless the user explicitly reauthorizes it later.

## Adjustment Policy

Agents may reasonably adjust substeps, filenames, commands, evidence layout, implementation details, and sequencing when repository evidence requires it. Those adjustments must not weaken the total objective, downgrade visible validation into API-only validation, split GUI and code execution paths, remove typed communication guarantees, or replace runtime closure with cosmetic-only UI work.

If a route becomes stale, record the evidence, diagnosis, route change, preserved quality bar, and exact next step before continuing.

## Evidence Review And Plan Revision Policy

Before executing the next step, review whether the current route is stale. Trigger a review when any of these apply:

1. the visible UI contradicts the intended operator flow;
2. backend state proves a run exists, but the desktop UI does not hydrate it correctly;
3. a step appears complete only because of test coverage while the real app still fails;
4. the next step would polish templates or docs while the approval/runtime path is still broken;
5. a completed step's acceptance criteria no longer support the total objective;
6. a proposed fix would bypass the visible path instead of repairing it.

Every revision must record:

- evidence inspected;
- diagnosis;
- route change;
- what must not be weakened;
- exact next step.

## Execution Rules

1. Each agent turn executing this plan must begin by reading this file plus the three related plans listed in the objective section.
2. Start from the earliest numbered step whose status is not `completed`, unless the user explicitly redirects.
3. Complete exactly one numbered step per turn unless the user explicitly asks for more.
4. Update this plan before stopping.
5. A step may be marked `completed` only when all of its acceptance criteria are satisfied.
6. Every UI-facing step must use the in-app browser and visible interaction paths first.
7. For every UI-facing step, preserve:
   - `step-report.md`
   - `validation-note.md`
   - `commands.txt`
   - `screenshots/`
8. When the native in-app screenshot path is flaky, preserve the failure and then use the repository-standard fallback capture path on the same URL.
9. Each turn must end with a strong handoff: completed work, files changed, validation run, blockers, evidence-driven revisions, and exact next step.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Re-baseline The Remaining Blockers
- Next step: Step 1, Re-baseline The Remaining Blockers
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: Create this focused remaining-work handoff plan and make the next entry point explicit.

Main actions:

- Define the remaining Agent Graph objective.
- Record the required constraints, acceptance discipline, evidence policy, and step sequence.
- Point future agents to the current highest-leverage starting step.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes objective, constraints, adjustment policy, evidence review policy, current progress, execution steps, acceptance criteria, and progress log.
- The next step is unambiguous.

Status: completed

### 1. Re-baseline The Remaining Blockers

Goal: Reconfirm the real remaining blockers from the current repo and live product surface before any further implementation.

Main actions:

- Read the current master plan, subordinate GUI/runtime plan, and GUI runtime checklist.
- Inspect the current approval-boundary evidence and the current desktop/runtime code paths that feed run refs into the graph workspace.
- Reopen the app in the in-app browser, navigate to the approval-gated graph path through visible UI actions, and confirm the latest real failure mode.
- Write a short blocker baseline under `PRIVATE/agent-graph-dynamic-workflow/step12-approval-baseline/<YYYYMMDD>/`.

Acceptance criteria:

- The blocker baseline distinguishes repository-proved behavior, visible-UI failure, and inferred hypotheses.
- The baseline names the exact next implementation target, not a vague area.
- Screenshots and/or preserved DOM reports show the current operator-visible failure state.

Status: not started

### 2. Repair Run-Panel And Approval-Panel Hydration

Goal: Make approval-gated fixture runs surface their live run state and approval controls in the visible graph workspace.

Main actions:

- Repair the desktop state flow so a newly started approval-gated run immediately hydrates the current graph workspace with the returned `run_ref`.
- Cover fixture start, approve, reject, cancel, and recover mutation paths so local state stays aligned until query refresh catches up.
- Add or update focused tests around the desktop state-selection logic and approval-panel rendering path.
- Preserve a repair report under `PRIVATE/agent-graph-dynamic-workflow/step12-approval-hydration-fix/<YYYYMMDD>/`.

Acceptance criteria:

- A freshly started approval-gated run shows the run panel and approval panel without requiring a hidden refresh trick.
- Focused desktop tests cover the new hydration path and pass.
- Type-checking passes for touched desktop files.

Status: not started

### 3. Validate Human-Approval Boundary Dogfood From The Visible UI

Goal: Close the remaining approval-boundary product proof from the real app surface.

Main actions:

- Open the running AstraBridge app in the in-app browser.
- Navigate into an approval-gated graph only through visible product controls.
- Exercise waiting state, at least one reject path, and at least one approve path. Exercise cancel or recover where the product surface supports it.
- Cross-check the visible behavior against durable run-state artifacts and preserve the evidence pack under `PRIVATE/agent-graph-dynamic-workflow/step12-human-approval-boundary-dogfood/<YYYYMMDD>/`.

Acceptance criteria:

- Approval state is visibly understandable to an operator from the product surface.
- Reject blocks continuation and approve advances the run in a way that matches durable run-state artifacts.
- The evidence pack preserves screenshots, commands, validation notes, and durable run-state references.

Status: not started

### 4. Package Template Discoverability And Reuse Paths

Goal: Make the graph system reusable through the live product surface rather than a one-off engineering demo.

Main actions:

- Audit and tighten the visible template library for the core templates already in scope: provider update, code fix/test/review, fan-out research, document analysis, multimodal adapter, and blank graph.
- Reduce low-signal text and redundant UI if it still interferes with quick template selection.
- Validate at least one click-driven instantiate -> reopen -> reuse path from the visible UI.
- Preserve evidence under `PRIVATE/agent-graph-dynamic-workflow/step13-template-packaging/<YYYYMMDD>/`.

Acceptance criteria:

- Common templates are discoverable from the GUI without relying on chat history or source inspection.
- At least one reuse path is visibly validated from the real product surface.
- The evidence explicitly records any remaining template gaps instead of hiding them.

Status: not started

### 5. Align Operator Documentation With The Live Product

Goal: Ensure operator-facing instructions match the real graph product behavior and constraints.

Main actions:

- Review the existing repository-local graph operation skill and related docs against the live product behavior.
- Update only the pieces that are stale after the approval-boundary and template work.
- Include explicit operator expectations for visible UI usage, screenshot cadence, approval gates, recovery, and known product limits.
- Preserve a short docs-alignment note under `PRIVATE/agent-graph-dynamic-workflow/step13-operator-doc-alignment/<YYYYMMDD>/`.

Acceptance criteria:

- Operator documentation matches the real visible product path for the core graph flows.
- The docs name known limitations rather than implying unsupported behavior exists.
- Another agent can use the docs plus repo files to operate a representative graph path without prior chat context.

Status: not started

### 6. Run A Focused Final GUI Regression Sweep

Goal: Verify that the repaired graph surface still behaves coherently across the most important operator paths.

Main actions:

- Recheck conversation -> task graph entry, template instantiate, node/edge inspect, run monitor, recovery, and approval-boundary flows through visible interaction.
- Include at least one constrained-width or stressed-sidebar pass.
- Preserve a focused regression sweep under `PRIVATE/agent-graph-dynamic-workflow/step14-final-gui-regression/<YYYYMMDD>/`.

Acceptance criteria:

- The key operator flows are revalidated on the visible product surface after the remaining fixes.
- Screenshots capture both normal and stressed layout states.
- Any remaining rough edges are explicitly listed with severity and scope.

Status: not started

### 7. Run Final Validation And Secret-Safety Checks

Goal: Produce a clean validation gate for the remaining execution slice.

Main actions:

- Run the focused desktop tests and type-check baseline for touched UI files.
- Run any additional focused sidecar tests required by the approval-boundary path.
- Perform a quick secret-safety review over touched reports, screenshots, logs, and changed files.
- Preserve command output summaries under `PRIVATE/agent-graph-dynamic-workflow/step14-final-validation/<YYYYMMDD>/`.

Acceptance criteria:

- Required tests and type-checks are passing or explicitly blocked with preserved evidence.
- The validation pack records what was run and what remains intentionally out of scope.
- The touched evidence pack and changed files do not persist secrets.

Status: not started

### 8. Write The Final Release Handoff Report

Goal: Close this remaining-work slice with a resume-friendly acceptance package.

Main actions:

- Summarize the remaining-work execution outcome across approval, reuse, docs, and regression results.
- Separate proven paths, blocked paths, and deferred paths.
- Update this plan and any owning plan status fields needed to keep the next entry point unambiguous.
- Preserve the final report under `PRIVATE/agent-graph-dynamic-workflow/final-remaining-slice/<YYYYMMDD>/`.

Acceptance criteria:

- A final handoff report exists on disk.
- The report clearly distinguishes what is proven, what is blocked, and what is deferred.
- Future agents can resume from the updated plan state without reconstructing prior chat history.

Status: not started

## Progress Log

### 2026-07-09 - Step 0

- Completed: Created a focused remaining-work handoff plan for the Agent Graph productization slice after the large Step 11 buildout.
- Files changed: `PLAN/AGENT_GRAPH_REMAINING_EXECUTION_HANDOFF_PLAN.md`
- Validation: Read the durable handoff skill, the master productization plan, the subordinate GUI/runtime execution plan, and the companion execution checklist; then converted the remaining work into a concrete step sequence with explicit acceptance gates and visible-UI evidence rules.
- Blockers: None.
- Next step: Step 1, Re-baseline The Remaining Blockers.
