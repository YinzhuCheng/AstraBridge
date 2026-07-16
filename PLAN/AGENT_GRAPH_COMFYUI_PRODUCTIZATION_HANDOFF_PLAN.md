# Agent Graph ComfyUI-Style Productization Handoff Plan

## Total Objective

Turn AstraBridge Agent Graph into a canvas-first workflow product for arbitrary tasks, not just image or video generation. The target shape is a ComfyUI-like visual builder plus a Claude-Code-style dynamic workflow runtime:

- users can add agents, tools, artifacts, gates, transforms, and outputs from the GUI;
- users can wire typed connections, edit prompt templates, output contracts, communication formats, and context policy;
- the runtime supports bounded parallel subagents, default context isolation, structured handoff, recovery, and durable evidence;
- the GUI path and code-authored path share one canonical graph contract and one runtime.

This plan is the concrete handoff route for that productization slice. It must stay compatible with the broader roadmap in [AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md](D:/AstraBridge/PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md), but it is intentionally narrower and more executable.

## Deliverables

- A source-backed baseline for the ComfyUI-style product slice, tied to current UI, runtime, and contract evidence.
- A locked release-slice graph contract shared by GUI authoring, code authoring, dry-run, and runtime execution.
- A canvas-first GUI builder with usable node creation, typed wiring, contract editing, run inspection, and recovery controls.
- A code-first orchestration interface that can create, lint, diff, import, export, migrate, and execute the same graph contract.
- A bounded subagent runtime with typed handoff, default context isolation, approval boundaries, and durable run artifacts.
- A multimodal and provider-aware capability surface that blocks unsupported modality or model combinations.
- A maintainer skill or runbook for future agent-led repair, adaptation, and extension work.
- Preserved click-driven screenshots, traces, compiled plans, run manifests, reports, and validation notes under `PRIVATE/agent-graph-comfyui-productization/**`.

## Related Context Files

- [AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md](D:/AstraBridge/PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md)
- [AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md](D:/AstraBridge/PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md)
- [AGENT_GRAPH_GUI_RUNTIME_EXECUTION_CHECKLIST.md](D:/AstraBridge/PLAN/AGENT_GRAPH_GUI_RUNTIME_EXECUTION_CHECKLIST.md)
- [AGENT_GRAPH_PRODUCT_SLICE_EXECUTION_HANDOFF_PLAN.md](D:/AstraBridge/PLAN/AGENT_GRAPH_PRODUCT_SLICE_EXECUTION_HANDOFF_PLAN.md)
- [AGENT_GRAPH_MULTIMODAL_PRODUCT_EXECUTION_PLAN.md](D:/AstraBridge/PLAN/AGENT_GRAPH_MULTIMODAL_PRODUCT_EXECUTION_PLAN.md)
- [AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md](D:/AstraBridge/PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md)
- [AGENT_GRAPH_VISUAL_ORCHESTRATOR_EXECUTION_HANDOFF_PLAN.md](D:/AstraBridge/PLAN/AGENT_GRAPH_VISUAL_ORCHESTRATOR_EXECUTION_HANDOFF_PLAN.md)
- [AGENT_ORCHESTRATION_GRAPH_CONTRACT.md](D:/AstraBridge/PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md)
- [apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx](D:/AstraBridge/apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx)
- [apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx](D:/AstraBridge/apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx)
- [apps/astrabridge-desktop/src/types.ts](D:/AstraBridge/apps/astrabridge-desktop/src/types.ts)
- [apps/astrabridge-desktop/src/api.ts](D:/AstraBridge/apps/astrabridge-desktop/src/api.ts)
- [apps/astrabridge-desktop/src/styles.css](D:/AstraBridge/apps/astrabridge-desktop/src/styles.css)
- [apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py](D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py)
- [apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py](D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py)

## Repository-Proved Baseline

Use this section to avoid redoing work that the repository already proves. The plan starts from a stronger baseline than a greenfield productization effort.

- Master dynamic-workflow work has already closed the foundational runtime and contract slices through Step 10 in [AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md](D:/AstraBridge/PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md), including canonical graph spec work, code-first interface work, compiler work, scheduler MVP, typed handoff bus, bounded subagent runtime, parallel fan-out and join semantics, recovery semantics, and multimodal capability integration.
- The GUI/runtime subordinate execution path has already closed the early canvas and editing slices through Step 8 in [AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md](D:/AstraBridge/PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md), including node-library entry, node-card compaction, edge glyphs, inspector separation, typed-port discoverability, contract editing, and a real run-monitor path.
- The current open repository-level runtime gap is the visible recovery interaction closure in subordinate Step 9. Future agents must read the latest progress entries before deciding whether that gap is still product code, browser-control, or evidence-only.
- This ComfyUI-style plan therefore should not restart from "does any graph runtime exist?" or "is there any canvas at all?". It should instead audit the current proved substrate, then drive the remaining product gap to a coherent canvas-first, code-and-GUI unified workflow product.

## Current Gap Snapshot

Use this snapshot to keep later execution grounded in current repository evidence instead of broad ambition.

- `proved in repository`:
  - canonical graph contract, compiler, scheduler MVP, typed context and artifact bus, bounded subagent runtime, parallel fan-out and join semantics, recovery substrate, and multimodal capability substrate are already landed in the master dynamic-workflow plan family;
  - the GUI path already has a usable canvas shell, template or node entry, compacted node cards, typed edge and port discoverability, contract editing, run monitoring, visible cancel or resume flow, and visible end-to-end fixture dogfood evidence.
- `partial and still risky`:
  - GUI and code round-trip as one operator-grade product story is not yet closed end to end;
  - human-approval boundary behavior is not yet dogfooded from the visible UI in the current execution family;
  - multimodal and provider gating is partly runtime-backed but not yet fully shaped into compact, user-friendly authoring affordances;
  - operator usability is improved but still at risk from canvas crowding, inspector sprawl, unclear iconography, and evidence gaps after reopen or reload.
- `missing or not yet accepted`:
  - one clean release-slice definition covering which node classes, edge classes, modality types, and operator flows are officially in scope;
  - one code-authored graph and one GUI-authored graph round-tripping through the same graph contract and runtime with preserved evidence;
  - one credible regression and smoke gate that catches contract drift, runtime drift, and visible UI drift together.
- `out of scope unless the user reauthorizes later`:
  - official OpenAI direct live verification;
  - unlimited-depth agent nesting or uncontrolled auto-orchestration;
  - product claims that depend on hidden API mutation instead of visible interaction.

## Execution Entry Rule

This file is the preferred handoff entry point for the "ComfyUI-like general agent workflow product" objective. Future agents should:

1. read this file first;
2. read the latest progress entries in the master dynamic-workflow plan and GUI runtime subordinate plan;
3. start from the earliest non-completed step here;
4. avoid creating a parallel handoff plan for the same product slice unless this plan is explicitly retired or replaced by user instruction.

## Constraints And Attention Notes

1. Keep one canonical graph contract. GUI graphs, code-authored graphs, dry-run, and runtime execution must not diverge into separate formats or engines.
2. `Project -> Task` remains the product boundary. Graph runs, worker lanes, artifacts, and subagents stay task-scoped unless a later approved feature expands that boundary.
3. Default context isolation is mandatory. Full parent history, provider-private reasoning, raw scratchpads, secrets, and unrelated worker outputs must not cross edges implicitly.
4. Every edge must declare a handoff or context policy that is machine-checkable.
5. GUI claims require visible product-path validation. Use simulated clicking, dragging, typing, hovering, collapsing, expanding, scrolling, resizing, and reopening in the in-app browser whenever a visible path exists.
6. API-only proof, hidden store mutation, console injection, fixture preloading, or debug-only shortcuts do not count as GUI acceptance.
7. The canvas is the primary surface. Avoid card stacking, oversized type, redundant metadata, decorative frames, inspector sprawl, and low-semantic text occupying the main workspace.
8. Task-graph sidebars should be collapsible and user-resizable. Collapsed state must return meaningful canvas space.
9. Prefer icon-led semantics with tooltip disclosure for common node roles and edge meanings. Persist text only where it carries essential meaning.
10. Main-agent orchestration should stay shallow by default: one planner or supervisor layer, bounded workers, and synthesizer or reviewer. Deeper nesting requires explicit justification and evidence.
11. Multimodal and provider-aware routing must be capability-backed. Unsupported modality or model combinations should be blocked during authoring or dry-run.
12. Preserve diagnostics, screenshots, click traces, compiled plans, run manifests, reports, and sanitized outputs under `PRIVATE/**`. Do not clean them unless the user explicitly names targets.
13. Never persist API keys, tokens, cookies, auth headers, vault secrets, or other secret-bearing material in plans, logs, screenshots, or artifacts.
14. Product acceptance is not complete until one GUI-authored graph and one code-authored graph round-trip through the same contract and runtime with preserved evidence.

## Adjustment Policy

Agents may adjust filenames, substeps, component boundaries, validation commands, implementation order, and evidence layout when repository evidence requires it. Such adjustments must not weaken the total objective, reduce the validation bar to API-only proof, remove typed communication, bypass context isolation, or split GUI and code execution into incompatible paths.

If the current route becomes stale, revise this plan before continuing. Record the evidence inspected, diagnosis, route change, what must not be weakened, and the exact next step.

## Evidence Review And Plan Revision Policy

Before executing the next step, check whether any of these revision triggers apply:

1. current runtime or UI evidence contradicts the assumed route;
2. a completed step proves only fixtures or tests while the visible product path is still weak;
3. screenshots show canvas-first usability is still materially blocked;
4. multimodal or provider capability evidence invalidates a planned node, port, or routing surface;
5. the next step adds polish while a higher-leverage contract, runtime, or operator-flow blocker remains;
6. GUI and code paths begin drifting into different graph shapes or different runtime semantics;
7. a completed step's acceptance criteria are too weak to support the product objective.

When a trigger applies, revise the plan first. Allowed revisions include splitting a step, adding a diagnostic step, reordering future work, or replacing a weak acceptance route with stronger click-driven evidence.

## Execution Rules

1. Each execution turn must begin by reading this file and the related master plan.
2. Start from the earliest numbered step whose status is not `completed`, unless the user explicitly redirects.
3. Complete exactly one numbered step per turn unless the user explicitly asks for more.
4. Update this plan before stopping.
5. A step can be marked `completed` only when all acceptance criteria are actually satisfied.
6. UI-facing steps must use the visible product surface in the in-app browser and preserve screenshot-backed validation notes.
7. Runtime-facing steps must include deterministic tests and preserved run artifacts.
8. When layout is touched, include at least one constrained-width or sidebar-stressed validation pass.
9. Final handoff for each step must name completed work, files changed, validation, evidence path, blockers, and exact next step.

## Simulated Interaction Gate

Any GUI-related execution step must:

1. open the real AstraBridge app in the in-app browser;
2. enter the target surface through visible controls where possible;
3. operate the product through simulated clicking, dragging, typing, hovering, scrolling, expanding, collapsing, and resizing instead of relying on direct API shortcuts;
4. capture screenshots frequently enough to catch obvious UI regressions early;
5. treat card stacking, oversized fonts, fixed sidebars wasting space, meaningless icons, redundant metadata, detached controls, and inspector or canvas crowding as product defects, not deferrable polish;
6. re-validate persisted behavior after reload or reopen when the step changes durable state.

## Acceptance Package Contract

Every numbered step in this plan must leave behind a reviewable acceptance package under:

- `PRIVATE/agent-graph-comfyui-productization/step<step-number>-<short-name>/<YYYYMMDD>/`

Unless the step is explicitly source-audit-only, the acceptance package must include:

1. `step-report.md`
   - what was changed;
   - exact files touched;
   - why this step is now complete;
   - known remaining friction that does not block acceptance.
2. `validation-note.md`
   - exact visible click path or code-path used for validation;
   - reload or reopen path when durable state changed;
   - constrained-width or stressed-layout observations when UI changed.
3. durable artifacts relevant to the step:
   - screenshots,
   - action traces,
   - capture reports,
   - graph specs,
   - compiled plans,
   - run manifests,
   - test output summaries,
   - or schema/contract fixtures.
4. a short `commands.txt` or equivalent command record whenever shell validation, tests, or capture scripts are used.

If a step touches the visible product surface, the package is incomplete unless it contains:

- one starting-state screenshot;
- one post-interaction screenshot;
- one final screenshot after reload, reopen, or rerender when relevant;
- at least one screenshot or report from a constrained-width or sidebar-stressed pass when layout was touched.

If a step is blocked, the same evidence root must contain the failed click path, the blocking screenshot or report, the blocker diagnosis, and the exact next entry point.

## Mandatory Validation Baseline

Unless a step is documentation-only or source-audit-only, agents should run the smallest relevant baseline and preserve the result in the step package:

- focused tests for touched runtime or UI surfaces;
- `tsc --noEmit` for desktop TypeScript changes;
- the real in-app browser path for GUI-visible changes;
- headless page-capture fallback when native browser screenshot capture is flaky;
- a file-level diff review against the current objective before ending the turn.

Agents may narrow the test scope when the touched surface is well-bounded, but they must record the exact commands and explain any omitted validation.

## Release-Slice Acceptance Matrix

The product slice governed by this plan is not accepted until all of the following are proved with durable evidence:

1. Graph authoring:
   - create or instantiate a representative graph through the visible GUI;
   - edit representative nodes and edges;
   - save, reload, and reopen without losing contract state.
2. Shared contract:
   - one code-authored graph and one GUI-authored graph round-trip through the same canonical graph shape;
   - required node, edge, port, and policy fields survive import and export.
3. Runtime execution:
   - the generic scheduler executes a representative bounded workflow;
   - node and edge run detail are inspectable from the visible product surface.
4. Recovery:
   - at least one cancel path and one recovery path are exercised through visible controls;
   - rerun-versus-reuse semantics are understandable to an operator.
5. Subagent discipline:
   - bounded parallel workers are supported;
   - default context isolation and explicit handoff policy remain enforced.
6. Multimodal and provider gating:
   - unsupported model/modality combinations are blocked or clearly warned;
   - at least one mixed-modality route is preserved as evidence.
7. Operator usability:
   - canvas remains visually primary;
   - sidebars are collapsible and resizable where applicable;
   - low-semantic text and redundant card framing do not dominate the graph workspace.

Future agents must not mark this plan complete by averaging confidence across these areas. Each area needs direct evidence.

## Reviewer Acceptance Checklist

Use this checklist when another agent claims that a numbered step or the whole plan is complete.

1. Did the agent preserve a step package under `PRIVATE/agent-graph-comfyui-productization/**` with `step-report.md`, `validation-note.md`, relevant artifacts, and command records when commands were used?
2. If the step touched the GUI, did the agent validate through the real in-app browser with simulated clicking, dragging, typing, hovering, scrolling, collapsing, expanding, resizing, reload, or reopen instead of relying on API shortcuts?
3. Do the screenshots show that the canvas remains primary, without new card stacking, oversized text, redundant metadata, or detached controls?
4. If the step touched runtime behavior, are there focused deterministic tests or preserved run artifacts proving the change?
5. If the step touched graph contract behavior, do code and GUI paths still point at one canonical graph shape rather than drifting into parallel formats?
6. If the step touched multimodal or provider gating, is the behavior backed by source-backed capability evidence or preserved smoke evidence rather than assumption?
7. Did the agent record remaining friction explicitly instead of presenting a partial path as full product acceptance?
8. Is the next step unambiguous for the next agent?

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Baseline Gap Audit And Product Slice Lock
- Next step: Step 1, Baseline Gap Audit And Product Slice Lock
- Execution mode: inherit already-proved master and subordinate evidence first; do not replay already-accepted substrate work unless a new plan-review note says the inherited proof is stale
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: Create this durable handoff plan and make the first executable entry point clear.

Main actions:

- Define the ComfyUI-style product objective in executable terms.
- Record constraints, revision rules, validation rules, and step sequencing.
- Align the plan with existing repository plan families without creating a duplicate product objective.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes objective, deliverables, constraints, adjustment policy, evidence review policy, current progress, numbered steps, acceptance criteria, and progress log.
- The next step is unambiguous.

Status: completed

### 1. Baseline Gap Audit And Product Slice Lock

Goal: Produce a source-backed restatement of the exact first product slice and the current gap to reach it.

Main actions:

- Read the latest progress entries in the master dynamic-workflow plan and GUI runtime subordinate plan before auditing source code or UI state.
- Inspect the current canvas, inspector, graph authoring path, runtime path, code orchestration path, subagent path, and multimodal/provider capability surfaces.
- Classify each surface as `proved`, `partial`, `blocked`, or `missing`.
- Separate "already proved in repository", "proved only in fixture or test space", "proved only in visible GUI", and "still missing from both".
- Lock the first product slice: which node types, edge types, modality types, recovery actions, and operator flows are in scope for the release slice.
- Save the baseline report under `PRIVATE/agent-graph-comfyui-productization/step1-baseline/<YYYYMMDD>/`.

Acceptance criteria:

- A baseline report exists on disk.
- The report cites exact files and real UI observations.
- The report names the highest-leverage runtime blocker, GUI blocker, and contract blocker.
- The report explicitly says which already-landed master/subordinate steps are being inherited rather than re-executed.
- The release-slice scope is explicit enough that later agents do not need to re-derive it.

Status: not started

### 2. Canonical Graph Contract Lock

Goal: Freeze the release-slice graph contract shared by GUI, code orchestration, dry-run, and runtime.

Main actions:

- Audit node, edge, port, context-policy, output-schema, multimodal, and subagent fields in the canonical graph shape.
- Remove ambiguity between GUI metadata and runtime metadata.
- Tighten validation for fields that must survive code and GUI round-trip.

Acceptance criteria:

- The release-slice contract explicitly covers node roles, typed ports, edge bindings, context policies, output contracts, multimodal artifact types, routing metadata, and subagent policy.
- Tests or fixtures reject missing edge policy, invalid modality claims, and invalid round-trip state.
- There is one documented canonical graph shape for both GUI and code paths.

Status: not started

### 3. Code-Orchestration Interface Unification

Goal: Provide a code-first interface that authors and runs the same graph used by the GUI.

Main actions:

- Harden import, export, lint, diff, migrate, and dry-run for the canonical graph spec.
- Add or refresh examples for planner-worker-synthesizer, research fan-out, code-fix-review, multimodal adapter, and blank graph.
- Preserve round-trip evidence under `PRIVATE/agent-graph-comfyui-productization/step3-code-interface/<YYYYMMDD>/`.

Acceptance criteria:

- One code-authored graph can be linted, dry-run, imported into the GUI, edited, exported, and re-run without contract loss.
- Example graphs cover at least one bounded parallel subagent flow and one multimodal flow.
- The code path does not introduce a second runtime or a second graph format.

Status: not started

### 4. Parallel Runtime And Join Rule Closure

Goal: Close the runtime gap for bounded fan-out, join rules, and durable execution evidence.

Main actions:

- Verify or finish parallel ready-node scheduling.
- Tighten join behavior for all-required, any-success, quorum, and manual or approval-gated joins where supported.
- Preserve compiled plans, run manifests, event traces, and timing evidence.

Acceptance criteria:

- Deterministic tests prove at least two workers can run in parallel and join correctly.
- Failed, blocked, and partial branch cases have explicit downstream behavior.
- Evidence exists under `PRIVATE/agent-graph-comfyui-productization/step4-parallel-runtime/<YYYYMMDD>/`.

Status: not started

### 5. Recovery And Operator Safety

Goal: Make graph runs cancellable, retryable, resumable, and safe to operate from both runtime and GUI perspectives.

Main actions:

- Add or finish cancellation, retry, resume, rerun-selected-node, and partial execution semantics.
- Persist recovery traces and versioned artifacts instead of silently overwriting state.
- Surface enough run-state metadata for operators to understand what will rerun and what will be reused.

Acceptance criteria:

- Tests cover cancel active run, retry failed node, resume interrupted run, and rerun selected node.
- Recovery artifacts are preserved under `PRIVATE/agent-graph-comfyui-productization/step5-recovery/<YYYYMMDD>/`.
- The operator-facing state model is explicit enough for GUI recovery work.

Status: not started

### 6. Multimodal And Provider-Aware Capability Surface

Goal: Make multimodal routing and provider gating product-grade instead of ad hoc.

Main actions:

- Freeze the release-slice port types: text, image, audio, document, structured JSON, tool result, code diff, and agent report.
- Connect provider and model selection to docs-backed or smoke-backed capability evidence.
- Block unsupported modality and provider combinations in both code and GUI paths.

Acceptance criteria:

- Invalid modality or provider routes are rejected or clearly blocked.
- At least one mixed-modality graph is preserved as evidence.
- The GUI shows modality type using compact iconography or tooltip disclosure, not large persistent explanatory text.

Status: not started

### 7. Canvas-First Layout Refactor

Goal: Turn the graph surface into a usable canvas-first product workspace.

Main actions:

- Remove unnecessary wrapper cards, redundant headers, decorative frames, and wasted rails.
- Keep graph-view sidebars resizable and collapsible, with collapsed state returning meaningful canvas space.
- Move low-semantic details into tooltip, inspector, or collapsible sections.

Acceptance criteria:

- Screenshots show materially more usable canvas area than the current surface.
- Both graph-view sidebars can be resized by the user.
- The canvas no longer depends on stacked cards for basic information display.

Status: not started

### 8. Node And Edge Visual Language

Goal: Make nodes and edges readable through iconography and hierarchy rather than verbose text blocks.

Main actions:

- Add stable icon mapping for common agent roles such as planner, worker, synthesizer, validator, reviewer, tool, approval gate, and output.
- Add edge semantics iconography for context handoff, artifact handoff, review flow, approval, and multimodal transfer.
- Reduce node chrome, tighten typography, and remove unclear or low-value symbols.

Acceptance criteria:

- Nodes use consistent iconography with tooltip disclosure.
- Edges communicate their semantics without long inline labels.
- Screenshots show smaller type, less visual noise, and no unexplained symbols.

Status: not started

### 9. Inspector Refactor

Goal: Make the inspector compact, structured, and object-context aware instead of a cramped form dump.

Main actions:

- Move secondary run details and expanded configuration into grouped collapsible sections.
- Refactor field ordering around common edit flows: prompt, provider or model, output, edge policy, safety, advanced.
- Clean overflow, spacing, and checkbox or list layout issues.

Acceptance criteria:

- The inspector supports common node and edge editing without excessive scrolling at standard desktop width.
- Secondary settings are hidden by default but remain discoverable.
- Click-driven screenshots confirm inspector usability for both node and edge editing.

Status: not started

### 10. GUI Graph Authoring Core Flows

Goal: Make visible graph authoring work end to end without API shortcuts.

Main actions:

- Use simulated interaction to create nodes, connect edges, edit contracts, save graphs, reload, reopen, export, and import representative graphs.
- Preserve ordered screenshots and a click-path note for each core flow.
- Record the highest-friction authoring steps and remove the worst blockers.

Acceptance criteria:

- At least three representative graph-authoring flows work through the visible UI.
- Validation artifacts include replayable click paths and screenshots.
- Reload or reopen proves the saved state is durable.

Status: not started

### 11. GUI Run Surface, Trace, And Artifact Inspection

Goal: Make graph execution understandable from the visible product surface.

Main actions:

- Surface run state on the canvas and in the inspector without flooding the canvas with raw text.
- Let users inspect node outputs, edge handoffs, artifacts, timing, and diagnostics through visible controls.
- Validate the flow during a real execution path from the GUI.

Acceptance criteria:

- A user can inspect at least one node output and one edge handoff through visible controls.
- Screenshots prove the run monitor works during execution.
- The canvas stays primary while detail remains discoverable.

Status: not started

### 12. Code And GUI Round-Trip Dogfood

Goal: Prove the shared-contract story with real product evidence.

Main actions:

- Create one graph from code and one from the GUI.
- Round-trip both through import, export, edit, and execute paths.
- Compare graph specs, compiled plans, manifests, and visible behavior.

Acceptance criteria:

- One code-authored and one GUI-authored graph both execute through the same runtime path.
- Required contract fields survive round-trip.
- Evidence packs preserve graph files, compiled plans, manifests, and screenshots.

Status: not started

### 13. Main-Agent Repair Skill And Runbook

Goal: Teach future agents how to maintain and repair graph, runtime, and capability-adaptation issues safely.

Main actions:

- Create or update a skill or runbook for diagnosing graph, runtime, multimodal, and provider compatibility regressions.
- Include rules for docs-backed verification, smoke evidence, GUI click validation, rollback, and artifact preservation.
- Encode a bounded workflow for graph repair and capability adaptation.

Acceptance criteria:

- A durable skill or runbook exists on disk and references the canonical graph contract and evidence conventions.
- It requires screenshot-backed GUI validation where a visible path exists.
- It describes rollback and safety boundaries explicitly.

Status: not started

### 14. Regression, Smoke, And Compatibility Gates

Goal: Turn the product slice into something maintainable, not a one-off demo.

Main actions:

- Add focused tests, runtime dry-run cases, graph round-trip tests, UI flow tests, and capability-sensitive checks.
- Define a minimum smoke matrix covering at least code-fix flow, research fan-out/fan-in, and multimodal capability gate.
- Make the regression gate fast enough to catch contract, runtime, and UI drift after future changes.

Acceptance criteria:

- A minimum credible gate exists and can catch contract, runtime, or UI drift.
- The smoke matrix matches the official release slice.
- The gate does not depend on hidden secrets as its only proof route.

Status: not started

### 15. End-To-End Product Acceptance

Goal: Prove through the real product surface that this has become a coherent workflow product rather than a loose feature set.

Main actions:

- Complete three end-to-end journeys: code-fix workflow, research fan-out/fan-in, and multimodal capability gate.
- Complete one code-authored-to-GUI-to-runtime loop and one GUI-authored-to-export loop.
- Summarize supported paths, blocked paths, and remaining gaps in a final report.

Acceptance criteria:

- Evidence includes click paths, screenshots, graph files, run artifacts, and a final validation report.
- The product clearly supports canvas-style workflow orchestration, code orchestration, bounded parallel subagents, context isolation, and structured communication.
- Remaining gaps are recorded explicitly instead of hidden behind general confidence claims.

Status: not started

## Progress Log

### 2026-07-09 - Step 0

- Completed: Rebuilt the ComfyUI-style productization plan into a concrete durable handoff plan that can be executed by later agents without relying on chat history.
- Files changed: `PLAN/AGENT_GRAPH_COMFYUI_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation: Re-read the durable handoff plan skill and template, reviewed adjacent Agent Graph plan files, and aligned this plan with the repository's current productization direction.
- Blockers: None.
- Next step: Step 1, Baseline Gap Audit And Product Slice Lock.

### 2026-07-09 - Plan Review

- Evidence inspected: `PLAN/AGENT_GRAPH_COMFYUI_PRODUCTIZATION_HANDOFF_PLAN.md`, `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`, `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`, and `PLAN/AGENT_GRAPH_PRODUCT_SLICE_EXECUTION_HANDOFF_PLAN.md`
- Diagnosis: The repository already had a plan slot for the ComfyUI-style target, but it needed a tighter, execution-grade handoff contract and a cleaner relation to the existing master and subordinate plan family.
- Route change: Replaced the weaker or stale version of the file with a concrete execution plan focused on release-slice scope, visible UI validation, code or GUI parity, multimodal/provider gating, and a future maintainer skill.
- What must not be weakened: one canonical graph contract; visible click-driven GUI validation; shallow-by-default orchestration; default context isolation; and durable evidence preservation.
- Next step: Step 1, Baseline Gap Audit And Product Slice Lock.

### 2026-07-09 - Plan Hardening For Current Product Baseline

- Evidence inspected: `PLAN/AGENT_GRAPH_COMFYUI_PRODUCTIZATION_HANDOFF_PLAN.md`, `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`, `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`, and `PLAN/AGENT_GRAPH_GUI_RUNTIME_EXECUTION_CHECKLIST.md`
- Diagnosis: The plan objective was correct, but the handoff contract still allowed future agents to waste time re-auditing already-proved runtime and GUI substrate or to create another overlapping plan for the same product target.
- Route change: Added a repository-proved baseline section, an explicit execution entry rule, and a sharper Step 1 audit requirement that distinguishes inherited proof from still-missing product behavior.
- What must not be weakened: one canonical graph contract; visible click-driven GUI validation; code and GUI parity; default context isolation; and the requirement to inherit rather than duplicate already-proved repository work.
- Next step: Step 1, Baseline Gap Audit And Product Slice Lock.

### 2026-07-09 - Plan Hardening For Verifiable Handoff

- Evidence inspected: `C:\\Users\\cyz19\\.codex\\skills\\durable-handoff-plan\\SKILL.md`, `C:\\Users\\cyz19\\.codex\\skills\\durable-handoff-plan\\references\\plan-template.md`, `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`, `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`, and `PLAN/AGENT_GRAPH_COMFYUI_PRODUCTIZATION_HANDOFF_PLAN.md`
- Diagnosis: The existing ComfyUI-style handoff plan had the right objective and step sequence, but it still left too much room for uneven execution quality across future agents. In particular, it did not force a consistent evidence bundle, baseline validation record, or cross-slice acceptance matrix.
- Route change: Added an explicit acceptance-package contract, a mandatory validation baseline, and a release-slice acceptance matrix. This turns the file from a directional roadmap into a stricter execution contract that another agent can follow and that a reviewer can accept or reject without reconstructing chat context.
- What must not be weakened: one canonical graph contract; simulated visible interaction as the default GUI validation path; durable evidence preservation; explicit runtime and recovery proof; and operator-facing usability as a first-class acceptance dimension rather than cosmetic polish.
- Next step: Step 1, Baseline Gap Audit And Product Slice Lock.

### 2026-07-09 - Plan Hardening For Specific Handoff And Acceptance

- Evidence inspected: `C:\\Users\\cyz19\\.codex\\skills\\durable-handoff-plan\\SKILL.md`, `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`, `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`, and `PLAN/AGENT_GRAPH_COMFYUI_PRODUCTIZATION_HANDOFF_PLAN.md`
- Diagnosis: The plan was already durable, but it still relied too much on a reader inferring the current product distance and the reviewer acceptance bar from surrounding files. That creates avoidable ambiguity for future agents and reviewers.
- Route change: Added a concrete current-gap snapshot, a reviewer acceptance checklist, and an explicit execution-mode rule that tells future agents to inherit proved substrate evidence instead of replaying already-accepted work. This makes the file more specific as a handoff contract and reduces duplicate effort.
- What must not be weakened: one canonical graph contract; click-driven visible validation; evidence-backed acceptance instead of narrative confidence; and explicit separation between already-proved substrate, partial product behavior, and still-missing product closure.
- Next step: Step 1, Baseline Gap Audit And Product Slice Lock.
