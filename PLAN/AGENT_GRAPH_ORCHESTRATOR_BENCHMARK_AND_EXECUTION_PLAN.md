# Agent Graph Orchestrator Benchmark And Execution Plan

## Total Objective

Turn AstraBridge Agent Graph into a user-friendly, multimodal, multi-model workflow orchestrator comparable in day-to-day operability to mainstream visual agent/workflow products, while preserving AstraBridge's stronger requirements around typed communication, bounded subagents, default context isolation, and one canonical graph contract shared by GUI and code.

This plan is a product and validation plan. It exists to close the gap between the current AstraBridge graph surface and a credible orchestrator product that users can operate mainly through the visible UI, with code-first authoring available as a first-class parallel interface rather than a separate engine.

## Related Plans And Source Anchors

- `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SCOPE_AND_UX_PRINCIPLES.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md`
- `PLAN/MULTIMODAL_ADAPTER_FAMILY_CONTRACT.md`
- `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
- `apps/astrabridge-desktop/src/styles.css`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`

## Deliverables

- A source-backed benchmark report mapping AstraBridge against common visual orchestrators and code-first agent workflow systems.
- A clarified product contract for AstraBridge graph authoring: what is GUI-first, what is code-first, what is shared, and what is intentionally deferred.
- A canvas-first UI route that allows users to add nodes, connect edges, edit contracts, inspect runs, and recover executions mainly through simulated user interaction.
- A code orchestration interface that authors the same canonical graph contract as the GUI.
- A validated subagent model with bounded parallelism, context isolation, and typed communication.
- A repeatable evidence pack and runbook so future agents can keep evolving the orchestrator without reconstructing context from chat history.

## Constraints And Attention Notes

1. Keep one canonical graph contract across GUI, code authoring, dry-run, and runtime execution.
2. Do not create a GUI-only orchestration format or a code-only runtime path.
3. Default context isolation is mandatory. Cross-agent communication must remain explicit, typed, and inspectable.
4. Main-agent orchestration should stay shallow by default. Deep nesting requires explicit justification and recorded evidence.
5. GUI acceptance requires visible product-path validation through simulated clicks, drags, hover, scroll, resize, expand, collapse, reload, and screenshot review.
6. Do not accept API-only, store-mutation, fixture-injection, or console-state shortcuts as GUI evidence when the visible UI path exists.
7. Every UI-facing step must preserve screenshots and a validation note with the exact click path and remaining friction.
8. Preserve diagnostics, screenshots, traces, manifests, reports, and sanitized raw outputs under `PRIVATE/**`.
9. Never persist secrets, keys, tokens, cookies, auth headers, or vault material in the plan, evidence, screenshots, or logs.
10. Official OpenAI direct live verification remains out of scope unless the user explicitly re-authorizes it later.
11. Provider/model capability claims must be backed by code, official docs, metadata, or preserved smoke evidence.
12. User friendliness is a hard requirement: avoid card stacking, oversized type, redundant frames, low-semantic text in the primary path, and hidden editing routes.

## Adjustment Policy

Agents may adjust substeps, filenames, evidence layout, or implementation sequencing when repository evidence requires it. Those adjustments must not weaken the total objective, relax typed communication, bypass UI validation, split the graph contract, or reduce the task into cosmetic polish only.

If new evidence shows the route is stale, revise this plan first. Record the evidence inspected, diagnosis, route change, preserved quality bar, and exact next step.

## Evidence Review And Plan Revision Policy

Before executing the next numbered step, review whether any of these triggers apply:

1. visible UI behavior contradicts the current plan assumptions;
2. source code reality differs from earlier benchmark or architecture claims;
3. a step appears complete in tests but still fails through the visible product surface;
4. the next step adds polish while a more basic authoring, execution, or inspection blocker remains unresolved;
5. a code-first path and GUI path begin to diverge in contract or behavior;
6. the benchmark set is too shallow to justify the product direction;
7. subagent isolation, typed handoff, or multimodal capability boundaries become weaker than intended.

If any trigger applies, revise the plan before continuing.

## Execution Rules

1. Each agent turn executing this plan must begin by reading this file and the related master plan files.
2. Start from the earliest numbered step whose status is not `completed`, unless the user explicitly redirects.
3. Complete exactly one numbered step per turn unless the user explicitly asks for more.
4. Update this plan before stopping.
5. A step is complete only when all of its acceptance criteria are actually satisfied.
6. UI-facing steps must use simulated user interaction in the running app and preserve screenshot evidence.
7. When layout is touched, include at least one constrained-width or panel-stressed validation pass.
8. Final handoff for each turn must name completed work, files changed, validation run, evidence path, blockers, and exact next step.

## Evidence Convention

- Default root: `PRIVATE/agent-graph-orchestrator/<step-id>/<YYYYMMDD>/`
- Benchmark steps must preserve source notes, links, screenshots where useful, and a distilled comparison artifact.
- Product/UI steps must preserve:
  - a starting screenshot,
  - screenshots after major interactions,
  - a final screenshot after reload or reopen,
  - a validation note with exact click/drag/resize path,
  - at least one constrained-width pass when layout changes.
- Runtime steps must preserve graph specs, run manifests, compiled plans, node/edge inspection evidence, and recovery artifacts.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Benchmark The Current Market And Interaction Baselines
- Next step: Step 1, Benchmark The Current Market And Interaction Baselines
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: Create this durable plan and define the first executable entry point.

Main actions:

- Define the benchmark-to-execution objective.
- Record constraints, evidence rules, adjustment policy, and executable steps.
- Identify the first concrete step.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes objective, constraints, adjustment policy, evidence policy, current progress, numbered steps, acceptance criteria, and progress log.
- Step 1 is clearly identified as the next entry point.

Status: completed

### 1. Benchmark The Current Market And Interaction Baselines

Goal: Produce a current benchmark of common visual agent/workflow orchestrators and code-first graph systems relevant to AstraBridge.

Main actions:

- Review representative systems such as ComfyUI, n8n, Dify, Langflow, Flowise, Rivet, AutoGen Studio, LangGraph Studio, and Claude Code dynamic workflows where publicly inspectable.
- Compare them across node authoring, edge semantics, subagent modeling, run inspection, recovery, code authoring, multimodal handling, and UX density.
- Produce a benchmark artifact that names where AstraBridge is already stronger, where it is weaker, and which interaction patterns are worth copying or explicitly rejecting.

Acceptance criteria:

- A benchmark report exists under the step evidence root.
- The report distinguishes product shape, runtime shape, and UX shape rather than mixing them.
- The report names at least five concrete patterns AstraBridge should adopt and five concrete patterns it should avoid.
- No product code changes occur in this step.

Status: not started

### 2. Audit AstraBridge Against The Benchmark

Goal: Turn the external benchmark into a source-backed AstraBridge gap matrix.

Main actions:

- Inspect the current desktop graph UI, sidecar contracts, runtime scheduler, typed ports, edge policies, and recovery surfaces.
- Map the current product against the benchmark dimensions from Step 1.
- Identify the exact gaps that block AstraBridge from functioning as a credible orchestrator product.

Acceptance criteria:

- A gap matrix exists under the step evidence root.
- The matrix separates proven code paths, partial paths, and missing paths.
- The matrix names the highest-leverage UI blocker, runtime blocker, and code-authoring blocker.
- No speculative claims are left without source references.

Status: not started

### 3. Lock The Product Contract For GUI And Code Authoring

Goal: Define exactly how GUI graph editing and code graph editing coexist without divergence.

Main actions:

- Specify what users can do from the GUI, what they can do from code, and what must round-trip between both.
- Define how templates, imports, exports, diffs, migrations, and code-authored graph files map into the canonical contract.
- Record non-goals and deferred paths to prevent scope drift.

Acceptance criteria:

- A contract note exists on disk under the step evidence root or in a referenced plan/design file.
- The contract explicitly forbids a second graph format or runtime path.
- GUI-only, code-only, and shared capabilities are clearly listed.
- The next implementation steps can reference this contract without ambiguity.

Status: not started

### 4. Define The Subagent Runtime And Communication Product Rules

Goal: Make AstraBridge's subagent model concrete, bounded, and user-explainable.

Main actions:

- Specify default context isolation, allowed communication channels, typed handoff modes, artifact passing rules, and shallow-graph defaults.
- Define the visible UI representation for subagents, joins, approvals, and typed communication.
- Define which subagent options are safe for regular users and which remain advanced or gated.

Acceptance criteria:

- A durable design artifact exists under the step evidence root.
- The artifact defines default-safe behavior, advanced behavior, and explicitly unsupported behavior.
- The communication rules are specific enough to guide both UI and runtime work.
- The design remains compatible with the existing canonical graph contract.

Status: not started

### 5. Design The Canvas-First Interaction Model

Goal: Define the target interaction model for the graph surface before further UI edits scatter.

Main actions:

- Specify the canvas, sidebars, inspector, toolbar, run controls, and context panels with emphasis on space priority and discoverability.
- Define which information stays always visible, which moves to hover, which moves to inspector, and which is hidden behind expand/collapse.
- Record expected user flows for adding nodes, wiring edges, editing prompts/contracts, inspecting runs, and recovering failed runs.

Acceptance criteria:

- A canvas interaction spec exists under the step evidence root.
- It includes explicit layout principles and concrete user flows.
- It names information that must leave the canvas and information that must remain on it.
- The spec is detailed enough to drive UI implementation and UI review.

Status: not started

### 6. Implement Node And Edge Visual Semantics To Match The Product Contract

Goal: Make nodes and edges compact, typed, and understandable from the default canvas view.

Main actions:

- Refine node card density, role icons, status markers, port visibility, and custom-role fallback.
- Replace verbose edge text with typed visual markers plus inspector and hover detail.
- Remove unexplained micro-icons, redundant frames, and decorative clutter.

Acceptance criteria:

- Representative node and edge states are visibly more compact and easier to scan.
- Typed semantics remain discoverable without flooding the canvas with text.
- Screenshots prove improved density and readability at normal and constrained widths.
- Focused tests cover the relevant rendering paths where practical.

Status: not started

### 7. Make The Sidebars Truly Secondary, Collapsible, And Resizable

Goal: Ensure the graph canvas remains primary while detail panels remain usable.

Main actions:

- Add or refine visible resize handles and persisted widths where appropriate.
- Reduce framing and redundant headers in the left and right panels.
- Move detailed configuration and run inspection into structured inspector sections rather than free-floating cards.

Acceptance criteria:

- Left and right graph sidebars can be resized through the visible UI.
- Collapsed state frees meaningful space rather than leaving decorative shells.
- Inspector content is structured and readable without severe overflow.
- Click-driven evidence covers resize, collapse, expand, and constrained-width behavior.

Status: not started

### 8. Complete GUI Contract Editing For Nodes And Edges

Goal: Let users edit prompts, routing, output contracts, and communication policies from the visible UI.

Main actions:

- Implement or refine node editing for prompt templates, provider/model routing, tool policy, subagent policy, output contracts, and execution options.
- Implement or refine edge editing for context policy, handoff mode, artifact inclusion, summary strategy, and typed communication details.
- Add visible validation and durable save/reload behavior.

Acceptance criteria:

- A user can edit a representative node and edge from the GUI and see the change survive reload.
- Invalid settings are blocked or warned with understandable feedback.
- Evidence preserves the exact click path and resulting saved state.
- The edits remain compatible with code import/export paths.

Status: not started

### 9. Complete The Code Authoring Interface For The Same Graph Contract

Goal: Make code orchestration a real parallel interface rather than an afterthought.

Main actions:

- Audit and finish import/export/lint/diff/migrate paths for the canonical graph files.
- Add or refine representative code-authored graph examples for common workflow shapes.
- Verify round-trip fidelity between code files and the visible GUI.

Acceptance criteria:

- Code-authored graphs can be linted, imported, exported, diffed, and reloaded without contract loss.
- Round-trip evidence exists for at least one representative workflow.
- The code interface does not bypass validation rules present in the GUI/runtime.
- Evidence is preserved under the step root.

Status: not started

### 10. Build A Credible Run Monitor And Recovery Surface

Goal: Make runtime inspection and recovery operable from the visible product surface.

Main actions:

- Expose node state, edge handoff, timing, diagnostics, artifacts, and worker outputs through compact canvas indicators plus inspector detail.
- Move run detail into a structured inspection path.
- Exercise cancellation, retry, resume, and partial rerun through visible controls.

Acceptance criteria:

- A user can inspect meaningful run state from the GUI without leaving the graph context.
- At least one cancellation path and one recovery path are validated from the visible UI.
- Evidence links GUI actions to durable backend run artifacts.
- Remaining confusion points are recorded explicitly.

Status: not started

### 11. Create A Repository-Local Agent Skill For Orchestrator Maintenance

Goal: Teach future agents how to extend and repair AstraBridge's orchestrator safely.

Main actions:

- Create or update a repository-local skill/runbook covering benchmark review, graph contract safety, UI validation, multimodal capability checks, and subagent communication discipline.
- Include explicit instructions to use simulated clicks and frequent screenshots for UI work.
- Include rules for preserving artifacts, avoiding secret leakage, and keeping GUI/code paths unified.

Acceptance criteria:

- The skill/runbook exists on disk and references the relevant plan files and code anchors.
- It is concrete enough for another agent to follow without chat history.
- It includes visible-product validation requirements rather than API-only shortcuts.
- It explicitly covers how to investigate and fix capability-adaptation regressions.

Status: not started

### 12. Run End-To-End Fixture Dogfood And Final Benchmark Recheck

Goal: Prove that the integrated orchestrator path works coherently and measure the remaining gap against the benchmark.

Main actions:

- Start from the visible product surface, create or load a representative graph, run it in fixture mode, inspect outputs, and exercise recovery.
- Re-evaluate AstraBridge against the Step 1 benchmark using the now-updated product.
- Write a final report summarizing what is now proven, what remains weak, and the next recommended slice.

Acceptance criteria:

- Evidence connects GUI actions, runtime artifacts, and benchmark conclusions in one coherent package.
- The report clearly states which orchestrator capabilities are now product-grade, partial, or still missing.
- Remaining gaps are prioritized by user impact and implementation leverage.
- The plan can hand off cleanly to a next implementation or release plan.

Status: not started

## Progress Log

### 2026-07-09 - Step 0

- Completed: Created the durable benchmark and execution plan for AstraBridge Agent Graph orchestrator work.
- Files changed: `PLAN/AGENT_GRAPH_ORCHESTRATOR_BENCHMARK_AND_EXECUTION_PLAN.md`
- Validation: Checked the plan structure against the durable handoff plan skill and aligned it with the existing master and subordinate Agent Graph plans.
- Blockers: None.
- Next step: Step 1, Benchmark The Current Market And Interaction Baselines.
