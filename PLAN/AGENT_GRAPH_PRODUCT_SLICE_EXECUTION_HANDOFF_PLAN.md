# Agent Graph Product Slice Execution Handoff Plan

## Total Objective

Deliver the first product-grade AstraBridge Agent Graph slice that is genuinely usable by normal users: a ComfyUI-like visual workflow builder for arbitrary multimodal, multi-model tasks, backed by one canonical graph contract, one real runtime path, bounded parallel subagents, default context isolation, typed communication, and click-verified operator UX in the running app.

This plan is narrower than the full long-range productization roadmap. It focuses on the first release slice that must feel coherent as a product, not merely exist as backend/runtime pieces plus an awkward editor.

## Deliverables

- A source-backed gap baseline for the first product slice, tied to concrete repository files and current runtime/UI behavior.
- A unified execution path proving that GUI-authored graphs and code-authored graphs compile into the same canonical graph contract and runtime.
- A bounded parallel subagent workflow with typed handoff, join behavior, and durable run evidence.
- A usable visual builder where users can add nodes, wire edges, edit prompts/contracts, run workflows, inspect outputs, and recover from failures through visible controls.
- A code orchestration interface that can create, lint, diff, import, export, and execute the same graph used by the GUI.
- A maintainer/operator runbook plus an agent-facing skill or runbook for future graph repair and capability-adaptation work.
- Preserved screenshots, click traces, compiled plans, run manifests, validation notes, and reports under `PRIVATE/agent-graph-product-slice/**`.

## Related Context Files

- `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `PLAN/AGENT_GRAPH_VISUAL_ORCHESTRATOR_EXECUTION_HANDOFF_PLAN.md`
- `PLAN/AGENT_GRAPH_MULTIMODAL_PRODUCT_EXECUTION_PLAN.md`
- `PLAN/MULTIMODAL_ADAPTER_FAMILY_CONTRACT.md`
- `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
- `apps/astrabridge-desktop/src/api.ts`
- `apps/astrabridge-desktop/src/styles.css`

## Constraints And Attention Notes

1. `Project -> Task` remains the product boundary. Graph runs, worker lanes, provider threads, subagents, and artifacts stay task-scoped unless explicitly surfaced as bounded graph state.
2. GUI graphs and code-authored graphs must share one canonical contract and one runtime. No second editor-only or code-only execution engine is allowed.
3. Default context isolation is mandatory. Full parent chat history, provider-private reasoning, raw scratchpads, secrets, and unrelated worker outputs must not cross edges implicitly.
4. Every edge must declare a typed handoff or context policy. Critical communication must be machine-checkable.
5. The first release slice must be operable from the visible product surface. Simulated clicking, dragging, typing, resizing, hovering, expanding, collapsing, and screenshot review are required acceptance evidence whenever a visible path exists.
6. UI work is not accepted through API-only proof, hidden state mutation, fixture preloading, console injection, or store mutation when a user-facing path exists.
7. The canvas is the primary surface. Avoid card stacking, oversized fonts, redundant metadata, decorative frames, unclear icons, wasted empty rails, and inspector-first layouts.
8. Both task-graph sidebars in the graph view should be user-resizable, and collapsed states must actually return meaningful canvas space.
9. Common agent roles and edge semantics should prefer icons plus tooltip disclosure over persistent verbose text.
10. Product work should bias toward shallow orchestration. One planner/supervisor layer with bounded parallel workers plus synthesizer/reviewer is normal. Deeper nesting requires explicit justification and evidence.
11. Multimodal routing must be capability-aware. A provider/model cannot be offered for a modality unless docs-backed or smoke-backed evidence supports it.
12. Preserve diagnostics, screenshots, traces, compiled plans, run manifests, reports, and sanitized raw outputs under `PRIVATE/**`. Never persist secrets.
13. Do not rely on official OpenAI account login as a product path. API-key providers remain the normal path.
14. The product slice is not complete until one code-authored graph and one GUI-authored graph round-trip through the same contract and runtime with preserved evidence.

## Adjustment Policy

Agents may adjust filenames, sequence, substeps, implementation details, and validation commands when repository evidence requires it. Such changes must not weaken the total objective, remove click-driven validation, lower the context-isolation bar, split code and GUI execution into separate engines, or replace substantive runtime/product work with cosmetic polishing.

If evidence shows the route is stale, revise the plan before continuing. Record the evidence, diagnosis, route change, what must not be weakened, and the exact next step.

## Evidence Review And Plan Revision Policy

Before each execution turn, review whether the current route is stale. Trigger a plan revision when any of these occur:

1. runtime evidence contradicts the assumed scheduler or handoff behavior;
2. GUI screenshots show serious usability debt that blocks normal use;
3. a completed step only proves fixture behavior while the visible product path remains broken;
4. multimodal/provider capability evidence invalidates a planned node or port route;
5. the next step would polish visuals while the real blocker is still canonical contract, runtime, context isolation, or operator flow;
6. code and GUI start drifting into parallel incompatible formats or run paths;
7. a completed step's acceptance criteria are too weak to support the release slice.

Every revision must record:

- evidence inspected;
- diagnosis;
- route change;
- what must not be weakened;
- exact next step.

## Execution Rules

1. Each execution turn must begin by reading this plan and checking the revision triggers.
2. Complete exactly one numbered step per turn unless the user explicitly asks for more.
3. Update this plan before stopping.
4. A step is `completed` only when all acceptance criteria are met.
5. UI-facing steps require preserved screenshots and a validation note describing the exact click/drag/type path.
6. Runtime-facing steps require deterministic tests plus preserved run artifacts.
7. When a visible path exists, the agent must prefer simulated clicking over direct API shortcuts.
8. Every handoff must state files changed, validation run, evidence path, blockers, and exact next step.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Product Slice Baseline And Gap Restatement
- Next step: Step 1, Product Slice Baseline And Gap Restatement
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: Create this durable execution handoff plan and make the first entry point unambiguous.

Main actions:

- Define the first-release product slice clearly.
- Record constraints, evidence rules, execution rules, sequenced steps, and acceptance criteria.
- Set the initial current progress.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes objective, deliverables, constraints, adjustment policy, evidence review policy, current progress, execution steps, acceptance criteria, and progress log.
- Step 1 is clearly identified as the next step.

Status: completed

### 1. Product Slice Baseline And Gap Restatement

Goal: Produce a current-state baseline for the exact first release slice instead of the broader long-range roadmap.

Main actions:

- Re-read the current runtime, contract, multimodal, and task-graph UI surfaces.
- Compare current repository state against the product slice target: usable canvas, shared contract, shared runtime, bounded parallel subagents, typed handoff, multimodal capability gating, and code-first orchestration.
- Write a gap report that separates already-proved paths from still-missing product paths.

Acceptance criteria:

- A baseline report exists under `PRIVATE/agent-graph-product-slice/step1-baseline/<YYYYMMDD>/`.
- The report cites exact files and explicitly distinguishes backend-proved, fixture-only, UI-only, blocked, and missing paths.
- The report names the highest-leverage runtime blocker and the highest-leverage UX blocker.

Status: not started

### 2. Canonical Contract Freeze For The Product Slice

Goal: Freeze the minimal canonical graph contract needed for the release slice.

Main actions:

- Audit node, edge, port, context-policy, output-schema, multimodal, and subagent fields in the canonical contract.
- Remove ambiguity between GUI metadata and runtime metadata.
- Add or tighten validation for fields the GUI and code interface must both preserve.

Acceptance criteria:

- The canonical contract explicitly covers node roles, typed ports, edge bindings, context policies, output contracts, multimodal artifact types, routing metadata, and subagent policy.
- Tests reject missing edge policy, invalid modality claims, and invalid code/GUI round-trip state.
- There is one documented canonical graph shape for both GUI and code paths.

Status: not started

### 3. Code-Orchestration Interface Unification

Goal: Give agents and advanced users a code-first way to create and control the same graphs used by the GUI.

Main actions:

- Harden import, export, lint, diff, migrate, and dry-run for the canonical graph spec.
- Add or improve examples for planner-worker-synthesizer, fan-out research, code-fix-review, multimodal adapter, and blank graph.
- Ensure graph files can round-trip through GUI edit and runtime execution without contract loss.

Acceptance criteria:

- One code-authored graph can be linted, dry-run, imported into the GUI, edited, exported, and re-run without losing required fields.
- Examples cover at least one bounded parallel subagent graph and one multimodal graph.
- Validation artifacts are preserved under `PRIVATE/agent-graph-product-slice/step3-code-interface/<YYYYMMDD>/`.

Status: not started

### 4. Parallel Runtime And Join Rule Closure

Goal: Close the runtime gap for bounded fan-out, join rules, and durable execution evidence.

Main actions:

- Finish or verify parallel ready-node scheduling.
- Tighten join behavior for all-required, any-success, quorum, and manual/approval-gated joins where the spec supports them.
- Preserve compiled plans, run manifests, event traces, and timing evidence.

Acceptance criteria:

- Deterministic tests prove at least two worker nodes can run in parallel and join correctly.
- Failed, blocked, and partial branch cases have explicit downstream behavior.
- Evidence exists under `PRIVATE/agent-graph-product-slice/step4-parallel-runtime/<YYYYMMDD>/` with compiled plan, manifest, and timing summary.

Status: not started

### 5. Recovery And Operator Safety

Goal: Make graph runs cancellable, retryable, resumable, and safe to operate.

Main actions:

- Add or finish cancellation, retry, resume, rerun-selected-node, and partial execution semantics.
- Persist recovery traces and version new artifacts instead of silently overwriting them.
- Surface enough run-state information for the GUI to explain operator actions.

Acceptance criteria:

- Tests cover cancel active run, retry failed node, resume interrupted run, and rerun selected node.
- Recovery artifacts are preserved under `PRIVATE/agent-graph-product-slice/step5-recovery/<YYYYMMDD>/`.
- The runtime and UI surface enough state for an operator to understand what will happen next.

Status: not started

### 6. Multimodal Port And Capability Gate

Goal: Make multimodal routing product-grade rather than ad hoc.

Main actions:

- Freeze the release-slice port types: text, image, audio, document, structured JSON, tool result, code diff, and agent report.
- Connect provider/model selection to docs-backed or smoke-backed capability evidence.
- Block unsupported modality/provider combinations in both code and GUI paths.

Acceptance criteria:

- Invalid modality/provider routes are rejected or clearly blocked.
- At least one mixed-modality graph is preserved as evidence.
- The GUI shows modality type using icons/tooltips rather than large persistent explanatory text.

Status: not started

### 7. Canvas-First Layout Refactor

Goal: Turn the current graph surface into a usable canvas-first product workspace.

Main actions:

- Remove unnecessary wrapper cards, redundant headers, decorative frames, and wasted rails.
- Make graph-view sidebars resizable and collapsible, with collapsed state returning meaningful canvas space.
- Move low-semantic details into tooltip, inspector, or collapsible sections instead of persistent canvas clutter.

Acceptance criteria:

- Screenshots show materially more usable canvas area than the current surface.
- Both graph-view sidebars can be resized by the user.
- The canvas no longer depends on stacked cards for basic information display.

Status: not started

### 8. Node And Edge Visual Language

Goal: Make nodes and edges readable through iconography and hierarchy rather than verbose text blocks.

Main actions:

- Add icon mapping for common agent roles such as planner, worker, synthesizer, validator, reviewer, tool, approval gate, and output.
- Add edge semantics iconography for context handoff, artifact handoff, review flow, approval, and multimodal transfer.
- Reduce node chrome, tighten typography, and remove unclear or low-value symbols.

Acceptance criteria:

- Nodes use consistent iconography with tooltip disclosure.
- Edges can communicate their semantics without long inline labels.
- Screenshots show improved text hierarchy, smaller type, and less visual noise.

Status: not started

### 9. Inspector Refactor

Goal: Make the inspector compact, structured, and useful instead of a cramped form dump.

Main actions:

- Move secondary run details and expanded configuration into grouped collapsible sections.
- Refactor field ordering around what users do most often: prompt, model/provider, output, edge policy, safety, advanced fields.
- Clean overflow, spacing, and checkbox/list layout issues.

Acceptance criteria:

- The inspector fits the common edit flow without excessive scrolling at standard desktop width.
- Secondary settings are hidden by default but discoverable.
- Click-driven screenshots confirm the inspector is usable for both node and edge editing.

Status: not started

### 10. GUI Authoring Flow Closure

Goal: Make visible graph authoring work end-to-end without API shortcuts.

Main actions:

- Verify users can add nodes, connect edges, edit prompts/contracts, set model/provider choices, and save the graph from the GUI.
- Use simulated clicking, dragging, typing, resizing, hovering, and collapsing during validation.
- Record screenshots after each major interaction.

Acceptance criteria:

- A new graph can be created and configured from the visible UI.
- Validation artifacts include a click-path note and ordered screenshots.
- No hidden API or store shortcut is required to complete the authoring flow.

Status: not started

### 11. GUI Run Monitor And Output Inspection

Goal: Make graph execution understandable from the visible product surface.

Main actions:

- Surface run states on the canvas and in the inspector.
- Let users inspect node outputs, edge handoffs, artifacts, timing, and diagnostics without drowning the canvas in raw text.
- Validate the flow by real clicking during a run.

Acceptance criteria:

- A user can inspect at least one node output and one edge handoff from visible controls.
- Screenshots prove the run monitor works during an actual execution path.
- The canvas remains primary while detail views stay discoverable.

Status: not started

### 12. Code And GUI Round-Trip Dogfood

Goal: Prove the shared-contract story with real product evidence.

Main actions:

- Create one graph from code and one graph from the GUI.
- Round-trip both through import/export/edit/execute paths.
- Compare produced graph specs, compiled plans, manifests, and visible behavior.

Acceptance criteria:

- One code-authored and one GUI-authored graph both execute through the same runtime path.
- Required contract fields survive round-trip.
- Evidence pack preserves graph files, compiled plans, manifests, and screenshots.

Status: not started

### 13. Agent Repair Skill And Runbook

Goal: Teach future agents how to maintain and repair capability-adaptation and workflow issues safely.

Main actions:

- Create or update a skill/runbook for diagnosing graph/runtime/multimodal/provider compatibility regressions.
- Include rules for docs-backed verification, smoke evidence, UI click validation, rollback, and artifact preservation.
- Include a bounded workflow for repairing capability mismatches without broad uncontrolled edits.

Acceptance criteria:

- A durable skill or runbook exists on disk and references the canonical graph contract and evidence conventions.
- It requires screenshot-backed GUI validation where a visible path exists.
- It describes rollback and safety boundaries explicitly.

Status: not started

### 14. Product Slice Final Gate

Goal: Close the first release slice with evidence strong enough for handoff and continued iteration.

Main actions:

- Run backend tests, runtime dogfood, GUI click dogfood, and a focused secret-safety review over changed files and evidence.
- Write a release-style report that states what is supported, what is blocked, and what remains next.
- Record the remaining delta versus the broader long-range productization plan.

Acceptance criteria:

- A final report exists under `PRIVATE/agent-graph-product-slice/final/<YYYYMMDD>/`.
- The report lists supported behaviors, blocked behaviors, and next recommended slice.
- The plan current progress is updated to `Complete` or `Blocked` with exact residual work.

Status: not started

## Progress Log

### 2026-07-09 - Step 0

- Completed: Created a durable execution handoff plan for the first product-grade Agent Graph slice, focused on shared contract/runtime, bounded parallel subagents, multimodal capability gating, code orchestration, and click-verified GUI usability.
- Files changed: `PLAN/AGENT_GRAPH_PRODUCT_SLICE_EXECUTION_HANDOFF_PLAN.md`
- Validation: Checked the plan against the durable handoff plan skill template and aligned it with current AstraBridge repository priorities.
- Blockers: None.
- Next step: Step 1, Product Slice Baseline And Gap Restatement.
