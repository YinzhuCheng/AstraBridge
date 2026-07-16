# Agent Graph Orchestrator Benchmark And Product Execution Plan

## Total Objective

Produce a source-backed, execution-ready plan that moves AstraBridge Agent Graph toward a user-friendly, multimodal, multi-model agent orchestrator comparable in operator experience to mainstream visual workflow tools while preserving AstraBridge's canonical graph contract, bounded subagent runtime, typed communication, and GUI-first usability. The target outcome is not only a research memo: it must drive concrete product work for GUI orchestration, code-first orchestration, subagent isolation, inter-agent communication contracts, and repeatable click-driven validation.

## Deliverables

- A benchmark report covering commonly used visual agent or workflow orchestrators, their interaction model, graph contract shape, code-first surface, runtime inspection model, and user-facing tradeoffs.
- A source-backed AstraBridge gap report that maps current GUI/runtime capability to the benchmark set.
- A concrete UX and contract target for AstraBridge Agent Graph, including GUI authoring, code authoring, subagent policy, typed edge semantics, and operator inspection flows.
- A validated implementation slice for code-first orchestration and GUI-first orchestration that share one canonical graph contract.
- A click-driven evidence pack under `PRIVATE/agent-graph-orchestrator-benchmark/**` with screenshots, interaction traces, validation notes, and acceptance reports.

## Constraints And Attention Notes

1. This plan complements, but does not replace, `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md` and `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`.
2. Benchmark conclusions must be backed by current public sources or public repository evidence. Do not rely on memory-only product descriptions when current docs or repos are available.
3. GUI claims require simulated user interaction in the visible product surface. Do not accept API-only or hidden-state proof when a visible path exists.
4. Future agents executing UI steps must operate the in-app browser by clicking, dragging, typing, hovering, scrolling, resizing, collapsing, and expanding. They must not treat direct store writes, console mutation, or sidecar-only calls as GUI acceptance.
5. Every UI-touching step must preserve screenshots before the change, after the change, after the main interaction path, and after reload or reopen.
6. The canvas must remain primary. Avoid card stacking, large dead-space frames, low-semantic text blocks, oversized fonts, inspector sprawl, and redundant chrome.
7. Code-first orchestration must share the same graph contract as GUI orchestration. Do not create a second incompatible workflow language.
8. Subagents must remain context-isolated by default. Cross-agent communication must stay explicit, typed, and inspectable.
9. Preserve diagnostics, traces, benchmark notes, screenshots, run manifests, and validation reports under `PRIVATE/**`. Do not clean them unless the user explicitly names targets.
10. Never persist API keys, bearer tokens, cookies, auth headers, vault secrets, or desktop secret material in plan artifacts, screenshots, logs, or reports.

## Adjustment Policy

Agents may adjust benchmark scope, step sequencing, filenames, evidence layout, or implementation order when repository evidence or current product state requires it. Adjustments must not weaken the objective, turn GUI validation into API-only validation, split the canonical graph contract, or replace runtime and usability work with cosmetic-only polish.

If current evidence shows the route is stale, agents must revise this plan before continuing. Every revision must record the evidence inspected, diagnosis, route change, what must not be weakened, and the exact next step.

## Evidence Review And Plan Revision Policy

Before executing the next numbered step, check whether any of these triggers apply:

1. current public docs or repo evidence contradict the assumed benchmark landscape;
2. AstraBridge already implements part of a planned slice and the real blocker is elsewhere;
3. GUI screenshots show operator friction severe enough that further feature work would be wasted without UX correction;
4. code-first and GUI-first graph behavior diverge in contract shape or runtime behavior;
5. a completed step's acceptance criteria are too weak to support the target product shape;
6. the next step would add polish while the current highest-leverage blocker is runtime, isolation, typed communication, or operator flow;
7. a proposed change would create a second orchestration engine instead of extending the canonical graph path.

When a trigger applies, revise the plan first. Allowed revisions include splitting a step, adding a stronger benchmark or validation step, reordering implementation, or inserting a decision gate. Do not weaken the total objective or quality bar without user approval.

## Execution Rules

1. Each agent turn executing this plan must begin by reading this file and the linked Agent Graph master plans.
2. Start from the earliest numbered step whose status is not `completed`, unless the user explicitly redirects.
3. Complete exactly one numbered step per turn unless the user explicitly asks for more.
4. Update this plan before stopping.
5. A step can be marked `completed` only when all acceptance criteria are met.
6. UI-facing steps must use simulated user interaction in the in-app browser. Direct API manipulation does not count as acceptance when a visible path exists.
7. Every UI-facing step must preserve:
   - one starting screenshot;
   - screenshots after major interactions;
   - one final screenshot after reload or reopen;
   - one validation note with the exact click/drag/type/resize path;
   - one constrained-width or sidebar-stressed pass when layout is touched.
8. Benchmark and documentation steps must preserve source links, dates checked, and repo paths inspected.
9. Final handoff for each turn must name completed work, files changed, validation run, evidence path, blockers, and exact next step.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Benchmark The Common Visual Agent Orchestrators
- Next step: Step 1, Benchmark The Common Visual Agent Orchestrators
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: Create this durable execution plan and make the first entry point explicit.

Main actions:

- Define the benchmark and productization objective.
- Record constraints, evidence rules, execution rules, and step acceptance gates.
- Set the initial next step.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes objective, constraints, adjustment policy, evidence review policy, current progress, execution steps, acceptance criteria, and progress log.
- Step 1 is clearly identified as the next entry point.

Status: completed

### 1. Benchmark The Common Visual Agent Orchestrators

Goal: Build a current benchmark of the main visual agent or workflow orchestrators relevant to AstraBridge's target product shape.

Main actions:

- Research the current public product and open-source landscape for tools such as ComfyUI, LangGraph Studio, AutoGen Studio, Flowise, Langflow, Dify, Rivet, n8n, and other directly relevant agent-graph builders.
- Record for each benchmark: GUI authoring model, code-first surface, node library model, edge semantics, run inspection, recovery model, template reuse, subagent or worker model, and strengths or weaknesses for operator usability.
- Save a benchmark report with exact source links and dates checked.

Acceptance criteria:

- A benchmark report exists under `PRIVATE/agent-graph-orchestrator-benchmark/step1-benchmark/<YYYYMMDD>/`.
- The report covers at least five relevant products or open-source systems.
- Every benchmark entry cites current sources or public repository evidence.
- The report explicitly identifies the patterns AstraBridge should adopt, adapt, or avoid.

Status: not started

### 2. Map AstraBridge Against The Benchmark Set

Goal: Turn the benchmark into a source-backed AstraBridge gap map.

Main actions:

- Inspect the current AstraBridge graph contract, GUI task-graph workspace, runtime scheduler, subagent surfaces, typed edge semantics, and validation artifacts.
- Compare AstraBridge's current state against the benchmark dimensions established in Step 1.
- Separate already-implemented capability, partial capability, missing capability, and misleading or UI-incomplete capability.

Acceptance criteria:

- A gap report exists under `PRIVATE/agent-graph-orchestrator-benchmark/step2-gap-map/<YYYYMMDD>/`.
- The report cites exact AstraBridge source files and current evidence artifacts.
- The report identifies the three highest-leverage product gaps and the three most urgent UX gaps.
- No product code changes occur in this step.

Status: not started

### 3. Define The Canonical Product Target

Goal: Convert the benchmark and gap findings into a precise AstraBridge orchestrator target.

Main actions:

- Define the target operator workflow for creating, editing, wiring, running, inspecting, recovering, and reusing agent graphs.
- Define the product stance on GUI-first orchestration, code-first orchestration, template reuse, subgraph depth, and default subagent isolation.
- Write the target spec as a durable design brief linked to the canonical graph contract.

Acceptance criteria:

- A design brief exists under `PLAN/` or `PRIVATE/agent-graph-orchestrator-benchmark/step3-target/<YYYYMMDD>/`.
- The brief defines GUI primitives, code primitives, runtime primitives, and communication primitives.
- The brief explicitly states what AstraBridge will not do, including uncontrolled deep nesting and implicit full-history sharing.
- The brief is concrete enough to drive implementation without chat reconstruction.

Status: not started

### 4. Specify The Code-First Orchestration Surface

Goal: Define how users and agents can author the same workflow by code.

Main actions:

- Specify the code-facing interface for graph authoring, editing, diffing, validation, import/export, and execution.
- Decide whether the interface is file-first, DSL-first, API-first, or hybrid, while preserving the canonical contract.
- Define how prompts, output schemas, communication schemas, provider routing, and subagent policy are expressed in code.

Acceptance criteria:

- A code-first interface spec exists with examples for at least three representative workflow patterns.
- The spec clearly round-trips to the GUI graph contract without lossy fields.
- The spec includes validation expectations and migration expectations.
- The spec does not introduce a second incompatible workflow language.

Status: not started

### 5. Specify The GUI-First Orchestration Surface

Goal: Define the target GUI interactions for user-friendly graph authoring and editing.

Main actions:

- Specify the canvas-first interaction model for adding agents, wiring edges, editing prompts, assigning models, setting communication policy, and reviewing outputs.
- Define which information stays on the canvas, which moves into hover tooltips, and which belongs only in the inspector.
- Define icon usage, text density, default collapsed states, sidebar behavior, and resize affordances.

Acceptance criteria:

- A GUI interaction spec exists with concrete interaction sequences.
- The spec explicitly minimizes redundant cards, low-semantic text, and oversized labels.
- The spec includes default collapsed states and visible hover-detail behavior.
- The spec defines acceptance expectations using simulated clicks and screenshots.

Status: not started

### 6. Define The Subagent And Communication Contract

Goal: Lock down how subagents are spawned, isolated, and allowed to communicate.

Main actions:

- Define bounded subagent policy fields: prompt scope, model/provider, tools, skills, permissions, max turns, execution budget, and isolation mode.
- Define edge communication envelopes for summaries, machine outputs, artifacts, approvals, multimodal payloads, and resource refs.
- Define default privacy and redaction rules for inter-agent communication.

Acceptance criteria:

- A contract note exists that covers node execution policy and edge communication policy together.
- The note explicitly defines default context isolation and explicit opt-in sharing.
- The note includes validation rules for invalid or unsafe communication contracts.
- The note is aligned with current runtime and graph contract code paths.

Status: not started

### 7. Implement The First Shared Code-And-GUI Orchestration Slice

Goal: Land one end-to-end implementation slice that proves code-authored and GUI-authored graphs use the same contract.

Main actions:

- Choose one representative workflow pattern such as supervisor-worker-synthesizer or code-fix-test-review.
- Implement the missing contract, import/export, or runtime glue needed so the graph can be authored, edited, and executed from both code and GUI.
- Preserve deterministic tests and fixture evidence.

Acceptance criteria:

- One representative workflow can be authored in code and edited in GUI without losing required fields.
- Focused tests cover the shared contract and at least one round-trip path.
- Evidence shows one coherent graph path rather than two parallel engines.
- The implementation slice is preserved with reproducible validation steps.

Status: not started

### 8. Implement The First User-Friendly GUI Authoring Slice

Goal: Land the first GUI slice that clearly improves operator usability rather than only adding raw capability.

Main actions:

- Implement the highest-leverage GUI authoring improvements from the prior steps.
- Validate them through simulated user interaction in the in-app browser.
- Capture before/after screenshots and operator-path notes.

Acceptance criteria:

- The visible UI authoring path is measurably clearer and denser than before.
- Screenshots show the actual improvement in canvas priority and editability.
- Validation notes record the exact click path and remaining friction.
- Focused tests pass for the touched surface where tests exist.

Status: not started

### 9. Implement The First Subagent Runtime And Inspection Slice

Goal: Prove bounded subagent execution and inspection through the visible product path.

Main actions:

- Implement or harden one shallow graph with parallel or sequential subagent execution.
- Verify users can inspect node role, assigned model/provider, communication outputs, and recovery state from the GUI.
- Preserve run manifests, screenshots, and validation notes.

Acceptance criteria:

- A shallow multi-agent graph runs through the canonical scheduler.
- The visible UI exposes meaningful execution and communication state.
- Evidence connects UI interactions to durable backend run artifacts.
- Default context isolation is preserved and documented.

Status: not started

### 10. Add The Repository Skill For Agent-Led Orchestrator Maintenance

Goal: Give future agents a bounded skill for benchmarking, adapting, validating, and repairing the orchestrator product surface.

Main actions:

- Create or update a repository-local skill that teaches agents how to benchmark the market, inspect the local graph contract, modify the product, validate through GUI interactions, and preserve evidence.
- Encode strong rules around simulated clicks, screenshot cadence, source-backed benchmark work, and canonical-contract preservation.
- Include clear failure handling and plan-revision instructions.

Acceptance criteria:

- The skill exists on disk and is specific to AstraBridge orchestrator work.
- The skill requires GUI validation through simulated interaction rather than API-only flows.
- The skill covers both product code work and evidence preservation.
- Another agent can follow the skill without needing this chat history.

Status: not started

### 11. Run End-To-End Dogfood Against The Product Target

Goal: Validate that the benchmark-informed target is actually usable in the live product.

Main actions:

- Start from the visible product surface.
- Create or edit a representative graph, wire it, configure prompts and communication policy, run it in fixture mode, inspect outputs, and exercise one recovery path.
- Capture an end-to-end evidence pack.

Acceptance criteria:

- Evidence shows a full user path from authoring to inspection and recovery.
- The path is executed through visible controls with simulated clicks and typing.
- The evidence pack includes screenshots, run artifacts, validation notes, and any remaining usability debt.
- The dogfood path proves actual operator usability rather than inferred readiness.

Status: not started

### 12. Final Acceptance And Handoff

Goal: Close the benchmark-to-product slice with a durable, evidence-backed handoff.

Main actions:

- Summarize proven capabilities, unresolved gaps, and recommended next implementation slices.
- Run focused validation and a secret-safety pass on touched files and evidence.
- Update this plan so the next entry point is explicit.

Acceptance criteria:

- A final acceptance report exists under `PRIVATE/agent-graph-orchestrator-benchmark/final/<YYYYMMDD>/`.
- The report distinguishes benchmark conclusions, implemented product gains, blocked items, and deferred items.
- The plan is updated with the final completion state or exact next step.
- A future agent can resume without reconstructing prior discussion.

Status: not started

## Progress Log

### 2026-07-09 - Step 0

- Completed: Created the durable benchmark-and-product execution plan for AstraBridge Agent Graph orchestrator work.
- Files changed: `PLAN/AGENT_GRAPH_ORCHESTRATOR_BENCHMARK_AND_PRODUCT_EXECUTION_PLAN.md`
- Validation: Checked the plan shape against the durable handoff plan skill and aligned the step structure to the current AstraBridge Agent Graph objective: benchmark, target definition, shared code/GUI contract, subagent isolation, click-driven validation, and final handoff.
- Blockers: None.
- Next step: Step 1, Benchmark The Common Visual Agent Orchestrators.
