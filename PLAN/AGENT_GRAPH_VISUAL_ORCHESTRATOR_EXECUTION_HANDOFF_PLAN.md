# Agent Graph Visual Orchestrator Execution Handoff Plan

## Total Objective

Turn AstraBridge Agent Graph into a user-friendly visual orchestrator for arbitrary multimodal, multi-model tasks. The target product is a canvas-first workflow builder closer to "ComfyUI for general agent work" than to a dense form page: users should be able to create or import a graph, add agent nodes, wire typed edges, edit prompt and communication contracts, choose providers and models, run bounded parallel subagents, inspect outputs, and recover from failure through the GUI while sharing one canonical contract with the code-authored path.

This plan is the concrete delegation contract for the current visual-orchestrator slice. Future agents should use this plan as the preferred execution entry point for this product area instead of reconstructing scope from broader plans.

## Deliverables

- A concrete product-slice scope note with competitive acceptance criteria and operator-facing UX gates.
- A canonical graph contract shared by GUI graphs, code-authored graphs, dry-run, runtime execution, persisted evidence, and repair tooling.
- A capability-aware node and port registry that truthfully constrains multimodal routing by provider/model support.
- A generic compiled-graph runtime path with bounded parallel subagents, typed handoff envelopes, approvals, recovery, and durable artifacts.
- A canvas-first GUI flow where users can create nodes, wire edges, edit contracts, inspect outputs, and operate runs with simulated-click validation.
- A self-repair skill or runbook that teaches future agents how to diagnose and fix capability-adaptation and GUI-orchestrator defects through the real app.
- A preserved validation pack under `PRIVATE/agent-graph-visual-orchestrator/**`.

## Release Bar For This Plan

This plan is only considered successful when the following product claims are all backed by preserved evidence:

1. GUI graph authoring:
   - a user can start from the visible app surface;
   - enter the graph view;
   - create or import a workflow;
   - add nodes;
   - connect typed edges by visible interaction;
   - edit at least one node contract and one edge contract;
   - save, reload, and reopen without losing required state.
2. Runtime execution:
   - the same canonical graph can dry-run, compile, and execute through the generic runtime;
   - at least one bounded parallel subagent path and one synthesizer or reviewer path are proven.
3. Inspection and recovery:
   - a user can inspect at least one node output and one edge handoff from visible controls;
   - a user can exercise at least one failure-recovery path such as retry, partial rerun, or resume.
4. Code parity:
   - the same graph can be authored or edited through a code-first path, then round-trip through the GUI without dropping required contract fields.

The following conditions are explicit rejection reasons even if backend tests pass:

- the canvas is still visually secondary to cards, summaries, or oversized sidebars;
- graph authoring depends primarily on hidden APIs, injected state, or console-side mutation;
- save state, recovery scope, or typed compatibility is not understandable from the visible product;
- node and edge editing only partially persists or requires debug-only entry paths;
- code-first and GUI paths drift into incompatible contract shapes.

## Related Context Files

- `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `PLAN/AGENT_GRAPH_PRODUCT_SLICE_EXECUTION_HANDOFF_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_CLICK_DRIVEN_PRODUCTIZATION_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SCOPE_AND_UX_PRINCIPLES.md`
- `PLAN/MULTIMODAL_ADAPTER_FAMILY_CONTRACT.md`
- `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_compiler.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
- `apps/astrabridge-desktop/src/styles.css`
- `apps/astrabridge-sidecar/skills/agent-orchestration-operator/SKILL.md`

## Constraints And Attention Notes

1. `Project -> Task` remains the product boundary. Graph runs, subagents, provider lanes, artifacts, and internal worker state stay scoped under the task.
2. GUI graphs and code-authored graphs must compile into the same canonical workflow contract. No shadow graph format is allowed.
3. Subagent context isolation is the default. Full transcript inheritance, provider-private reasoning, or unrelated worker scratchpads must not cross edges implicitly.
4. Every edge must declare a typed handoff contract and context policy. Natural-language-only hidden conventions are insufficient.
5. Multimodal routing must be capability-aware. A provider/model cannot be presented as valid for a modality unless docs-backed metadata or smoke evidence supports it.
6. Every GUI-facing step must be validated by simulated user interaction in the running app. API-only proof is never enough.
7. Every GUI-facing step must preserve screenshots before the key interaction, during the flow, after the state change, and after reload or reopen when persistence is involved.
8. Agents executing this plan must prefer clicking, typing, dragging, hovering, resizing, and scrolling through the real product over direct store mutation, hidden route forcing, or internal API shortcuts.
9. The canvas is primary. Avoid card stacking, oversized typography, redundant low-semantic metadata, inspector sprawl, wasted framing, and controls that consume prime canvas space.
10. High-risk actions such as paid provider calls, source mutation, installs, or external writeback must remain approval-gated and auditable.
11. Preserve logs, screenshots, traces, exported graphs, compiled plans, dry-run reports, run manifests, node envelopes, and sanitized diagnostics under `PRIVATE/**`.
12. Never persist secrets, auth headers, cookies, vault material, desktop key files, or raw secret-bearing payloads in plans, artifacts, screenshots, logs, or staged changes.
13. For GUI claims, another agent must be able to reproduce the same path from preserved screenshots and notes without reading chat history.
14. For runtime claims, another agent must be able to reproduce the same result from preserved specs, tests, and durable artifacts without relying on ephemeral UI state.

## Adjustment Policy

Agents may reasonably adjust filenames, substeps, commands, sequencing, UI selectors, evidence filenames, and implementation details when repository evidence requires it. Adjustments must not change the total objective, remove the click-driven usability gate, weaken typed communication or context isolation, replace runtime work with cosmetic-only work, or split GUI and code execution into incompatible systems.

If evidence shows the current route is stale, revise the plan before continuing and log:

- evidence inspected;
- diagnosis;
- route change;
- what must not be weakened;
- exact next step.

## Evidence Review And Plan Revision Policy

Before executing the next step, future agents must check whether a plan review is needed. Trigger a review when:

1. repository evidence contradicts the assumed runtime or UI architecture;
2. fixture success does not prove the generic runtime path;
3. GUI screenshots show operator-hostile layout, discoverability, or state-clarity problems that block normal use;
4. provider/model capability evidence invalidates a planned multimodal route;
5. a completed step proves only schema or only UI, while the total objective requires both;
6. the next step would produce documentation or polish while the highest-leverage blocker remains runtime, typed communication, or execution safety;
7. a proposed shortcut would bypass simulated clicks, typed contracts, or context-isolation guarantees.

## Execution Rules

1. Each execution turn must start by reading this plan and checking the evidence-review triggers.
2. Complete exactly one numbered step per turn unless the user explicitly asks otherwise.
3. Update this plan before stopping.
4. A step may be marked `completed` only when every acceptance criterion is satisfied.
5. GUI-facing steps must be executed through simulated interaction in the running app:
   - open the real app in the in-app browser;
   - reach the target surface through visible controls when feasible;
   - click, type, drag, hover, resize, scroll, expand, collapse, and reload through real controls;
   - capture screenshots frequently enough to prove UX quality, not just backend correctness.
6. If a visible click path fails, preserve the failing screenshot or trace before using lower-level diagnosis.
7. Runtime steps must preserve deterministic tests plus at least one durable sanitized artifact such as a compiled plan, dry-run report, run manifest, node envelope, or event trace.
8. No GUI-facing step is complete until the changed flow still works after reload or reopen when persistence is involved.
9. Each turn must end with a strong handoff: completed work, files changed, validation commands, evidence path, blockers, any route revision, and exact next step.

## Simulated Interaction Gate

Any agent executing GUI-facing steps under this plan must treat product interaction as a hard acceptance gate:

1. operate the running AstraBridge app instead of claiming success from internal APIs alone;
2. prefer simulated clicks and drags over hidden state injection;
3. take screenshots repeatedly while editing or validating the workflow;
4. explicitly record common UX defects when encountered: card stacking, wasted panels, oversized fonts, ambiguous icons, redundant metadata, invisible save state, dead buttons, blocked scroll areas, awkward resizing, and inspector overflow;
5. do not mark a GUI step complete until the changed flow still works after reload or reopen when persistence is involved.

## Handoff Entry Rule

Future agents should resume this product area from this plan before reading chat history. The expected order is:

1. read this file;
2. read `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md` for the umbrella objective;
3. locate the earliest non-completed step here;
4. gather current repository and UI evidence for that step;
5. complete one full numbered step;
6. update both this plan and the umbrella plan when the step materially changes product status.

## Operator Proof Standard

Every future agent executing a GUI-facing step under this plan must satisfy this proof standard:

1. Use the in-app browser as the default validation surface.
2. Reach the target feature from the visible product path instead of hidden debug routes when a visible path exists.
3. Prefer simulated click, drag, hover, scroll, resize, expand, collapse, and text-entry interactions over internal API calls or direct state mutation.
4. Take screenshots frequently enough to show:
   - initial state;
   - the entry interaction;
   - each major state transition;
   - the post-save or post-run state;
   - the post-reload or post-reopen state.
5. When layout changes are involved, include at least one constrained-width or panel-stressed screenshot pass.
6. When a GUI defect is discovered, preserve the pre-fix screenshot or trace before claiming the fix.
7. Do not claim a user-friendly result if the path still depends on hidden prerequisites, dead zones, oversized chrome, or unexplained icons.

## Evidence Convention

- Default artifact root: `PRIVATE/agent-graph-visual-orchestrator/<step-id>/<YYYYMMDD>/`
- Backend steps must preserve:
  - a concise report;
  - test output summary;
  - relevant exported specs or fixtures;
  - sanitized validation logs.
- Runtime steps must preserve:
  - graph spec or import source;
  - compiled plan;
  - dry-run output;
  - run manifest;
  - node input or output envelopes when relevant;
  - event trace;
  - recovery or rollback evidence when relevant.
- GUI-facing steps must preserve:
  - `01-entry.png`
  - `02-before-change.png`
  - `03-in-flow-*.png`
  - `04-after-change.png`
  - `05-after-reload.png`
  - `06-constrained-width.png` when layout, inspector, or panel density is touched
  - `validation-note.md` with exact click path, typed values, observed state, and remaining friction.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Freeze Product Slice And Competitive Acceptance Bar
- Next step: Step 1, Freeze Product Slice And Competitive Acceptance Bar
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: Create this handoff plan and make the next entry point unambiguous.

Main actions:

- Define the concrete visual-orchestrator objective.
- Record constraints, evidence policy, execution rules, and acceptance gates.
- Set the first actionable step.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, deliverables, constraints, adjustment policy, evidence-review policy, execution rules, current progress, numbered steps, and progress log.
- Simulated-click validation is explicitly mandatory for GUI-facing steps.

Status: completed

### 1. Freeze Product Slice And Competitive Acceptance Bar

Goal: Define the first product slice that must feel credible against common visual agent and workflow tools.

Main actions:

- Write `scope-and-acceptance.md` under the step evidence root.
- Compare the first AstraBridge slice against the minimum useful behavior borrowed from ComfyUI-like builders, LangGraph Studio-like inspectability, and dynamic-workflow-style execution.
- Freeze the first supported user journeys:
  - create graph from template or blank;
  - add nodes;
  - wire typed edges;
  - edit prompt and handoff contract;
  - dry-run;
  - run in fixture mode;
  - inspect node output and edge handoff;
  - approve or reject a gated action;
  - retry or partial-rerun after failure.
- Define explicit UI acceptance gates:
  - canvas-first layout;
  - collapsible and resizable side panels;
  - low-noise metadata;
  - readable density;
  - visible save state;
  - discoverable controls;
  - no card-stacking default layout;
  - no inspector or summary panel that dominates the canvas without an active selection or run-inspection reason.
- Define explicit workflow acceptance gates:
  - GUI drag or click authoring path is complete without debug shortcuts;
  - code-authored import/export path round-trips through the same contract;
  - one bounded parallel subagent workflow is in scope for the first credible slice;
  - typed handoff and context-isolation behavior are inspectable rather than implied.

Acceptance criteria:

- `scope-and-acceptance.md` exists under `PRIVATE/agent-graph-visual-orchestrator/step1-slice-and-acceptance/<YYYYMMDD>/`.
- The artifact defines required user journeys, non-goals, and UI rejection reasons.
- Another agent can use the artifact to reject a backend-correct but UX-poor change without rereading chat.
- The artifact includes explicit rejection examples: oversized sidebars, redundant summary cards, text-first edge semantics, hidden save state, and graph-edit actions that cannot be completed from visible controls.

Status: not started

### 2. Lock The Canonical Workflow Contract

Goal: Make GUI authoring, code authoring, runtime compilation, and evidence storage share one graph contract.

Main actions:

- Finalize node, edge, port, modality, tool-policy, subagent-policy, context-policy, approval-policy, and UI-metadata fields.
- Define import and migration rules from current task graph records.
- Define what fields must survive GUI round-trip, code round-trip, and dry-run export.
- Preserve a contract note or code-diff report under the step evidence root.

Acceptance criteria:

- Contract documentation or code contract update exists on disk.
- Tests or fixtures prove:
  - valid graph;
  - invalid unsafe sharing;
  - invalid modality route;
  - migration compatibility.
- The contract remains diffable and JSON-serializable.

Status: not started

### 3. Build The Capability-Aware Node And Port Registry

Goal: Ensure multimodal and provider/model choices are grounded in real capability data.

Main actions:

- Define standard node families, port types, edge attributes, and icon mappings.
- Connect modality claims to provider/model capability metadata and smoke evidence.
- Define fallback behavior when a capability is docs-backed but not yet live-verified.
- Preserve a matrix or registry report showing supported and rejected combinations.

Acceptance criteria:

- A registry artifact or implementation exists that maps node types, port types, and capability constraints.
- Unsupported provider/model and modality combinations are blocked or warned deterministically.
- Tests cover at least:
  - text;
  - image;
  - document;
  - structured JSON;
  - agent-report ports.

Status: not started

### 4. Finish The Graph Compiler And Compiled-Plan Artifact

Goal: Compile canonical graphs into explicit, inspectable execution plans.

Main actions:

- Validate topology, joins, approval gates, context envelopes, retry posture, and artifact requirements.
- Emit a durable compiled-plan artifact into the run layout.
- Expose enough metadata that a later agent or user can inspect the execution plan without provider calls.

Acceptance criteria:

- Compiler tests cover:
  - linear flow;
  - fan-out and fan-in;
  - approval-gated flow;
  - invalid cycle;
  - missing dependency;
  - unsupported port cases.
- The compiled plan is written to the durable artifact layout.
- Unsafe implicit full-history sharing is rejected.

Status: not started

### 5. Land The Generic Runtime Scheduler

Goal: Execute compiled graphs generically rather than through template-specific fixture branches.

Main actions:

- Start ready nodes, unlock downstream nodes, enforce max parallelism, and record run events.
- Support fixture mode first, then provider-backed mode when separately authorized.
- Persist durable node state, run state, and event refs.

Acceptance criteria:

- A generic graph runs through the scheduler in fixture mode.
- Tests cover:
  - success;
  - failure;
  - fan-out and fan-in completion;
  - blocked downstream;
  - durable reload.
- Legacy template-specific branches are either migrated or explicitly marked as compatibility shims.

Status: not started

### 6. Implement Typed Handoff Envelopes And Context Isolation

Goal: Make inter-node communication explicit, typed, and minimally shared.

Main actions:

- Define node input and output envelopes for text, summaries, machine results, artifacts, resource refs, and multimodal payload refs.
- Apply edge policies when constructing downstream inputs.
- Add redaction and secret-safety checks before writing durable envelopes.

Acceptance criteria:

- Tests prove downstream nodes receive only allowed parts.
- `exclude_private_memory=true` is the default and unsafe sharing is rejected.
- Envelope artifacts are durable and inspectable without exposing secrets.

Status: not started

### 7. Implement Bounded Subagent Execution

Goal: Treat worker and synthesizer nodes as real bounded subagent jobs.

Main actions:

- Map node execution policy to subagent spawn parameters such as prompt, model/provider, tools, skills, permission posture, timeout, max turns, and isolation mode.
- Persist graph-run to subagent lineage.
- Capture subagent result envelopes and artifact refs for downstream handoff.

Acceptance criteria:

- A graph node can spawn a bounded subagent in deterministic validation.
- Subagent context does not inherit full parent conversation by default.
- Lineage records link graph run, node, worker thread or lane, and produced artifacts.

Status: not started

### 8. Rebuild The Canvas UI Around Node Density And Clarity

Goal: Make the visual builder feel like a real workflow tool instead of stacked cards and oversized side panels.

Main actions:

- Reduce unnecessary background cards, chrome, and low-value labels.
- Keep left and right panels collapsible, resizable, and secondary to the canvas.
- Tighten typography, node dimensions, spacing, and icon use so graphs remain readable at realistic density.
- Validate by opening the app, interacting with the task-graph view, resizing panels, and preserving screenshots.
- Move repeated low-semantic descriptions, secondary summaries, and detached action buttons out of the canvas-first view unless they are required for the immediate object or run state.

Acceptance criteria:

- The canvas is visually dominant at tested widths.
- Side panels can be collapsed and resized by the user.
- Simulated-click evidence shows improved readability, lower chrome overhead, and no obvious inspector overflow or stacked-card clutter.
- Screenshots show that common actions remain discoverable after density reduction; this step must not trade clarity for minimalism.

Status: not started

### 9. Ship Clickable Node Creation And Typed Edge Wiring

Goal: Let users compose graphs directly from the UI without API shortcuts.

Main actions:

- Support node creation from visible controls, drag or click placement, typed port display, edge creation, and edge selection.
- Use icons and hover tooltips for common agent and edge semantics instead of verbose always-on text.
- Keep save and dirty state visible and understandable.
- Validate through the real app with preserved screenshot cadence.
- Require the validating agent to complete the composition path without internal API calls, hidden fixture injection, or route-forced state edits.

Acceptance criteria:

- A future agent can create a graph from the visible UI through simulated clicks and drags.
- Edge types and node roles are understandable from icons plus hover, not large static text blocks.
- Screenshots show readable density and usable node sizing.
- Validation notes include the exact interaction recipe for add-node, connect-edge, edit-selection, save, and reopen.

Status: not started

### 10. Expose Prompt, Contract, And Capability Editing In The Inspector

Goal: Let users change what each node and edge actually does from visible controls.

Main actions:

- Add inspector controls for prompt templates, provider/model choice, modality constraints, output schema, tool policy, subagent policy, and context policy.
- Make advanced fields collapsible but discoverable.
- Add inline validation and save feedback.

Acceptance criteria:

- A user can edit a node prompt, provider/model, and at least one contract field through the GUI.
- A user can edit edge context and handoff behavior through the GUI.
- Invalid edits are blocked with understandable feedback and preserved evidence.

Status: not started

### 11. Build Run Monitor, Output Inspection, And Approval UX

Goal: Make runtime behavior understandable and operable from the product surface.

Main actions:

- Show run state on the canvas and inspector: queued, running, blocked, waiting approval, failed, succeeded, cancelled.
- Let users inspect node outputs, edge handoffs, artifacts, and diagnostics.
- Support visible approve and reject actions for gated nodes.

Acceptance criteria:

- A click-driven run shows progress and output inspection from visible controls.
- Approval and rejection can both be exercised from the GUI in a bounded validation path.
- The tested path survives reload with durable run state intact.

Status: not started

### 12. Add Failure Recovery, Retry, And Partial Rerun

Goal: Keep graph execution usable when runs fail or stop mid-flight.

Main actions:

- Add cancel, retry failed node, rerun selected node, and partial downstream rerun behavior.
- Preserve failure diagnostics and recovery traces.
- Make the operator-visible scope of rerun explicit.

Acceptance criteria:

- Tests cover cancel, retry, rerun selected node, and durable reload.
- The GUI exposes enough information for a user to understand what will rerun.
- Evidence includes failure, recovery action, and post-reload state.

Status: not started

### 13. Land Code-Authored Graph Parity

Goal: Make code-defined graphs a first-class interface rather than a side path.

Main actions:

- Ensure lint, dry-run, import, export, diff, migrate, and execution all work for code-authored graphs using the canonical contract.
- Provide repository examples for common workflows.
- Prove GUI and code round-trip parity on required fields.

Acceptance criteria:

- A code-authored graph can be linted, dry-run, imported into the GUI, exported back out, and re-executed.
- Round-trip tests show required fields are preserved.
- The code-first interface does not create a second incompatible workflow format.

Status: not started

### 14. Create The Agent Self-Repair Skill And Runbook

Goal: Teach future agents how to diagnose and repair model-capability adaptation and visual-orchestrator defects.

Main actions:

- Create or update a skill or runbook with commands, UI click recipes, evidence rules, and safety boundaries.
- Require agents to verify GUI fixes through simulated clicks and repeated screenshots.
- Include repair patterns for:
  - capability mismatch;
  - modality exposure bugs;
  - graph validation defects;
  - operator-hostile UI.

Acceptance criteria:

- A durable skill or runbook exists on disk.
- It tells another agent exactly how to reproduce, fix, and validate the product path.
- It explicitly forbids claiming a GUI fix without click-driven proof.
- It includes a short anti-pattern list covering API-only acceptance, hidden state mutation, screenshot omission, and shipping layout regressions without constrained-width review.

Status: not started

### 15. Run The End-To-End Product Gate

Goal: Prove the first visual-orchestrator slice works as a product feature.

Main actions:

- Create or import a graph through the GUI.
- Edit nodes and edges, dry-run it, run it in fixture mode, inspect outputs, exercise one approval path, and exercise one recovery path.
- Preserve screenshots, compiled plans, run manifests, artifacts, and the final validation report.

Acceptance criteria:

- A full evidence pack exists under the evidence root.
- The validated path starts from the visible product surface and uses simulated interaction instead of hidden state shortcuts.
- Residual gaps are recorded concretely enough for the next agent to continue without replaying chat history.

Status: not started

## Progress Log

### 2026-07-09 - Step 0

- Completed: Created a durable execution handoff plan for turning Agent Graph into a multimodal, multi-model visual orchestrator with a shared code/runtime/UI contract and a hard simulated-click validation bar.
- Files changed: `PLAN/AGENT_GRAPH_VISUAL_ORCHESTRATOR_EXECUTION_HANDOFF_PLAN.md`
- Validation:
  - Read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`
  - Read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\references\plan-template.md`
  - Reviewed adjacent repository plans to avoid conflicting execution contracts.
- Blockers: None.
- Next step: Step 1, Freeze Product Slice And Competitive Acceptance Bar.

### 2026-07-09 - Plan Review

- Evidence inspected:
  - `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`
  - `C:\Users\cyz19\.codex\skills\durable-handoff-plan\references\plan-template.md`
  - `D:\AstraBridge\PLAN\AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
  - `D:\AstraBridge\PLAN\AGENT_GRAPH_VISUAL_ORCHESTRATOR_EXECUTION_HANDOFF_PLAN.md`
- Diagnosis: The prior handoff plan had the right direction but was still too broad for low-context delegation. Another agent would still need to infer acceptance artifacts, screenshot cadence, and concrete reproduction rules.
- Route change: Refreshed this handoff plan into a stricter execution contract with explicit artifact names, GUI interaction rules, concrete user journeys, and sharper acceptance gates for backend, runtime, and UI work.
- What must not be weakened: One canonical graph contract, typed handoff and context isolation, capability-aware multimodal routing, and simulated-click validation for every GUI-facing claim.
- Next step: Step 1, Freeze Product Slice And Competitive Acceptance Bar.

### 2026-07-09 - Plan Hardening For Visual-Orchestrator Product Gate

- Evidence inspected:
  - `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`
  - `C:\Users\cyz19\.codex\skills\durable-handoff-plan\references\plan-template.md`
  - `D:\AstraBridge\PLAN\AGENT_GRAPH_VISUAL_ORCHESTRATOR_EXECUTION_HANDOFF_PLAN.md`
  - `D:\AstraBridge\PLAN\AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- Diagnosis: The existing plan direction was correct, but the execution contract still left too much room for future agents to claim success from API-level changes or thin screenshot evidence. The user has been explicit that GUI validation must force user-friendly behavior, especially around canvas priority, panel density, and simulated interaction.
- Route change: Hardened this plan with an explicit `Operator Proof Standard`, stronger screenshot cadence, more concrete rejection reasons for UX regressions, and step-level acceptance language that forces visible-path composition and constrained-width review.
- What must not be weakened: One canonical graph contract, code-first and GUI parity, default context isolation, capability-aware multimodal routing, and simulated-click proof for every GUI-facing claim.
- Next step: Step 1, Freeze Product Slice And Competitive Acceptance Bar.

### 2026-07-09 - Plan Refresh For ComfyUI-Like Product Handoff

- Evidence inspected:
  - `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`
  - `C:\Users\cyz19\.codex\skills\durable-handoff-plan\references\plan-template.md`
  - `D:\AstraBridge\PLAN\AGENT_GRAPH_VISUAL_ORCHESTRATOR_EXECUTION_HANDOFF_PLAN.md`
  - `D:\AstraBridge\PLAN\AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- Diagnosis: The plan direction was already correct, but the handoff contract still needed a clearer release bar for the exact product target discussed with the user: a ComfyUI-like general workflow surface with GUI authoring, code parity, bounded parallel subagents, typed handoffs, and visible recovery.
- Route change: Added an explicit release bar, hard rejection reasons, and a handoff entry rule so another agent can accept or reject progress without reconstructing prior discussion.
- What must not be weakened: one canonical graph contract; canvas-first UX; GUI/code/runtime parity; shallow-by-default subagent orchestration; typed context isolation; simulated-click validation.
- Next step: Step 1, Freeze Product Slice And Competitive Acceptance Bar.
