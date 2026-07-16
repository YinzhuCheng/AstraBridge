# Agent Graph Multimodal Product Execution Plan

## Total Objective

Deliver a product-grade AstraBridge Agent Graph slice that behaves like a general-purpose, multimodal, multi-model workflow builder rather than a form-heavy internal tool. The target is "ComfyUI-style visual orchestration for arbitrary agent tasks" with one canonical graph contract shared by GUI and code, bounded parallel subagents, default context isolation, typed handoff contracts, capability-aware multimodal routing, and click-verified operator usability in the real app.

This plan is a delivery-focused companion to `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`. The broader plan remains the architecture umbrella; this plan defines the concrete execution path and acceptance bar for the next implementation wave.

## Deliverables

- A canonical graph execution slice that can define, dry-run, compile, and execute bounded agent workflows through one shared contract.
- A subagent-capable runtime with typed input/output envelopes, explicit context isolation, durable lineage, and bounded parallel fan-out/fan-in.
- A multimodal capability adapter path that exposes only supported provider/model modality combinations and routes typed artifacts safely.
- A canvas-first GUI flow where users can add nodes, connect edges, edit prompt/contracts, inspect run state, and validate workflows mainly from the canvas.
- A code-authored interface for import, export, lint, diff, migrate, and execution of the same graph contract.
- A click-driven evidence pack and validation record under `PRIVATE/agent-graph-multimodal-product/**`.
- A maintainer skill/runbook that teaches agents to repair graph-runtime and graph-UI defects by operating the real product through simulated clicks instead of hidden state shortcuts.

## Related Context Files

- `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `PLAN/AGENT_GRAPH_VISUAL_ORCHESTRATOR_EXECUTION_HANDOFF_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_CLICK_DRIVEN_PRODUCTIZATION_PLAN.md`
- `PLAN/MULTIMODAL_ADAPTER_FAMILY_CONTRACT.md`
- `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`
- `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_compiler.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/providers/`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
- `apps/astrabridge-desktop/src/features/runtime/`
- `apps/astrabridge-desktop/src/styles.css`

## Product Slice

The first acceptable product slice under this plan is:

- one visible graph entry path from the main app;
- one canvas-first graph editing path;
- one bounded subagent workflow with at least parallel workers and one synthesizer;
- typed edge contracts and inspectable handoffs;
- one multimodal-capability-aware node configuration path;
- one cancellation or retry recovery path;
- one code-authored graph round-trip path;
- and one click-driven dogfood pack proving a normal operator can complete the flow.

Breadth beyond this slice is secondary. If later agents need to trade scope, they must protect this slice first.

## Constraints And Attention Notes

1. `Project -> Task` remains the product boundary. Agent Graph state, runs, subagents, artifacts, and worker lineage stay scoped under tasks.
2. GUI-authored graphs and code-authored graphs must compile into the same canonical contract. No shadow format is allowed.
3. Default subagent context isolation is mandatory. Full parent transcript inheritance, unrelated scratchpads, provider-private reasoning, and raw secrets must not cross edges implicitly.
4. Every node must declare execution policy, provider/model routing, tool policy, output contract, and UI metadata. Every edge must declare a typed handoff contract and context policy.
5. Multimodal support must be capability-aware. Unsupported provider/model and modality combinations must be blocked or clearly warned before execution.
6. UI work is not complete until it has been validated through simulated clicks in the running app. API-only proof does not count when a visible product path exists.
7. GUI validation must prefer real interaction: click, drag, type, hover, resize, scroll, collapse, expand, and reload. Hidden route forcing, direct store mutation, console injection, or internal API calls do not count as the primary acceptance path.
8. The canvas is primary. Avoid card stacking, oversized typography, redundant low-semantic text, unnecessary frames, inspector overflow, fixed-width sidebars that waste space, and decorative clutter that reduces usable canvas area.
9. When GUI behavior is touched, preserve frequent screenshots so later agents can see the actual operator experience instead of only reading code diffs.
10. High-risk actions such as installs, source mutation, external writes, paid provider calls, or widened permissions must remain approval-gated and auditable.
11. Preserve traces, screenshots, manifests, reports, typed envelopes, capability evidence, and sanitized logs under `PRIVATE/**` by default.
12. Never persist API keys, cookies, auth headers, vault material, desktop key contents, or secret-bearing raw payloads in plans, artifacts, screenshots, logs, or staged changes.
13. Main-agent orchestration should stay shallow by default. One supervisor layer plus parallel workers plus one synthesizer or reviewer is the normal pattern.
14. Code and UI execution claims must be backed by deterministic tests plus click-driven evidence where applicable.

## Adjustment Policy

Agents may reasonably adjust filenames, substeps, commands, selectors, viewport choices, implementation details, sequencing, or evidence layout when repository evidence requires it. Those adjustments must not change the total objective, weaken the click-driven usability gate, split GUI and code into incompatible systems, remove typed handoff contracts, relax context isolation, or replace runtime work with cosmetic-only changes.

If a planned route becomes stale, agents must revise the plan before continuing and log the evidence, diagnosis, route change, what must not be weakened, and the exact next step.

## Evidence Review And Plan Revision Policy

Before executing the next step, future agents must check whether a plan review is needed. Trigger a review when:

1. source or runtime evidence contradicts the assumed architecture or readiness;
2. fixture success does not prove the generic runtime path;
3. a step proves only backend or only GUI while the product slice requires both;
4. GUI screenshots show user-hostile layout, discoverability, or inspection problems;
5. provider/model capability evidence invalidates a planned multimodal path;
6. the next step would polish around the edges while the current blocker is still runtime, subagent execution, typed communication, or UX operability;
7. a proposed shortcut would bypass simulated clicks, capability gating, or context-isolation guarantees.

Every plan revision must record:

- evidence inspected;
- diagnosis;
- route change;
- what must not be weakened;
- exact next step.

## Execution Rules

1. Each agent turn executing under this plan must begin by reading this file and checking the evidence-review triggers.
2. Start from the earliest numbered step whose status is not `completed`, unless the user explicitly redirects.
3. Complete exactly one numbered step per turn unless the user explicitly asks otherwise.
4. Update this plan before stopping.
5. A step may be marked `completed` only when every acceptance criterion is satisfied.
6. GUI-facing steps must be validated through simulated interaction in the real running app.
7. Every GUI-facing validation note must include the starting surface, exact clicked controls, typed values, drag or resize path if any, observed result, and remaining friction.
8. If a visible click path fails, preserve the failing screenshot or trace before switching to lower-level diagnosis.
9. Runtime-facing steps must preserve deterministic tests plus at least one durable sanitized artifact such as a compiled plan, run manifest, input envelope, output envelope, or event trace.
10. Each turn must end with a strong handoff: completed work, files changed, validation run, evidence path, blockers, revisions, and the exact next step.

## Simulated Interaction Gate

Any agent executing GUI-facing work under this plan must:

1. open the actual AstraBridge app;
2. reach the changed surface from visible controls when feasible;
3. operate the product by simulated clicking, typing, dragging, hovering, scrolling, collapsing, expanding, and resizing instead of only using hidden APIs;
4. take screenshots repeatedly enough to catch obvious usability defects;
5. treat common UX problems as product defects: card stacking, text too large, fixed sidebars wasting space, meaningless icons, duplicate metadata, low-signal text occupying prime space, clipped controls, broken scroll areas, and confusing task/run inspection flows;
6. avoid marking the step complete until the changed path still behaves correctly after reload or reopen when persistence is involved.

## Evidence Convention

- Default artifact root: `PRIVATE/agent-graph-multimodal-product/<step-id>/<YYYYMMDD>/`
- Backend steps must preserve reports, test output summaries, sanitized logs, and any generated contract or run artifacts.
- Runtime steps must preserve compiled plans, run manifests, event traces, node input envelopes, node output envelopes, worker lineage, retry or cancel evidence when relevant, and concise validation notes.
- GUI-facing steps must preserve:
  - one initial surface screenshot;
  - one or more in-flow screenshots;
  - one final state screenshot;
  - one reload or reopen screenshot when persistence matters;
  - one concise validation note with the exact click path and remaining friction.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Freeze Product Slice And Acceptance Matrix
- Next step: Step 1, Freeze Product Slice And Acceptance Matrix
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: Create this execution plan and make the next entry point explicit.

Main actions:

- Define the concrete multimodal agent-graph product objective.
- Record constraints, execution rules, evidence rules, and acceptance bar.
- Set the first executable step.

Acceptance criteria:

- Plan file exists on disk.
- The plan includes objective, deliverables, constraints, adjustment policy, evidence-review policy, current progress, numbered steps, acceptance criteria, and progress log.
- The next step is unambiguous.

Status: completed

### 1. Freeze Product Slice And Acceptance Matrix

Goal: Convert the broad product ambition into a concrete first-release acceptance matrix.

Main actions:

- Audit the current repo state against the target slice: canonical graph, runtime, subagent execution, multimodal capability gating, code round-trip, and GUI operability.
- Define the exact v1 acceptance matrix covering backend, runtime, GUI, and evidence.
- Record which capabilities are mandatory, deferred, blocked, or explicitly out of scope for this slice.

Acceptance criteria:

- A written acceptance matrix exists under `PRIVATE/agent-graph-multimodal-product/step1-acceptance-matrix/<YYYYMMDD>/`.
- The matrix names exact must-pass flows and exact non-goals.
- The matrix identifies the highest-leverage blocker to implement first after planning.

Status: not started

### 2. Finish Subagent Node Runtime Contract

Goal: Treat a graph subagent node as a first-class bounded runtime unit.

Main actions:

- Map node execution policy to spawn parameters including provider/model, reasoning effort, tools, permissions, timeout, collaboration mode, and bounded subagent policy.
- Persist durable worker lineage and runtime contract snapshots.
- Explicitly block unsupported nested or worktree-sharing modes with clear evidence instead of silently accepting them.

Acceptance criteria:

- Deterministic tests prove a graph node can spawn a bounded subagent in a local fake runtime.
- Worker bindings preserve graph run id, node id, worker thread id, spawn policy, runtime contract, and downstream handoff references.
- Unsupported subagent modes fail explicitly and predictably.

Status: not started

### 3. Prove Parallel Fan-Out And Join Semantics

Goal: Demonstrate that multiple workers can run concurrently and merge through typed contracts.

Main actions:

- Implement or finish bounded parallel scheduling for independent ready nodes.
- Implement join readiness and downstream unlock behavior for fan-in nodes.
- Preserve timing and event evidence for parallel execution.

Acceptance criteria:

- Tests prove at least two workers run in parallel and a join node waits for the declared rule.
- Failure and blocked-worker cases produce clear downstream state.
- Evidence artifacts show parallel worker ordering and join behavior.

Status: not started

### 4. Finish Cancellation, Retry, Resume, And Partial Execution

Goal: Make long-running graph runs recoverable and operator-safe.

Main actions:

- Implement cancel active run, retry failed node, rerun selected node, rerun downstream, and resume interrupted runs.
- Preserve recovery traces and versioned artifacts.
- Expose enough run state for the operator to understand what will rerun.

Acceptance criteria:

- Tests cover cancel, retry, rerun, and resume flows.
- Runtime preserves deterministic recovery state and does not silently overwrite prior artifacts.
- Evidence artifacts document the recovery path.

Status: not started

### 5. Land Capability-Aware Multimodal Port Routing

Goal: Ensure graph nodes can expose multimodal inputs and outputs only when capability evidence supports them.

Main actions:

- Define or harden typed ports for text, image, audio, document, structured JSON, tool result, and agent report.
- Connect node/provider/model selection to official-source-backed capability metadata and local smoke evidence.
- Block unsupported modality routes before execution.

Acceptance criteria:

- Tests cover valid and invalid provider/model modality routes.
- At least one fixture graph passes a typed multimodal artifact across nodes.
- Capability-gated UI metadata exists for later GUI rendering.

Status: not started

### 6. Finish Code-Authored Graph Round-Trip

Goal: Make code-first workflow authoring a first-class path instead of a secondary import helper.

Main actions:

- Harden import, export, lint, diff, migrate, and execute commands or APIs for the canonical graph.
- Ensure graph files preserve runtime policy, typed contracts, and multimodal metadata across round-trips.
- Add or refine example graphs covering common workflow patterns.

Acceptance criteria:

- A code-authored graph can be linted, dry-run, imported, exported, diffed, migrated, re-imported, and executed through the same contract.
- Round-trip tests prove required fields are not lost.
- Example files are preserved without secrets.

Status: not started

### 7. Rebuild Task Graph Shell Around The Canvas

Goal: Make the task-graph surface feel like an operator tool instead of stacked forms.

Main actions:

- Rework layout so the canvas is the primary surface and sidebars are secondary, collapsible, and user-resizable.
- Remove low-signal framing, redundant panels, oversized typography, and wasteful cards from the task-graph view.
- Preserve stable selectors for later click validation.

Acceptance criteria:

- Screenshots show the canvas occupying the majority of the available task-graph workspace.
- Left and right graph sidebars are resizable or collapsed without layout breakage.
- The operator can still discover key controls without prime-space clutter.

Status: not started

### 8. Build Node Library, Wiring, And Icon Semantics

Goal: Make node creation and edge understanding fast and visual.

Main actions:

- Build or refine a node palette for common agent roles, tools, artifacts, transforms, gates, and outputs.
- Use icons for common node types and edge attributes, with hover tooltips for meaning.
- Reduce on-canvas text clutter and tighten typography and spacing.

Acceptance criteria:

- A user can add a small workflow from visible UI controls without API shortcuts.
- Nodes and edges use icons and tooltips for common semantics instead of verbose labels everywhere.
- Screenshots show improved visual density and readability.

Status: not started

### 9. Finish Inspector Editing For Prompt, Policy, And Contracts

Goal: Let users configure nodes and edges without drowning the canvas in forms.

Main actions:

- Move detailed editing into a cleaner inspector with collapsible advanced sections.
- Support prompt template, structured output, provider/model, subagent policy, edge handoff contract, and context policy editing.
- Add inline validation before save.

Acceptance criteria:

- A user can edit node and edge contract fields through visible controls.
- Invalid edits are blocked with understandable feedback.
- Screenshots show a cleaner inspector with smaller typography and better section hierarchy.

Status: not started

### 10. Finish Run Monitor And Handoff Inspection

Goal: Give operators a clear view of run state, outputs, and edge communication.

Main actions:

- Show node and run states on the canvas and in the inspector.
- Let users inspect node inputs, outputs, artifacts, worker lineage, and edge handoffs through visible controls.
- Move verbose low-signal run text out of prime canvas space.

Acceptance criteria:

- A click-driven validation flow can inspect at least one node output and one edge handoff.
- Run states are visible and understandable without opening developer tools.
- Screenshots show readable density and reduced clutter.

Status: not started

### 11. Dogfood One Full GUI Workflow Through Simulated Interaction

Goal: Prove a normal operator can complete the target slice through the real app.

Main actions:

- Open the real app and create or import a graph through visible controls.
- Edit nodes and edges, run fixture mode, inspect outputs, and exercise one recovery path through simulated clicks.
- Preserve screenshots, click notes, and run artifacts.

Acceptance criteria:

- The workflow is completed from the visible product surface without hidden state injection as the primary path.
- Evidence includes entry screenshots, in-flow screenshots, final state, reload or reopen confirmation, and concise click notes.
- Remaining UX friction is explicitly recorded.

Status: not started

### 12. Create Agent Repair Skill And Runbook

Goal: Teach future agents how to maintain and repair this product slice safely.

Main actions:

- Create or update a skill/runbook covering graph proposal, graph repair, code-first round-trip, runtime validation, multimodal capability checks, and GUI click validation.
- Require simulated-click proof for GUI claims and deterministic tests for runtime claims.
- Include safety rules for provider calls, installs, writes, and secrets.

Acceptance criteria:

- A skill or runbook exists on disk and references the canonical graph contract.
- It includes concrete repair and validation procedures.
- It explicitly forbids claiming UI success from API-only proof.

Status: not started

### 13. Optional Authorized Provider-Backed Pilot

Goal: Verify one real provider-backed bounded run when the user authorizes it.

Main actions:

- Select a low-risk graph with limited budgets and no external writes.
- Run one provider-backed execution with strict evidence preservation.
- Compare real-provider behavior with fixture behavior.

Acceptance criteria:

- If provider authorization is absent, the step records `blocked` and does not call providers.
- If authorized, evidence classifies failures precisely and preserves sanitized request or response summaries only.
- No secrets are persisted.

Status: not started

### 14. Final Product Gate And Handoff Pack

Goal: Close the slice with repeatable validation and a clean handoff for future maintainers.

Main actions:

- Run tests, GUI dogfood, evidence review, and a quick secret scan over touched files and artifacts.
- Write a release-style report summarizing supported, unsupported, blocked, and deferred capabilities.
- Update current progress and next recommended slice.

Acceptance criteria:

- A final report exists under `PRIVATE/agent-graph-multimodal-product/final/<YYYYMMDD>/`.
- The report states exact supported flows, known gaps, and follow-up recommendations.
- The plan is updated to `complete` or `blocked` with exact residual work.

Status: not started

## Progress Log

### 2026-07-09 - Step 0

- Completed: Created the durable multimodal agent-graph product execution plan.
- Files changed: `PLAN/AGENT_GRAPH_MULTIMODAL_PRODUCT_EXECUTION_PLAN.md`
- Validation: Reviewed against the durable handoff plan skill template and aligned it with the current AstraBridge plan set.
- Blockers: None.
- Next step: Step 1, Freeze Product Slice And Acceptance Matrix.
