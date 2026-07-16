# Multi Agent GUI Orchestration Handoff Plan

## Total Objective

Build a product-grade multi-agent orchestration layer in AstraBridge that is actually operable by normal users from the GUI: template-first workflow composition, explicit task assignment, bounded subagent execution, artifact-first handoff, approval gates for risky actions, and click-verified usability in the running app.

This plan is narrower than generic "multi-agent support". It focuses on the part most worth landing next: a user-friendly orchestration surface that forces agents to prove real operability by simulated clicks, not just unit tests or local mocks.

## Priority Slice

The highest-value slice to land first is:

- a visible entry into the multi-agent workspace,
- one bounded template-first workflow,
- direct node assignment and handoff inspection,
- one review-gated action,
- one cancel or retry recovery path,
- and preserved click-driven evidence that proves a normal operator can complete the flow.

If later agents need to trade off scope, they must protect this slice first and defer breadth work around extra protocols, generic chat patterns, or decorative UI.

## Scope

In scope:

- Template-first multi-agent workflow entry in the desktop GUI
- Node-level role assignment, worker responsibility, and bounded context flow
- Codex subagent-backed worker execution where available, with fallback isolated lanes
- Artifact-first inter-agent handoff
- Human review gates for risky actions
- Real in-app-browser or Playwright click validation for every GUI-facing milestone
- Durable evidence packs under `PRIVATE/**`

Out of scope for this plan:

- Open external A2A server compatibility
- Unbounded free-form group chat orchestration
- Hidden autonomous external writes
- Replacing GUI validation with API-only or unit-only proof

## Related Context Files

- `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`
- `docs/ARCHITECTURE.md`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
- `apps/astrabridge-desktop/src/App.tsx`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`

## Constraints And Attention Notes

1. `Project -> Task` remains the top-level product boundary.
2. Multi-agent workers, subagent lanes, provider threads, and scratchpads stay internal unless intentionally surfaced as bounded workflow state.
3. Critical machine state must be structured and durable; chat history is not the source of truth.
4. Every node and edge must declare explicit context rules.
5. Secrets, vault material, cookies, auth headers, API keys, and provider raw secrets must never be written into plans, artifacts, traces, screenshots, or logs.
6. Preserve validation artifacts, screenshots, traces, reports, and raw non-secret diagnostics under `PRIVATE/**`.
7. Every UI-facing step must include simulated-click validation in the running app. A step is not complete if the feature only works through code inspection, tests, or direct API calls.
8. For GUI workflows that claim to be user-friendly, the validating agent must actually drive the flow by clicking visible controls, opening panels, confirming state transitions, and preserving evidence.
9. If the simulated-click path reveals overlay issues, dead buttons, confusing flows, hidden state, or ambiguous copy, fix those as part of the step rather than deferring them as purely cosmetic.
10. Prefer bounded templates and explicit approvals over autonomous open-ended agent behavior.
11. "User-friendly" means a future agent acting like a normal user can discover the entry point, complete the main flow, understand blocked states, and inspect outputs without relying on route forcing, hidden debug controls, direct store mutation, or chat-only tribal knowledge.
12. For any step that changes the operator path, the validating agent must preserve both the successful click path and any pre-fix failing screenshot or trace that justified the change when such a failure was encountered.

## Evidence Convention

- Default artifact root for this plan: `PRIVATE/multi-agent-gui-orchestration/<step-id>/<YYYYMMDD>/`
- Minimum evidence for every GUI-facing step:
  - one screenshot before or during the key interaction,
  - one screenshot after the expected state transition,
  - one concise validation note with the exact click path, typed values, observed result, and remaining friction,
  - and, when the first attempt failed, one preserved pre-fix failure screenshot or trace.
- Evidence should be understandable by a later agent without replaying chat history.

## Adjustment Policy

Agents may adjust filenames, substeps, implementation details, commands, test shapes, evidence layout, and sequencing when repository facts require it.

Agents must not:

- weaken the click-driven validation gate
- replace GUI proof with API-only proof
- broaden the scope into generic agent chat
- remove approval boundaries for risky actions
- hide unresolved usability defects behind documentation alone
- replace real click-driven operator proof with URL forcing, hidden fixture injection, or internal state poking as the claimed acceptance path

If a planned approach becomes infeasible, record the blocker, the evidence, attempted alternatives, and a substitute path that preserves the product intent.

## Execution Rules

1. Read this plan at the start of every turn that executes under it.
2. Start from the earliest numbered step that is not `completed`, unless the user explicitly redirects.
3. Complete exactly one full numbered step per turn.
4. Update this plan before stopping.
5. For every GUI-facing step, preserve at least one screenshot and one concise validation note under `PRIVATE/**`.
6. For every GUI-facing step, the validating agent must perform manual-equivalent simulated clicks, not just DOM mutation or direct HTTP requests.
7. If a click path fails, record the failure mode and fix or isolate it before marking the step complete.
8. Every GUI-facing validation note must include a click recipe: starting surface, clicked controls, typed values, drag path if any, observed UI state, and remaining friction.
9. If a workflow claims to support user assignment, inspection, approval, cancellation, or recovery, the agent must prove that exact path from the visible app surface.
10. End each turn with the exact next entry point.

## Simulated Interaction Gate

Future agents executing this plan must treat simulated interaction as a product gate:

1. Start from the running AstraBridge app whenever feasible.
2. Reach the changed surface from a visible entry point by clicking, not only by forcing a route or mutating hidden state.
3. Perform the claimed workflow through real controls: buttons, lists, inputs, tabs, dialogs, drag paths, and review actions.
4. Preserve success evidence and, when encountered, the failing pre-fix evidence under `PRIVATE/**`.
5. Record any remaining friction that would matter to a normal user, even when the backend behavior is technically correct.
6. If the agent struggles to discover, operate, or understand the workflow, that friction counts as a product defect and must be fixed or explicitly recorded before the step is marked complete.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Handoff Plan
- Current step: Step 1, Freeze The Product Slice And GUI Acceptance Bar
- Next step: Step 1, Freeze The Product Slice And GUI Acceptance Bar
- Last updated: 2026-07-07

## Execution Steps

### 0. Create Durable Handoff Plan

Goal: Create a persistent execution contract for the multi-agent GUI orchestration slice.

Main actions:

- Define the objective, scope, constraints, execution rules, and acceptance bar.
- Make simulated-click validation a hard requirement.
- Leave an unambiguous next entry point for future agents.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes objective, scope, constraints, execution rules, numbered steps, and progress log.
- Simulated-click validation is explicitly mandatory for GUI-facing steps.

Status: completed

### 1. Freeze The Product Slice And GUI Acceptance Bar

Goal: Lock the first useful multi-agent GUI slice and define what "user-friendly" means operationally.

Main actions:

- Write a short scope note defining the supported first workflows: planner-worker-synthesizer, provider-update smoke gate, and code-fix-test-review.
- Define GUI acceptance checks: discoverable entry, no hidden required controls, no overlay-blocked primary actions, stable labels, visible approval state, artifact inspectability, and recoverable blocked states.
- For each supported workflow, define the click-driven proving path from visible entry to inspectable result.
- Define what evidence an agent must preserve when claiming usability.

Acceptance criteria:

- A scope artifact exists on disk.
- The artifact defines both supported workflows and GUI usability gates.
- The artifact explicitly requires a click path for create, configure, run, inspect, review, and one recovery action.

Status: not started

### 2. Define The Structured Worker Contract For GUI Orchestration

Goal: Make task assignment and inter-agent exchange durable and machine-readable.

Main actions:

- Define or refine contracts for worker role, node assignment, handoff artifact bundle, approval state, and timeline event shape.
- Ensure downstream workers consume declared artifacts and summaries rather than opaque transcript dumps.
- Record how GUI state maps onto machine state.

Acceptance criteria:

- Contract artifact or contract update exists on disk.
- A later agent can implement GUI and runtime behavior without relying on chat context.
- Approval and handoff state have explicit structured vocabularies.

Status: not started

### 3. Inventory Existing Runtime And UI Surfaces

Goal: Reuse existing task-graph, runtime, and sidecar surfaces rather than creating parallel state.

Main actions:

- Audit the current task-graph workspace, runtime worker execution, approval handling, artifact preview, and task persistence paths.
- List reusable pieces, missing pieces, and coupling risks.
- Identify where click-driven UX currently breaks or becomes confusing.

Acceptance criteria:

- An inventory artifact exists with file-level references.
- The artifact makes the next implementation surface choices obvious.
- Known click-path risks are listed explicitly.

Status: not started

### 4. Productize Template Entry And Assignment Flow

Goal: Make it straightforward for a user to create a bounded multi-agent workflow from the GUI.

Main actions:

- Add or refine template cards and inspector controls for worker assignment, model/provider choice, and context posture.
- Ensure primary actions are visible and reachable without hidden prerequisite steps.
- Preserve stable layout for node cards and inspectors.
- Require the validating agent to instantiate the workflow from the visible app surface and preserve the actual click sequence.

Acceptance criteria:

- A user can open the workspace, choose a template, and inspect assigned worker roles from the GUI.
- Simulated-click validation proves the full entry path in the running app.
- Validation notes include the exact clicked controls and what became visible after each major step.
- No blocking overlay or dead-end control remains in the tested path.

Status: not started

### 5. Make Context Sharing Explicit And Reviewable

Goal: Prevent accidental full-history leakage between agents.

Main actions:

- Surface edge or handoff policy controls for artifact inclusion, summary inclusion, history limits, and private-memory exclusion.
- Add validation for unsafe context policies.
- Ensure the GUI exposes enough state for users to understand what each worker receives.

Acceptance criteria:

- A user can inspect and edit context-sharing rules from the GUI.
- Invalid or unsafe policies are blocked before run.
- Simulated-click validation proves policy editing and persistence.

Status: not started

### 6. Bind Worker Nodes To Bounded Execution Lanes

Goal: Map GUI worker nodes onto real execution lanes without leaking private scratchpads.

Main actions:

- Reuse Codex subagent-capable runtime surfaces where available.
- Add fallback isolated worker lanes where subagent support is unavailable.
- Persist parent-child lineage in task-owned state only.

Acceptance criteria:

- Worker execution can start from a graph run without exposing raw private lane state.
- Parent-child lineage is durable and inspectable.
- Tests prove sensitive reasoning fields do not leak into persisted downstream state.

Status: not started

### 7. Make Artifact-First Handoff The Default

Goal: Ensure agent coordination works through inspectable artifacts instead of transcript archaeology.

Main actions:

- Persist worker outputs as structured artifacts and summaries.
- Surface artifact chips and previews in the run UI.
- Make downstream input construction depend on artifacts plus policy, not raw chat replay.

Acceptance criteria:

- Worker output artifacts are visible from the GUI.
- Downstream handoff state is structured and attributable.
- Simulated-click validation proves a user can open a produced artifact from the run view.

Status: not started

### 8. Add Human Review Gates For Risky Actions

Goal: Prevent silent high-risk writes, installs, paid provider calls, or external writeback.

Main actions:

- Add node-level or graph-level gate states for risky actions.
- Surface pending approval clearly in the GUI with visible approve and reject actions.
- Persist approval decisions into structured run state and timeline events.
- Force validation through one reject path and one approve path driven from the real GUI.

Acceptance criteria:

- High-risk nodes block with a clear reason.
- Approval and rejection both update durable state correctly.
- Simulated-click validation proves reject and approve flows in the running app.

Status: not started

### 9. Build A User-Comprehensible Run Timeline

Goal: Make multi-agent execution understandable without reading logs.

Main actions:

- Show node start, progress, completion, block, approval, artifact creation, warning, and failure events.
- Make it easy to move from a timeline entry to the relevant node or artifact.
- Keep the layout scannable in dense operational use.

Acceptance criteria:

- A user can identify what happened, where it blocked, and what artifacts were produced.
- Timeline state survives refresh and reopen.
- Simulated-click validation proves run inspection in the live app.

Status: not started

### 10. Add Cancellation, Retry, And Recovery

Goal: Keep the orchestration system operable when runs do not finish cleanly.

Main actions:

- Add cancel and retry behavior for bounded fixture or live runs.
- Persist interrupted state and recovery diagnostics.
- Ensure retry behavior is explicit and does not silently mutate old evidence.
- Require the validating agent to trigger cancellation or retry from the visible run surface and verify the post-reload state.

Acceptance criteria:

- A user can cancel a run and see durable interrupted state.
- A retry path exists and remains bounded.
- Simulated-click validation proves cancel, reload, and recovery visibility.

Status: not started

### 11. Add Template-Specific Guided Defaults

Goal: Turn the orchestration system into practical workflows instead of a raw graph editor.

Main actions:

- Refine defaults for planner-worker-synthesizer, provider-update smoke gate, and code-fix-test-review.
- Attach recommended model/provider hints, artifact expectations, and approval posture.
- Keep templates editable after instantiation.

Acceptance criteria:

- Each supported template can be instantiated and inspected from the GUI.
- Defaults are explicit and conservative.
- Simulated-click validation covers at least two templates end to end in fixture mode.

Status: not started

### 12. Build A Click-Driven Usability Gate

Goal: Force future agent work to pass a product usability bar rather than merely compiling.

Main actions:

- Define a reusable validation checklist for manual-equivalent simulated clicks.
- Require screenshot, click trace summary, observed friction points, and pass/fail judgment.
- Encode common failure modes: blocked controls, invisible state, confusing approval flow, broken artifact links, and reload regression.
- Include a hard rule that no GUI fix is accepted without a preserved click recipe and a post-reload verification when the changed flow persists state.

Acceptance criteria:

- A reusable GUI validation artifact exists on disk.
- Later steps can reference the same click-driven acceptance rules.
- The checklist is concrete enough that another agent can run it without reading prior chat.
- The checklist explicitly distinguishes acceptable fixture seeding from unacceptable hidden-state acceptance proof.

Status: not started

### 13. Package The Work As An Agent-Friendly Repair Workflow

Goal: Make future agents able to diagnose and repair orchestration UX defects with less manual supervision.

Main actions:

- Write a repair runbook or skill-oriented guidance for reproducing, inspecting, fixing, and revalidating task-graph UX defects.
- Require the agent to use simulated clicks to confirm the real fix.
- Define preservation rules for screenshots, traces, logs, and before/after notes.

Acceptance criteria:

- A durable runbook or skill artifact exists on disk.
- The workflow is specific to AstraBridge's orchestration surfaces.
- It explicitly bans claiming a fix without click-driven proof.

Status: not started

### 14. Dogfood A Real Multi-Agent Workflow

Goal: Prove the system works as a product feature rather than a lab demo.

Main actions:

- Run a realistic workflow in the GUI using planner, worker, reviewer, and synthesizer roles.
- Preserve graph definition, run timeline, worker outputs, approval events, and summary artifacts.
- Record what stayed confusing or fragile.

Acceptance criteria:

- A full evidence pack exists under `PRIVATE/**`.
- The workflow was configured and inspected through simulated GUI clicks.
- Remaining risks are documented with concrete follow-up ownership.

Status: not started

### 15. Write The Next-Stage Expansion Note

Goal: Leave a clean bridge to future work such as external A2A compatibility or richer GUI composition.

Main actions:

- Summarize what is now stable, what remains internal-only, and what can expand next.
- Separate productized surfaces from experiments.
- Identify which follow-on tasks belong in a new plan versus this one.

Acceptance criteria:

- A concise expansion note exists on disk.
- It clearly separates stable product behavior from unfinished experimental behavior.
- The next plan boundary is explicit.

Status: not started

## Progress Log

### 2026-07-07 - Step 0 Completion

- Completed: Created a durable handoff plan for the multi-agent GUI orchestration slice, centered on the most valuable next outcome: making AstraBridge's multi-agent workflow genuinely operable from the GUI with hard simulated-click validation.
- Files changed: `PLAN/MULTI_AGENT_GUI_ORCHESTRATION_HANDOFF_PLAN.md`
- Validation: Verified the plan is written on disk with explicit objective, scope, constraints, execution rules, acceptance criteria, and mandatory click-driven proof requirements.
- Blockers: None.
- Next step: Step 1, Freeze The Product Slice And GUI Acceptance Bar.

### 2026-07-07 - Plan Hardening For User-Friendly Execution

- Completed: Tightened the plan around the part most worth landing next: a bounded, template-first multi-agent GUI slice that must be proven by real simulated clicks. Added a priority slice, an evidence convention, a stronger simulated-interaction gate, and step-level acceptance language that now forces create-configure-run-inspect-review-recovery proof rather than vague "GUI works" claims.
- Files changed: `PLAN/MULTI_AGENT_GUI_ORCHESTRATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read the full plan after patching.
  - Verified that constraints, execution rules, the simulated interaction gate, Step 1, Step 4, Step 8, Step 10, and Step 12 all explicitly require click-driven evidence.
- Blockers: None.
- Next step: Step 1, Freeze The Product Slice And GUI Acceptance Bar.
