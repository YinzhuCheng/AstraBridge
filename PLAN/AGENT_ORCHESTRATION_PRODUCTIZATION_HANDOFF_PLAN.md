# Agent Orchestration Productization Handoff Plan

## Total Objective

Turn AstraBridge's early multi-agent task graph into a product-grade agent orchestration system that supports both GUI-first workflow authoring and code-first graph authoring, while letting the main agent safely design, inspect, validate, and execute bounded multi-agent workflows as a skill.

The intended product shape is not a generic clone of Dify, Flowise, Langflow, n8n, LangGraph Studio, AutoGen Studio, CrewAI, or Rivet. AstraBridge should use those systems as references, but focus on its own lane: provider-aware coding-agent orchestration with visible handoffs, typed communication contracts, reproducible evidence, rollback boundaries, and click-verified user experience.

## Deliverables

- A documented competitive reference matrix for visual agent/workflow orchestrators and the product patterns AstraBridge will adopt or reject.
- A canonical agent orchestration graph contract shared by GUI, code import/export, runtime execution, dry-run validation, and main-agent skill workflows.
- A code-first orchestration interface that can define, lint, dry-run, import, export, diff, and migrate agent graphs without creating a second runtime.
- A GUI-first orchestration workspace where users can add agents, connect handoffs, edit prompts, configure output schemas, configure communication formats, inspect runs, and recover from failures through visible controls.
- A main-agent orchestration skill that can propose, modify, validate, and operate bounded agent graphs without uncontrolled nesting.
- A preserved click-driven evidence pack for every user-facing milestone under `PRIVATE/agent-orchestration/productization/**`.
- A screenshot-driven UI quality review trail that catches layout anti-patterns such as card stacking, oversized fonts, low-semantic text, redundant labels, cramped inspectors, hidden controls, and unnecessary background frames.
- A maintainer runbook that tells future agents how to add orchestration features, validate them by simulated clicks, and preserve evidence without leaking secrets.

## Related Context Files

- `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_CLICK_DRIVEN_PRODUCTIZATION_PLAN.md`
- `PLAN/STEP17_GUI_USABILITY_CLICK_HANDOFF_PLAN.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SCOPE_AND_UX_PRINCIPLES.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SURFACE_MAP.md`
- `PLAN/AGENT_ORCHESTRATION_MAINTENANCE_RUNBOOK.md`
- `apps/astrabridge-desktop/src/types.ts`
- `apps/astrabridge-desktop/src/App.tsx`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
- `apps/astrabridge-desktop/src/styles.css`
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`

## External Reference Targets

Use primary documentation and public repositories as references. Do not copy implementation blindly.

- Dify: visual workflow, agent node, structured outputs, workflow-as-tool, observability.
  - https://github.com/langgenius/dify
  - https://docs.dify.ai/
- Flowise: visual agent builder, node registry, agentflow/chatflow separation, component packaging.
  - https://github.com/FlowiseAI/Flowise
  - https://docs.flowiseai.com/
- Langflow: visual authoring, API/MCP export, custom Python components, multi-agent orchestration.
  - https://github.com/langflow-ai/langflow
  - https://www.langflow.org/
- n8n: workflow automation UX, credentials separation, AI Agent node, templates.
  - https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/
- LangSmith/LangGraph Studio: graph visualization, prompt iteration, tracing, evaluation, time travel.
  - https://docs.langchain.com/langsmith/studio
- AutoGen Studio: declarative JSON specification, team builder, drag-and-drop, playground, message-flow view.
  - https://microsoft.github.io/autogen/dev/user-guide/autogenstudio-user-guide/index.html
  - https://www.microsoft.com/en-us/research/publication/autogen-studio-a-no-code-developer-tool-for-building-and-debugging-multi-agent-systems/
- CrewAI: code-first multi-agent abstraction, crews, flows, guardrails, memory, observability.
  - https://github.com/crewAIInc/crewAI
  - https://docs.crewai.com/
- Rivet: graph-as-YAML, visual prompt graph, versionable files, debugger, app embedding.
  - https://github.com/Ironclad/rivet
  - https://rivet.ironcladapp.com/

## Constraints And Attention Notes

1. This plan is a productization and architecture plan. Do not overwrite the completed Step 17 GUI usability plan or historical execution records.
2. There must be one canonical graph contract. GUI, code DSL, import/export, runtime, dry-run, and skill workflows must not diverge into separate incompatible graph engines.
3. UI-facing work is not complete until the changed path is operated in the real app through simulated clicks, typing, dragging, and screenshots. Unit tests and API checks are necessary but not sufficient.
4. Code-first orchestration must be reviewable and reversible: graph files should be diffable, schema-validated, dry-runnable, migratable, and rollback-friendly.
5. The main-agent orchestration skill must default to shallow orchestration. Prefer one supervisor layer plus workers and synthesizer/reviewer. Depth two requires explicit justification. Deeper nesting requires user approval and a recorded reason.
6. Graph execution must preserve safety boundaries: provider keys, bearer tokens, cookies, auth headers, vault material, and raw secret-bearing payloads must never be written to plan files, durable reports, screenshots, logs, or staged changes.
7. Preserve diagnostics, screenshots, raw validation reports, generated graph specs, migration reports, and dry-run outputs by default under `PRIVATE/**`. Do not clean them unless the user explicitly names target paths.
8. Do not use direct API calls as a substitute for proving user-facing flows. API calls are allowed for diagnosis after the visible user path has already been exercised or failed.
9. Every completed step must update this plan with files changed, validation run, preserved evidence path, blockers, and the exact next step.
10. If external reference behavior is used to justify a design decision, cite the source URL in the step evidence note or design artifact.
11. UI-facing steps must be driven from the product surface by simulated user actions. Agents must not instantiate graphs, start runs, cancel runs, approve gates, import files, export files, or mutate selected state by direct API/store calls when claiming that the GUI works.
12. Screenshot review is a required part of UI work. The implementing agent must inspect its own screenshots and explicitly record UI issues it sees, including card stacking, excessive visual containers, oversized typography, low-value text on the canvas, redundant metadata, unclear icon meanings, clipped controls, overflow, and wasted whitespace.
13. Future agents must treat simulated user interaction as the primary proof path for product work. If a step changes the visible app, the first validation attempt must be click-driven in the live product surface, not API-driven.
14. Screenshot capture is not optional "after-the-fact documentation". It is part of the implementation loop: inspect current UI, make a change, re-open the surface, click through the changed path, capture screenshots, critique the result, and only then decide whether the UI is acceptable.
15. Any agent that bypasses the visible product path by mutating store state, calling sidecar endpoints to advance UI state, or relying on hidden fixtures without first reproducing the flow by simulated clicks has not completed the step, even if the backend behavior is correct.
16. When the product is already running locally, the default UI proof path is the in-app browser with simulated clicks, typing, hovering, dragging, reload, and screenshot review. Headless or API-first validation is only supplemental.
17. For visible UI work, screenshots must be taken often enough to show the actual review loop: before change, after opening the target surface, after each major visible interaction, after each layout adjustment, and after reload or viewport verification.
18. If a screenshot still shows obvious UI debt such as card stacking, oversized fonts, redundant low-semantic text, cramped inspectors, unclear iconography, clipped content, or wasted canvas area, the agent must either fix it in the same step or record it explicitly as remaining debt with screenshot evidence.
19. When both a visible product path and an API/store shortcut exist, the visible product path is mandatory as the primary execution route. API/store access may explain failures afterward, but must not be used to fake the happy path.
20. Any agent claiming a UI flow works must be able to describe the exact click sequence, the screenshots captured during that sequence, and the UI problems noticed from those screenshots.
21. For AstraBridge productization work, the default proof environment is the running app in the in-app browser. Agents should assume they must navigate, click, drag, type, expand, collapse, scroll, reload, and re-open the real surface unless the step is explicitly backend-only.
22. "Works in the UI" means the changed path was exercised by visible interaction from the product surface. It does not mean the agent set state through sidecar endpoints, store patches, fixtures, console injection, or direct persistence writes and merely observed the result.
23. Screenshot cadence must be frequent enough to expose layout regressions early. At minimum, future agents must preserve the surface before the change, the entry path, each major interaction, each major layout adjustment, reload or re-open confirmation, and at least one constrained-width pass for visible UI work.
24. For GUI work, backend APIs are secondary evidence only. If an agent uses them, the evidence note must explicitly separate what was proven by simulated user interaction from what was diagnosed afterward by API or logs.
25. UI-facing steps must begin from the product surface and attempt the real user flow by simulated interaction before any mutating backend shortcut is considered.
26. If a visible flow can be performed by clicking, typing, dragging, hovering, expanding, collapsing, or reloading in the product, then sidecar API mutations, store patches, console injection, fixtures, or direct persistence writes are forbidden as primary proof.
27. Screenshot review is part of the implementation loop itself. Agents must inspect screenshots during the step and keep iterating until obvious clutter, oversized text, redundant low-semantic information, or detached controls are addressed or explicitly recorded as debt.
28. A step is incomplete if the agent cannot provide a replayable click path and screenshot trail for the claimed visible behavior, even when tests and backend traces pass.
29. "Simulated user interaction" means operating the visible product surface through browser or app input primitives such as click, double-click, type, drag, hover, scroll, resize, expand, collapse, and reload. It does not include mutating app state through `page.evaluate(...)`, devtools console injection, store patching, fixture preloading, localStorage/sessionStorage writes, hidden debug hooks, or sidecar endpoints to skip the visible path.
30. For UI-facing work, the implementing agent must preserve a screenshot trail dense enough to expose bad UI decisions early. The minimum set is: current surface before change, entry into the target surface, each major visible interaction, each major layout change, final persisted state after reload or reopen, and one constrained-width or alternate-viewport pass.
31. The screenshot review note must explicitly call out whether the current pass still shows card stacking, oversized fonts, low-semantic text consuming prime space, redundant information, detached controls, confusing iconography, unnecessary frames or rails, clipping, overlap, or wasted canvas area.
32. For visible product work, the first mutating validation attempt must happen from the running app surface, preferably the in-app browser tab that the user can also inspect. Agents must try the real click path before considering any API, fixture, store, or script shortcut.
33. If the visible path is broken, the agent must preserve the failing click sequence and screenshots first, then use lower-level diagnosis only to explain or repair the failure. Diagnosis is not acceptance evidence.
34. Screenshot review is part of the implementation loop itself, not a final packaging task. Agents must inspect screenshots after each major UI revision and keep iterating until the most obvious layout or density issues are fixed or explicitly recorded as debt.
35. When a UI pass still shows card stacking, oversized fonts, low-semantic text in prime space, redundant metadata, detached controls, unclear icons, unnecessary framing, clipped content, or wasted canvas area, the agent must either fix the issue in the same numbered step or record the issue with screenshot paths and severity.
36. For visible product work, the agent must default to operating the same in-app browser surface the user can inspect. Automation may assist, but it must drive that visible surface through user-like input rather than hidden state mutation.
37. Screenshot frequency should be biased high, not low. If there is doubt about whether a state transition, layout change, or interaction branch is obvious enough, preserve another screenshot and review it before moving on.
38. When a user-visible click path exists, future agents must treat it as the authoritative proof path even if backend endpoints, fixture loaders, or store mutations would reach the same state faster.
39. If a UI validation pass reveals avoidable visual debt such as card stacking, over-framing, oversized type, redundant helper text, detached controls, or wasted canvas area, the agent must continue iterating in the same numbered step until the visible issue is either fixed or explicitly logged with evidence and severity.
40. For visible product work, the default execution tool is simulated interaction in the running in-app browser surface the user can also inspect. Future agents must prefer visible click, type, drag, hover, scroll, resize, expand, collapse, and reload actions over any programmable shortcut.
41. Browser automation may help operate the product, but it must behave like a user. It may not use hidden store mutation, direct sidecar state writes, fixture preloads, console injection, or `page.evaluate(...)` state mutation to skip the visible path.
42. Screenshot review must happen continuously during implementation, not only after completion. Agents should capture, inspect, and critique screenshots often enough to catch card stacking, over-framing, oversized fonts, low-semantic text, redundancy, awkward iconography, and wasted canvas area before those issues spread across later revisions.
43. When the app is already open in the in-app browser, future agents must keep using that live visible surface as the primary workbench for UI-facing steps instead of treating it as a passive preview that is only checked at the end.
44. For UI-facing work, "simulate the product" means the implementing agent must personally drive the real visible controls through click, double-click, type, hover, drag, scroll, expand, collapse, resize, reload, reopen, and menu selection. It does not mean calling a backend API first and later taking a confirming screenshot.
45. If a state change could have been produced through visible interaction but was actually produced through an API, store patch, fixture preload, hidden debug hook, or script mutation, that state does not count as product proof and the step remains incomplete until reproduced from the visible surface.
46. Screenshot cadence should bias high rather than low. If there is any doubt about whether a layout change, state transition, or canvas interaction is obvious enough from the current evidence, the agent should capture another screenshot and review it before continuing.
47. The implementing agent must personally operate the product surface during validation. It is not enough for one agent to change code while another agent or script silently drives state through APIs and reports success.
48. When a visible operation can be performed through click, drag, hover, collapse, expand, scroll, reload, or typing, backend endpoints, store patches, fixture seeds, and console-driven state mutation are forbidden as the primary execution path for that operation.
49. Screenshot review must explicitly look for the concrete UI anti-patterns this project keeps hitting: card stacking, oversized fonts, low-semantic helper text occupying prime space, redundant metadata already visible elsewhere, unnecessary frames or rails, cramped inspectors, hidden canvas priority, and controls placed outside the object context where the user expects them.

## Evidence Convention

- Default artifact root: `PRIVATE/agent-orchestration/productization/<step-id>/<YYYYMMDD>/`
- Minimum evidence for UI-facing steps:
  - screenshot of the starting product surface before any mutating interaction,
  - screenshot before or during the key interaction,
  - screenshots at each major state transition, such as entry, add, edit, save, run, trace, reload, export, and failure,
  - screenshots after any meaningful canvas drag, panel expand/collapse, viewport change, or object selection change that affects what the user can see or act on,
- screenshot after the expected state change,
- screenshot after a reload, reopen, or fresh navigation pass proving the visible state persisted without hidden setup,
- screenshot from at least one constrained-width or alternate viewport pass for any layout-affecting work,
- screenshot after any meaningful hover-only or collapse/expand-only state when that state changes discoverability, density, or canvas priority,
- short validation note listing clicked controls, typed values, observed result, and rough edges,
- short interaction transcript listing the exact click, type, drag, hover, expand/collapse, and reload sequence in order,
- an explicit statement of which interactions were proven from the visible product surface and whether any API/store/backend inspection happened only afterward for diagnosis,
- an explicit statement that the primary mutating path was attempted from the visible product surface before any backend shortcut was considered,
- an explicit statement that no hidden state mutation such as `page.evaluate(...)`, store patching, fixture preload, direct sidecar write, or direct persistence write was used as acceptance evidence,
- an explicit statement that the in-app browser remained the primary proof surface whenever the product was already available there locally,
- UI quality checklist result covering card stacking, font size, semantic density, redundancy, canvas space, inspector density, tooltip discoverability, clipped text, and visual noise,
- intermediate screenshot-review notes describing what the implementing agent noticed and corrected during the step rather than only a final-state summary,
- an explicit note naming at least one UI choice that was rejected or simplified because screenshots showed it was low-value, over-framed, redundant, or visually noisy,
- preserved failure screenshot or trace if the first attempt exposed a defect.
- Minimum evidence for code-first/runtime steps:
  - schema or DSL examples,
  - validation report,
  - dry-run or lint output,
  - round-trip import/export result where applicable,
  - focused unit/integration test output.
- Evidence must be secret-free and understandable without reading chat history.

## Mandatory GUI Operation And UI Quality Gate

These rules apply to every UI-facing step and cannot be replaced by API proof.

1. Start from the visible app surface. Use the in-app browser or Playwright to click visible navigation, buttons, canvas controls, palettes, inspectors, menus, dialogs, and file controls.
2. Use direct API calls only for read-only diagnosis after the user-visible path has already been attempted, or for non-UI backend validation that is explicitly outside the step's GUI acceptance criteria.
3. Do not mark a UI-facing step complete from unit tests, DOM inspection, network responses, or sidecar API success alone.
4. Do not use direct API/store mutations to create, select, connect, run, cancel, approve, import, export, or persist graph state when the step is supposed to prove the GUI. Those actions must be performed by visible clicks, typing, dragging, and menu use in the product.
5. Do not use `page.evaluate(...)`, console injection, devtools snippets, hidden fixture toggles, direct storage writes, or internal state mutation as a substitute for clicking or typing through the visible UI. Automation is allowed only when it drives the same visible controls a user would use.
6. A UI step must include at least one "fresh-open" verification pass after edits: reopen or reload the surface, navigate back in through the visible UI, and confirm the interaction still works without hidden setup.
7. Capture screenshots frequently:
   - initial state before editing,
   - after opening the target workspace,
   - after every meaningful visible state change,
   - before and after a layout or style fix,
   - after reload or persistence checks,
   - after narrow-width or alternate viewport checks,
   - at every failure or confusing state before fixing it.
8. Each screenshot set must include a short human-readable review note. The note must say whether the UI still suffers from:
   - card stacking or nested-card clutter,
   - unnecessary background panels or framed containers,
   - font sizes that are too large for tool/editor surfaces,
   - low-semantic labels, metadata, or explanatory text taking primary space,
   - repeated information already shown elsewhere,
   - controls placed outside the canvas context when they belong inside it,
   - unclear icons without tooltips,
   - clipped text, overflow, or overlapping elements,
   - cramped sidebars or inspectors,
   - canvas space not being prioritized.
9. If a screenshot shows one of those issues, the agent must either fix it in the same step or record it as a named backlog item with severity and screenshot path. Silent acceptance is not allowed.
10. When a UI step claims "user-friendly", the claim must be backed by screenshot comparison and a click recipe that another agent can repeat without hidden state injection.
11. Agents should prefer visible simulated interaction even while debugging. If a UI bug blocks progress, first preserve the failing screenshots and click path, then use lower-level diagnostics only to explain the failure.
12. The preferred validation loop for UI work is:
   - open the real surface,
   - simulate the user interaction through visible controls,
   - capture screenshots,
   - critique the screenshots,
   - change the implementation,
   - reopen or reload and repeat.
   Skipping that loop in favor of direct API mutation is not acceptable proof for a GUI step.
13. When a click path exists, agents must use it even if an internal API would be faster. Faster is not better here; user-visible proof is the product requirement.
14. If a step changes visible layout, the screenshot review note must name at least one thing that improved and any remaining UI debt seen directly in the screenshots.
15. For any visible flow that mutates product state, the evidence note must include the exact click sequence in order: entry path, clicked controls, typed values, expanded or collapsed sections, drag actions if any, and the reload or reopen pass.
16. Each UI-facing validation pass must preserve enough screenshots to reconstruct the review loop: pre-change surface, target surface opened, each major visible interaction, each major layout revision, final persisted state after reload or reopen, and constrained-width or alternate-viewport verification when the change affects layout.
17. The implementing agent must explicitly inspect those screenshots for at least these failure modes:
   - card stacking or nested-card clutter,
   - fonts oversized for a tool or editor surface,
   - low-semantic helper text taking primary space,
   - repeated information already shown elsewhere,
   - controls detached from the canvas or object they act on,
   - unclear icons that should be replaced or backed by hover tooltip,
   - unnecessary borders, frames, rails, dividers, or background panels,
   - clipped labels, overlapping content, or wasted whitespace.
18. A screenshot set that still shows one of those issues without either a fix or an explicit debt note is not sufficient evidence for completion.
19. When the running app is already available in the in-app browser, the implementing agent must use that surface as the primary operation path and keep it open during the work so screenshots and visible interaction stay coupled to the real product.
20. If the visible click path fails, the agent must first preserve the failing screenshots and interaction sequence, then diagnose. Repairing the problem through API or hidden state mutation without first preserving the visible failure does not satisfy the GUI gate.
21. If the product is already open in the in-app browser, the agent must keep using that same visible surface as the main validation path instead of switching to backend shortcuts for convenience.
22. Simulated interaction must stay user-like: visible clicks, typing, dragging, hovering, scrolling, expanding, collapsing, and reload/reopen passes from the real product surface.
23. Screenshot review must happen continuously during the step. If an intermediate screenshot still shows card stacking, over-framing, oversized text, low-semantic clutter, cramped inspectors, awkward controls, or wasted canvas space, the step is not ready to close until that issue is fixed or explicitly logged as debt.
24. The default execution loop for visible work is: open the live product surface, operate it by simulated interaction, capture screenshots, inspect those screenshots for UI debt, adjust implementation, reopen or reload, and repeat. Reversing that order by using backend mutation first is not acceptable.
25. The implementing agent must personally perform the visible interaction sequence and preserve the exact click path. "The UI works" is not established by code inspection, API success, or another agent's claim.
26. If a user-visible operation has both a product-surface path and an API path, the product-surface path must be exercised first and treated as authoritative. The API path may only explain failures afterward.
27. Hover, collapse, expand, tooltip, and constrained-width states are part of the GUI contract when they affect density or discoverability. Agents must exercise and screenshot those states instead of validating only the default wide-open view.
28. For visible product work, the implementing agent must actively drive the app by simulated user actions rather than treat the app as a passive preview. The minimum expected interaction vocabulary is click, double-click, type, drag, hover, scroll, expand, collapse, resize, reopen, and reload, used against the real visible controls.
29. API calls, sidecar endpoints, store patches, fixture seeds, browser console injection, `page.evaluate(...)`, or direct persistence writes are forbidden as the primary mutation path for any GUI claim. If one of them is temporarily used for diagnosis, the same result must still be reproduced afterward by visible interaction before the step can pass.
30. Screenshot review notes must say what the agent removed, collapsed, simplified, or pushed behind tooltip/expansion because the screenshot showed it was low-semantic, redundant, over-framed, or crowding the main workspace.

## Mandatory UI Review Checklist

Every UI-facing validation note under this plan must include an explicit pass/fail checklist for the current screenshot set. At minimum, review:

1. card stacking or nested-card clutter,
2. oversized fonts for an editor, inspector, or canvas tool surface,
3. low-semantic helper text or metadata occupying primary space,
4. repeated information already shown elsewhere,
5. controls visually detached from the object or canvas area they affect,
6. confusing icons that need replacement or hover tooltip backup,
7. unnecessary frames, background cards, rails, vertical dividers, or decorative containers,
8. clipped labels, overflow, overlap, or hidden controls,
9. cramped sidebars or inspectors,
10. insufficient canvas or main-workspace priority.

If any item fails, the agent must either fix it within the same numbered step or record it as explicit remaining debt with screenshot paths and severity.

## Mandatory Click-Driven Review Loop

This is the default operating procedure for future agents working on visible AstraBridge product surfaces.

1. Enter through the real product entry point, preferably the in-app browser.
2. Use simulated clicks, typing, hovering, dragging, scrolling, expand/collapse actions, and reloads to reach the changed state.
3. Capture screenshots at minimum:
   - before the change,
   - after entering the target surface,
   - after every major visible interaction,
   - after each layout/style adjustment,
   - after reload or persistence verification,
   - after narrow-width or alternate viewport verification,
   - at any failure or confusing state.
4. Review the screenshots before deciding the step is acceptable.
5. Explicitly call out UI debt seen in those screenshots, especially:
   - card stacking or nested-card clutter,
   - oversized fonts,
   - low-semantic text taking prime space,
   - redundant information already shown elsewhere,
   - unnecessary frames, background cards, dividers, or decorative rails,
   - unclear icons that need tooltip backup,
   - controls placed outside the visual context where the user needs them,
   - cramped inspectors, clipped labels, overflow, or wasted canvas space.
6. Only after the click path and screenshot path are preserved may the agent use API/store/backend inspection to diagnose why a visible interaction failed.
7. A step is not complete if the only proof is tests, DOM inspection, API responses, sidecar endpoints, or direct state mutation.
8. When possible, the screenshot set should make the review loop legible to another agent: open surface, perform visible action, inspect result, adjust, reopen, and confirm.
9. When the app is already running, the default proof route is the in-app browser tab. If the agent uses Playwright or another automation layer, it must still drive the real product surface by simulated user interaction rather than internal APIs.
10. Another agent should be able to replay the claimed UI flow from the evidence note and screenshots alone without depending on hidden state injection.
11. Playwright or browser automation may select elements and dispatch real input, but it must not mutate application state through in-page script execution when the purpose is to prove the GUI.
12. If an agent temporarily uses a mutating backend or store shortcut during debugging, that shortcut does not count toward acceptance. The same visible state must still be reproduced afterward from the product surface by simulated clicks, typing, dragging, scrolling, expand/collapse, and reload.
13. The preferred proof environment is the in-app browser when the app is already running there. Future agents should assume they must operate the same surface the user can see unless the step is explicitly backend-only.
14. Screenshot cadence must be dense enough to catch bad UI decisions before they spread. For layout-affecting work, agents should capture before-change, after-open, after-interaction, after-layout-adjustment, after-reload, and constrained-width screenshots in the same step rather than waiting for the end.
15. If the visible UI still reads as card-heavy, text-heavy, over-framed, cramped, or visually noisy in the preserved screenshots, that is a validation failure until fixed or explicitly recorded as debt in the current step note.
16. Future agents should assume that any claim of "user-friendly" or "GUI-complete" will be judged against the screenshot trail, not against backend correctness alone. If the screenshots still show obvious clutter, awkward density, detached controls, or oversized text, the step is not done.
17. Future agents should assume the reviewer will ask whether the product was actually clicked through by the implementing agent and whether the screenshots were taken often enough to expose bad UI choices early. The evidence should answer both questions directly.
18. Future agents should assume the reviewer will also ask whether they operated the same visible in-app browser surface the user could inspect, or instead jumped to backend/state shortcuts. The evidence note must answer that directly.
19. Future agents should preserve enough screenshots to make the critique loop obvious: enter, click, observe, criticize, adjust, reopen, and re-check. A pile of final-state screenshots without intermediate critique is not enough.
20. For GUI work, every acceptance note should be replayable by another agent using only the written click sequence and the preserved screenshots, without hidden setup or API-side preconditioning.

## Adjustment Policy

Agents may reasonably adjust substeps, filenames, implementation details, commands, viewport sizes, selectors, or sequencing when repository facts require it. Such adjustments must not change the total objective, remove click-driven validation, remove code-first orchestration, weaken safety gates, or replace substantive product work with cosmetic cleanup. If a core objective becomes infeasible, record the blocker, evidence, attempted paths, and a substitute path that preserves the original intent.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks for more.
2. Each turn must start by reading this plan and the files relevant to the current step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all acceptance criteria are satisfied.
5. UI-facing steps must operate the real app in the in-app browser or Playwright by visible user actions: click, type, drag, inspect, reload, screenshot, and visually review screenshots before claiming completion.
6. Code/API checks may supplement UI proof, but must not replace it. If API calls are used for diagnosis, the progress log must state which actions were still proven through visible clicks.
7. If a step changes persisted graph data or migration behavior, preserve before/after examples and a rollback note.
8. If a step changes agent execution, preserve a dry-run report before any paid or stateful live execution.
9. Each turn must end with a precise handoff: completed work, files changed, validation run, evidence path, blockers, and exact next step.
10. For UI-facing steps, the progress log must explicitly say:
   - which interactions were performed by simulated clicks or drags,
   - which screenshots were reviewed by the implementing agent,
   - what UI issues were observed from those screenshots,
   - whether any API/store access was used only for diagnosis after the click path failed.
11. For plan execution that touches visible UI, agents should think in this order:
   - click the product,
   - screenshot the result,
   - critique the UI,
   - modify the code,
   - reopen and click again,
   - use API/store diagnostics only if the visible flow still fails.
12. If a future step includes creation, editing, wiring, running, import, export, template insertion, approval, retry, or navigation behavior that a user can trigger from the GUI, the acceptance proof must come from simulated product interaction first.
13. For UI steps, validation is not only behavioral. The agent must also review whether the surface is visually usable, with specific attention to clutter, typography scale, semantic density, and whether the canvas or main work surface is getting enough space.
14. If backend calls are used for diagnosis, the progress log must clearly separate what was proven by the visible click path from what was learned afterward through backend inspection.
15. For any UI-facing step, the progress log must also state:
   - whether the agent used the in-app browser, Playwright, or both,
   - whether any in-page script execution was limited to read-only inspection,
   - which screenshot paths correspond to before-state, interaction states, reload confirmation, and constrained-width review,
   - which UI issues were fixed during the step versus left as explicit debt.
16. Any mutating API, sidecar endpoint, store patch, fixture preload, or script shortcut used during debugging must be disclosed explicitly in the progress log and must be labeled as non-acceptance evidence unless the agent later reproduces the same user-visible result through the live product surface by simulated interaction.
17. For visible UI work, the progress log must also state whether the first successful mutating path was completed entirely through simulated interaction from the product surface. If not, the step is incomplete.
18. For visible UI work, agents must preserve enough screenshots to show their review loop in action, not only the final state: initial surface, target surface opened, major interaction states, major layout revisions, persistence check, and at least one constrained-width or alternate-viewport pass when layout is affected.
19. For visible UI work, agents must explicitly say whether they inspected those screenshots during implementation and what specific UI defects they looked for before deciding the step was acceptable.
20. For visible UI work, agents must explicitly state whether the in-app browser was used as the primary proof surface and whether any automation acted only through visible input primitives.
21. Any future agent that relies on backend mutation or hidden browser-state mutation to advance a user-facing flow must treat that work as diagnosis only and still reproduce the same result afterward through visible simulated interaction before claiming completion.
22. For visible UI work, the progress log must explicitly state whether the product stayed open in the in-app browser during iteration and whether each major UI change was rechecked there by visible interaction plus screenshots before moving on.
23. For visible UI work, the progress log must explicitly name which screenshot sets were used for intermediate critique, not only which screenshots showed the final passing state.
24. For visible UI work, the progress log must explicitly state that the implementing agent personally operated the product through simulated interaction rather than depending on API-side state mutation for the happy path.
25. For visible UI work, the progress log must explicitly state whether screenshot cadence was sufficient to catch intermediate layout or density problems early, and if not, what additional screenshot passes were added before closing the step.
26. For visible UI work, the progress log must explicitly state that the implementing agent personally clicked through the product surface and did not outsource the acceptance path to hidden scripts, backend setup, or another agent's prior state mutation.
27. For visible UI work, the progress log must explicitly list which hover, collapse/expand, narrow-width, or other density-sensitive states were exercised because those states often reveal the project's recurring UI problems.
28. For visible UI work, the progress log must explicitly state that the first primary mutation attempt happened from the visible product surface by simulated interaction, and must name any later API/store/backend access as diagnosis-only evidence.
29. For visible UI work, the progress log must explicitly list which screenshots were used for intermediate critique and what concrete UI simplifications or removals were made because those screenshots exposed clutter, redundancy, oversized type, awkward framing, or weak workspace priority.
30. For visible UI work, the progress log must explicitly say whether the same in-app browser surface remained the primary workbench throughout the step and whether all acceptance claims were reproduced there after code changes.

## Current Progress

- Current status: Completed
- Completed steps: Step 0, Create Durable Plan; Step 1, Baseline Current Orchestration Surface; Step 2, Build Competitive Pattern Matrix; Step 3, Define Canonical Orchestration Graph Contract; Step 4, Implement Schema Validation And Migration Skeleton; Step 5, Add Code-First Graph File Format; Step 6, Add Graph Lint, Dry-Run, And Diff Commands; Step 7, Implement Import And Export Round Trip In The App; Step 8, Redesign Canvas Information Architecture; Step 9, Add Agent Palette And Node Creation UX; Step 10, Productize Node Inspector For Agent Configuration; Step 11, Productize Edge Wiring And Communication Contracts; Step 12, Add Prompt, Schema, And Contract Editors; Step 13, Add Runtime Trace And Debugger Surface; Step 14, Add Graph Templates And Example Library; Step 15, Create Main Agent Orchestration Skill; Step 16, Add Safety, Versioning, And Rollback Boundaries; Step 17, Add End-To-End Click-Driven Dogfood Scenarios; Step 18, Publish Maintainer Runbook And Product Boundary
- Current step: None
- Next step: Follow-on maintenance only; numbered plan complete
- Last updated: 2026-07-09

## Execution Steps

### 0. Create Durable Plan

Goal: Create this persistent handoff plan and make the next entry point explicit.

Main actions:

- Define the total productization objective.
- Record constraints, evidence convention, adjustment policy, execution rules, steps, and acceptance criteria.
- Set the first implementation step around a current-state baseline rather than immediate feature edits.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, deliverables, constraints, adjustment policy, current progress, numbered steps, acceptance criteria, and progress log.
- The plan explicitly requires both GUI click validation and code-first orchestration.
- The plan includes a mandatory GUI operation and screenshot-based UI quality gate.
- The next step is clearly identified.

Status: completed

### 1. Baseline Current Orchestration Surface

Goal: Produce a current-state map of AstraBridge's existing task graph, runtime, UI, and evidence flows before expanding the feature.

Main actions:

- Read the related context files named in this plan.
- Map existing `TaskGraphDefinition`, node, edge, context policy, worker binding, run ref, dry-run, artifact, and UI inspector behavior.
- Open the running app and capture the current task graph surface through simulated user navigation.
- Record what already works, what is prototype-only, and what conflicts with the target orchestration model.

Acceptance criteria:

- A baseline note exists under the Step 1 evidence root.
- Screenshots are preserved for the visible navigation path into the graph workspace, the initial canvas, at least one inspector/palette state, and at least one narrow or constrained viewport.
- The note lists current graph schema fields, current GUI affordances, current runtime support, and known gaps.
- The note includes the UI quality checklist and names any visible card stacking, oversized text, low-semantic display text, redundant metadata, clipped controls, or wasted canvas space with screenshot paths.
- No product code is changed in this step unless a blocking app entry issue prevents baseline capture; if so, the blocker and fix must be recorded.

Status: completed

### 2. Build Competitive Pattern Matrix

Goal: Convert external orchestrator research into concrete design inputs for AstraBridge.

Main actions:

- Review the external reference targets using official docs and public repos.
- Extract patterns for node palette, graph storage format, prompt editing, structured outputs, code export, debugging, templates, credentials safety, and runtime observability.
- Mark each pattern as `adopt`, `adapt`, `defer`, or `reject` for AstraBridge.
- Avoid copying code unless licenses and scope are explicitly reviewed.

Acceptance criteria:

- A matrix artifact exists under the Step 2 evidence root.
- Every referenced product has source URLs and a concise relevance note.
- The matrix identifies at least five product patterns AstraBridge should adopt or adapt.
- The matrix identifies at least three patterns AstraBridge should avoid because they conflict with local-first safety, coding-agent workflows, or product scope.

Status: completed

### 3. Define Canonical Orchestration Graph Contract

Goal: Define the single graph contract that GUI, code, runtime, and skill workflows will share.

Main actions:

- Design a versioned `AgentOrchestrationGraph` contract that extends or cleanly wraps the existing `TaskGraphDefinition`.
- Include node roles, provider/model routing, prompt templates, tools, permissions, context policy, memory policy, output schemas, artifact contracts, edge handoff contracts, edge communication formats, validation gates, run policy, and UI layout metadata.
- Define migration rules from current task graphs.
- Decide where the canonical schema lives and how generated frontend/backend types stay in sync.

Acceptance criteria:

- A contract design document exists under `PLAN/**` or `docs/**`.
- The design explicitly states whether it extends current `TaskGraphDefinition` or introduces a wrapper that compiles to it.
- The design includes example graph JSON/YAML for at least two workflows.
- The design includes compatibility and migration notes for existing graph definitions.
- No runtime behavior is changed yet unless the user explicitly asks to combine design and implementation.

Status: completed

### 4. Implement Schema Validation And Migration Skeleton

Goal: Make orchestration graph definitions machine-checkable before adding GUI and DSL features.

Main actions:

- Add shared validation for graph version, node ids, edge ids, provider/model references, prompt template references, output schemas, communication contracts, permissions, and graph depth limits.
- Add migration stubs for old graph versions.
- Add focused tests for valid graphs, invalid graphs, same-node edges, cycles where disallowed, missing prompts, missing output schema references, unsafe permissions, and excessive nesting.
- Preserve validation reports.

Acceptance criteria:

- Validation code and tests exist.
- Invalid examples fail with actionable error messages.
- Existing current-source graph fixtures still validate or have documented migration warnings.
- Local test commands pass and are recorded in the progress log.

Status: completed

### 5. Add Code-First Graph File Format

Goal: Let users and agents define orchestration graphs as reviewable files.

Main actions:

- Choose the first graph file format, preferably YAML or JSON with explicit schema version.
- Add example graph files for common workflows.
- Add parser and serializer paths that compile to the canonical graph contract.
- Preserve formatting enough for human review where feasible.

Acceptance criteria:

- A graph file can be parsed into the canonical contract.
- The same graph can be serialized back without losing required semantic fields.
- Example files cover at least `code_fix_review`, `provider_update_smoke`, and `fanout_research_synthesis`.
- Parser tests and serializer tests pass.

Status: completed

### 6. Add Graph Lint, Dry-Run, And Diff Commands

Goal: Make code-first graphs safe to edit before they reach runtime execution.

Main actions:

- Add a local lint or validation entry point for graph files.
- Add dry-run reporting that checks node readiness, edge contracts, output schemas, permissions, provider availability, context budget hints, and depth limits.
- Add a graph diff view or report that highlights semantic changes between two graph files or graph versions.
- Preserve sample command outputs under the evidence root.

Acceptance criteria:

- A future agent can run one documented command to lint a graph file.
- A future agent can run one documented command to dry-run a graph file without live provider calls.
- A future agent can compare two graph definitions and see node, edge, prompt, schema, and permission changes.
- Tests and sample reports are preserved.

Status: completed

### 7. Implement Import And Export Round Trip In The App

Goal: Bridge GUI and code-first workflows without creating two sources of truth.

Main actions:

- Add import from graph file into the app through a visible control or documented local path.
- Add export from current graph to the chosen graph file format.
- Preserve graph id, version, prompts, schemas, layout, and edge policies through round-trip.
- Use simulated clicks to import, inspect, export, reload, and compare.
- Preserve screenshots for the full visible round-trip and record any UI friction seen while operating the controls.

Acceptance criteria:

- A simulated-click flow imports a graph and shows it on the canvas.
- A simulated-click flow exports the graph and validates the exported file.
- Round-trip comparison shows no loss of required semantic fields.
- Import, inspect, export, reload, and compare actions are all initiated through visible product controls, not direct API calls.
- The evidence note contains the exact click path and screenshot review findings, including any remaining UI rough edges.
- Screenshots for every major state transition, exported files, UI quality checklist, and validation reports are preserved under the Step 7 evidence root.

Status: completed

### 8. Redesign Canvas Information Architecture

Goal: Make the orchestration workspace canvas-first and user-friendly.

Main actions:

- Move nonessential text into collapsible panels, inspectors, or hover tooltips.
- Keep the main canvas spacious, with compact node cards and icon-forward affordances.
- Collapse side rails to icon-only by default where appropriate.
- Move primary graph actions into the canvas toolbar.
- Remove unnecessary background cards and nested card layouts where they do not carry meaning.
- Drive each redesign pass through visible interaction in the running product and inspect screenshots before deciding the layout is acceptable.

Acceptance criteria:

- The canvas is the dominant visible surface at desktop width.
- Collapsed rails give meaningful space back to the canvas.
- Required labels and actions remain discoverable through tooltips or inspector panels.
- Simulated-click screenshots prove desktop and narrow-width behavior before and after the redesign.
- Screenshot review shows no unresolved blocker-level card stacking, nested-card clutter, oversized typography, low-semantic text occupying primary canvas space, or redundant metadata on the canvas.
- The evidence note explicitly records what the implementing agent saw in the screenshots and why the revised layout is better for a real user.
- UI tests and build pass.

Status: completed

### 9. Add Agent Palette And Node Creation UX

Goal: Let users add common agent types without editing raw data.

Main actions:

- Add a compact palette for common agent roles such as supervisor, worker, coder, reviewer, validator, researcher, extractor, synthesizer, planner, gate, and custom.
- Use role icons and short labels; show detailed behavior on hover or in the inspector.
- Support click-to-add and drag-to-add where feasible.
- Ensure new nodes get safe defaults and visible validation warnings when incomplete.
- Validate palette ergonomics by simulated clicks and screenshot review rather than assuming the compact layout is usable.

Acceptance criteria:

- A simulated-click flow adds at least three agent nodes from the palette.
- Added nodes appear on the canvas with stable layout and role icons.
- Custom role fallback uses a default icon and remains editable.
- Palette open, node add, node select, hover tooltip, and post-reload screenshots are preserved.
- The validation note records the exact click or drag path used to open the palette, add nodes, inspect them, and confirm persistence after re-open or reload.
- The UI quality note confirms role icons are understandable, labels are compact, and palette/sidebar content does not crowd the canvas.
- Nodes are created by visible canvas or palette interaction, not by fixture injection or hidden state mutation.
- Any API/store inspection is documented as secondary diagnosis only and is not the primary proof for node creation UX.

Status: completed

### 10. Productize Node Inspector For Agent Configuration

Goal: Let users configure an agent's behavior without editing JSON.

Main actions:

- Add or refine controls for agent role, display name, provider, model, reasoning setting, tool permissions, context policy, memory policy, prompt template, prompt variables, and output schema.
- Add prompt preview using selected variables.
- Add validation messages for missing provider/model, invalid prompt variables, unsafe tools, and missing output schema where required.
- Preserve edited values after reload.
- Verify the inspector through repeated click-open, edit, collapse, reload, and screenshot review cycles so dense controls do not regress usability.

Acceptance criteria:

- A simulated-click flow edits a node prompt template, provider/model, and output schema.
- Invalid values produce visible actionable errors before save.
- Saved values survive reload and export.
- Screenshots are preserved for selected node, prompt edit, schema edit, validation error, save success, reload, and exported graph check.
- The validation note records the exact click, type, collapse, reopen, and reload path used to exercise the inspector.
- The UI quality note confirms inspector controls are dense but readable, text is not clipped, and low-semantic helper text is hidden behind tooltips or collapsible help.
- The evidence note clearly distinguishes user-visible edit actions from any backend-only validation commands.
- Component tests, relevant integration tests, and app build pass.

Status: completed

### 11. Productize Edge Wiring And Communication Contracts

Goal: Make agent-to-agent communication explicit, typed, and inspectable.

Main actions:

- Support visible edge creation by dragging or click-selecting source and target nodes.
- Add edge type icons for context handoff, artifact handoff, approval dependency, fan-out, fan-in, review gate, and custom.
- Add inspector controls for history mode, artifact inclusion, summary strategy, private-memory exclusion, resource refs, required input schema, produced output schema, and handoff message template.
- Show concise edge information on hover, not as persistent clutter.
- Validate that edge affordances are understandable from the live UI by simulated interaction and screenshot critique, not only from implementation intent.

Acceptance criteria:

- A simulated-click flow creates at least two edge types.
- An edge communication contract can be edited and saved.
- Invalid contracts are blocked with visible error messages.
- Saved edge contracts survive reload, export, and dry-run.
- Screenshots are preserved for edge creation, edge hover, edge inspector, invalid contract, saved contract, reload, and dry-run.
- The validation note records the exact visible edge-creation sequence, including how the source, target, and contract editor were operated by simulated interaction.
- The UI quality note confirms edge metadata is icon-forward, hover-revealed where appropriate, and does not clutter the canvas with persistent low-value text.
- Edge creation and editing are proven through visible interaction on the canvas or inspector, not by preloading edge objects through API/store mutations.

Status: completed

### 12. Add Prompt, Schema, And Contract Editors

Goal: Make orchestration precise enough for real multi-agent work.

Main actions:

- Add focused editors for prompt templates, JSON schemas, artifact contracts, and handoff message formats.
- Provide variable insertion or autocomplete for known upstream outputs and artifacts.
- Add preview payload generation for a selected node or edge.
- Keep the editor compact and out of the main canvas until selected.
- Exercise each editor by visible clicks and typing in the running app, then inspect screenshots to ensure the editor does not bury the canvas or flood the screen with low-value text.

Acceptance criteria:

- A simulated-click flow edits a prompt template and inserts an upstream variable.
- A simulated-click flow imports or edits a JSON schema and sees validation feedback.
- Preview payload clearly shows what will be sent to the downstream agent.
- Saved prompt/schema/contract artifacts are exported with the graph and validated by dry-run.
- Screenshots are preserved for editor open, variable insertion, schema validation, preview payload, save, and exported graph validation.
- The validation note records the exact click-and-type path for opening the editor, changing content, previewing the payload, and confirming the saved state after re-open or reload.
- The UI quality note confirms editors appear only when selected, do not bury the canvas, and avoid oversized fonts or redundant explanatory copy.
- The evidence note states which parts were exercised by visible typing, clicks, and selection changes in the app.

Status: completed

### 13. Add Runtime Trace And Debugger Surface

Goal: Let users understand what happened during a graph run without reading raw logs.

Main actions:

- Add a run/debug panel with node status, message flow, tool calls, token/latency where available, artifacts, warnings, failures, and approvals.
- Support selecting a timeline event to highlight the related node or edge.
- Add replay or retry affordances where runtime supports it.
- Preserve run diagnostics and artifact links.
- Prove debugger usability by operating it through visible clicks in the running app and reviewing screenshots for density, clarity, and noise.
- Start from the visible product surface first; only use backend inspection after the click-driven path is preserved if the debugger flow fails.

Acceptance criteria:

- A simulated-click flow runs a dry-run or fixture, opens the trace panel, selects an event, and opens an artifact.
- The selected event visibly maps back to a node or edge.
- Failure states show what failed and where evidence is stored.
- Screenshots are preserved for run start, running state, selected trace event, highlighted node or edge, artifact open, failure or warning state if present, and reload persistence.
- The validation note records the exact click path used to start the run, open the trace/debugger, inspect an event, inspect an artifact, and return to the graph context.
- The UI quality note confirms timeline rows are compact, semantic, and not dominated by repeated metadata or unnecessary cards.
- The run, trace navigation, and artifact inspection are all initiated through visible controls in the app.
- The evidence note explicitly separates what was proven by simulated clicks in the app from any later API/log diagnosis.

Status: completed

### 14. Add Graph Templates And Example Library

Goal: Give users useful starting points instead of a blank canvas.

Main actions:

- Add curated templates for code fix/test/review, provider update/smoke/gate, multimodal capability adapter, fan-out research/fan-in synthesis, document extract/analyze/report, and custom blank graph.
- Keep templates editable after instantiation.
- Store templates in a format compatible with the code-first graph contract.
- Add screenshots and short notes for each template.
- Validate template discoverability and instantiation through visible clicks and screenshot review so the template surface does not become another card-heavy reading exercise.
- Require template selection, preview, instantiation, and follow-on edits to be exercised from the visible product surface before any direct file or API shortcut is used.
- Keep the in-app browser open during the step and use it as the primary proof surface for template discovery, preview, insertion, follow-on edit, reload, and constrained-width review.

Acceptance criteria:

- At least five templates instantiate through visible UI.
- Template files validate through the code-first lint command.
- A simulated-click flow instantiates at least three templates and verifies node/edge defaults.
- Template list, template hover or detail, instantiation, resulting canvas, inspector defaults, and reload screenshots are preserved.
- The preserved screenshot trail is dense enough to reconstruct the review loop: graph open, template rail expand, template preview/detail, instantiate, resulting canvas, follow-on edit, reload or reopen, and at least one constrained-width pass.
- The validation note records the exact click path for opening the library, previewing a template, instantiating it, editing it, and confirming the result after re-open or reload.
- The UI quality note confirms templates do not create card-heavy sidebars, duplicate information already visible on the canvas, or force excessive reading before use.
- Template instantiation is proven by visible clicks from the template surface, not by loading graph JSON behind the scenes.
- The evidence note states that screenshots were reviewed during implementation and records any remaining layout debt or interaction friction seen directly in those screenshots.
- The evidence note explicitly states that the in-app browser was the primary proof surface and that no hidden state mutation, direct sidecar write, or `page.evaluate(...)` state mutation was used as acceptance evidence.

Status: completed

### 15. Create Main Agent Orchestration Skill

Goal: Teach the main agent when and how to design, modify, validate, and operate orchestration graphs.

Main actions:

- Create or update a Codex skill for AstraBridge agent orchestration.
- Include decision rules for when multi-agent orchestration is justified and when a single agent is better.
- Include graph-depth limits, safety gates, permission rules, prompt/output schema conventions, dry-run requirements, and click-validation requirements.
- Include examples that generate or modify graph files through the code-first interface.
- Teach the skill to treat simulated product interaction and screenshot critique as mandatory for visible UI changes, instead of treating API mutation as equivalent proof.
- Teach the skill to prefer the in-app browser product surface for local UI verification, with screenshots captured before and after each major interaction or layout revision.
- Teach the skill to require agents to keep operating the visible product surface until obvious UI debt seen in screenshots is either fixed or explicitly logged, rather than stopping at backend correctness.

Acceptance criteria:

- Skill files exist in the appropriate local skill location or repository-managed skill package, as chosen by the implementation agent.
- The skill instructs agents to use canonical graph files and validation commands instead of ad hoc runtime mutations.
- The skill requires user approval for deep nesting, risky permissions, or live provider execution.
- A dry-run example proves the skill can produce a valid graph without leaking secrets.
- The validation note records which parts of the user-facing workflow were still proven from the running product surface by simulated interaction and which parts were backend or skill validation only.
- The skill guidance explicitly forbids using direct API/store mutation as the primary proof path for visible product work when a click path exists.
- The skill guidance explicitly requires dense screenshot capture and screenshot critique during implementation, including checks for card stacking, oversized fonts, low-semantic text, redundant information, detached controls, and wasted canvas space.

Status: completed

### 16. Add Safety, Versioning, And Rollback Boundaries

Goal: Make agent-authored orchestration changes safe to review and undo.

Main actions:

- Add graph versioning and migration reports.
- Add before/after graph snapshots for GUI edits and code imports.
- Add rollback affordance or documented rollback procedure.
- Add focused secret scanning for graph files, prompt templates, run reports, and evidence.
- Ensure provider credentials and vault contents are referenced only by safe identifiers, never copied.
- Preserve enough click-driven evidence around GUI edits that a future agent can both reproduce the change and verify the rollback path from the visible product surface.
- Require snapshot creation, diff inspection, rollback, and reopen checks to be attempted through visible controls first whenever that path exists in the product.

Acceptance criteria:

- A graph edit creates or preserves enough state to compare and roll back.
- Secret scan checks run over changed graph/prompt/evidence files with no concrete secrets found.
- Migration reports are generated for version changes.
- Rollback procedure is documented and tested on at least one sample graph.
- The validation note records the exact click path for snapshot creation, confirmation, diff inspection, rollback, and post-rollback re-open checks.
- The evidence note explicitly separates visible rollback proof from any later backend inspection used only to explain failures.

Status: completed

### 17. Add End-To-End Click-Driven Dogfood Scenarios

Goal: Prove the full product path with realistic user workflows.

Main actions:

- Execute full simulated user sessions for at least three workflows:
  - code fix/test/review,
  - provider update/smoke/gate,
  - fan-out research/fan-in synthesis.
- For each workflow: import or instantiate graph, edit node prompt, wire or edit edge, dry-run, run fixture or safe local execution, inspect trace, open artifact, export graph, reload, and verify state.
- Test at least two viewport sizes.
- Use only visible product controls for all user-facing actions. Direct API calls may diagnose failures after they are captured, but cannot advance the happy path.
- Force each scenario owner to review screenshots repeatedly during the run, not only at the end, and record concrete UI debt seen at each major stage.

Acceptance criteria:

- Evidence packs exist for all three workflows.
- Each evidence pack includes screenshots for entry, graph creation/import, node edit, edge edit, dry-run, run/fixture, trace, artifact, export, reload, and viewport checks.
- No tested path ends in a silent dead end.
- Exported graphs validate after the run.
- Remaining issues are classified as blocker, high, medium, or backlog with screenshots, and UI anti-patterns such as card stacking, oversized text, redundant metadata, and wasted canvas space are explicitly reviewed.
- The evidence notes make clear that workflow progression happened through simulated product interaction rather than hidden state changes.
- Each scenario report explicitly separates visible simulated interaction from any later API/log diagnosis and names the screenshots reviewed during the implementation loop.
- Each scenario report names the exact point where screenshots triggered a UI correction or, if not fixed, an explicit remaining-debt entry.

Status: completed

### 18. Publish Maintainer Runbook And Product Boundary

Goal: Leave a future maintainer with the rules needed to extend orchestration safely.

Main actions:

- Write a maintainer runbook for adding node types, edge types, prompt editors, schema editors, templates, DSL fields, migrations, and skill rules.
- Document the canonical graph contract ownership and compatibility policy.
- Document the required validation matrix for every orchestration change.
- Link the runbook from relevant plan or docs files.
- Explicitly document that future agents must prefer simulated clicks plus screenshot review over API shortcuts when validating visible product behavior.
- Explicitly document that the in-app browser is the default proof environment when the local product is already running and visible there.

Acceptance criteria:

- Runbook exists on disk.
- Runbook includes click-validation, code-validation, dry-run, migration, rollback, and secret-scan requirements.
- Runbook includes screenshot cadence, UI quality checklist, forbidden API substitutions, and examples of acceptable click-driven evidence.
- Runbook includes "how to add a new provider/model-sensitive agent template" without hardcoding secrets.
- This plan's current progress and progress log are updated with the final status and any remaining follow-on work.
- The runbook includes a short "do not fake the UI" section that forbids using API/store mutation as the sole proof for visible product work.
- The runbook includes a short "screenshot review loop" section that tells future agents to capture, inspect, critique, fix, and re-open the product repeatedly until obvious UI debt is addressed or explicitly logged.

Status: completed

## Progress Log

### 2026-07-08 - Plan Update For Agent-Self-Operated Product Clicking And Screenshot-Critique Discipline

- Completed: Tightened the plan again so future agents must treat the visible in-app browser surface as an active workbench, not a passive preview, and must personally drive the app through click, double-click, type, drag, hover, scroll, expand/collapse, resize, reopen, and reload where relevant.
- Completed: Made it explicit that API calls, sidecar endpoints, store patches, fixture seeds, `page.evaluate(...)`, console injection, and direct persistence writes are forbidden as the primary mutation path for GUI acceptance claims and count only as diagnosis unless the same result is later reproduced from the visible product surface.
- Completed: Raised the screenshot-review bar so future agents must record what they simplified, removed, collapsed, or moved behind tooltip/expansion after screenshots exposed low-semantic clutter, redundancy, oversized typography, weak workspace priority, or unnecessary framing.
- Completed: Strengthened execution-log requirements so future agents must state that the first primary mutation attempt came from the visible product surface, identify which screenshots were used for intermediate critique, and confirm whether the same in-app browser surface remained the main proof environment through the step.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for mandatory GUI operation, mandatory click-driven review loop, execution rules, and progress-log expectations before editing.
  - Verified the updated plan now forces future agents to prove GUI work by self-operated product interaction plus screenshot critique, instead of drifting into API-first validation.
- Blockers: None.
- Next step: Step 16, Add Safety, Versioning, And Rollback Boundaries.

### 2026-07-08 - Step 15 Create Main Agent Orchestration Skill

- Completed: Created a repository-managed AstraBridge orchestration skill at `apps/astrabridge-sidecar/skills/agent-orchestration-operator/`.
- Completed: Added skill guidance that tells future agents when to stay single-agent, when bounded orchestration is justified, how to keep graph depth shallow, and when user approval is mandatory for deeper nesting, risky permissions, or live provider execution.
- Completed: Added explicit code-first operating rules for canonical graph files and the orchestration CLI `lint`, `dry-run`, and `diff` commands.
- Completed: Added explicit click-first GUI proof rules so future agents must use the in-app browser, visible interaction, dense screenshots, and screenshot critique instead of API-first shortcuts for visible product work.
- Completed: Added a reference file that points future agents at the durable plan, canonical graph contract, CLI, desktop workspace, example graphs, validation checklist, approval checklist, and example request patterns.
- Completed: Preserved a Step 15 evidence pack under `PRIVATE/agent-orchestration/productization/step15/20260708/`, including a task-local example graph, lint/dry-run/diff reports, and the final validation note.
- Files changed:
  - `apps/astrabridge-sidecar/skills/agent-orchestration-operator/SKILL.md`
  - `apps/astrabridge-sidecar/skills/agent-orchestration-operator/agents/openai.yaml`
  - `apps/astrabridge-sidecar/skills/agent-orchestration-operator/references/operating-surfaces.md`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step15/20260708/validation-note.md`
- Validation:
  - Ran `python C:\Users\cyz19\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AstraBridge\apps\astrabridge-sidecar\skills\agent-orchestration-operator`
  - Generated `PRIVATE/agent-orchestration/productization/step15/20260708/graph_step15_skill_example_code_fix_review.json` from the canonical code-fix example.
  - Ran `.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli lint ...`
  - Ran `.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli dry-run ...`
  - Ran `.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli diff ...`
- Validation artifacts:
  - `PRIVATE/agent-orchestration/productization/step15/20260708/reports/lint.json`
  - `PRIVATE/agent-orchestration/productization/step15/20260708/reports/dry-run.json`
  - `PRIVATE/agent-orchestration/productization/step15/20260708/reports/diff.json`
  - `PRIVATE/agent-orchestration/productization/step15/20260708/validation-note.md`
- User-facing workflow versus backend validation:
  - no new desktop or sidecar UI behavior was changed in Step 15;
  - visible product-surface proof remained the Step 14 in-app browser evidence for graph authoring and persistence;
  - Step 15 acceptance itself came from skill-structure validation plus code-first graph validation, not from a new GUI mutation claim.
- Real issue encountered and resolved:
  - the first generated example graph was written with a UTF-8 BOM by PowerShell and the orchestration CLI rejected it with `Unexpected UTF-8 BOM`;
  - the file was rewritten as UTF-8 without BOM and then passed lint, dry-run, and diff.
- Blockers: None for Step 15 after the BOM rewrite.
- Next step: Step 16, Add Safety, Versioning, And Rollback Boundaries.

### 2026-07-08 - Step 14 Add Graph Templates And Example Library

- Completed: Verified the live sidecar template catalog in the running product after replacing a stale in-memory process; the visible template rail now exposes `7` templates instead of the stale `5`-template state seen earlier in the step.
- Completed: Generated canonical code-first template files under `PRIVATE/agent-orchestration/productization/step14/20260708/template-files/` and lint-validated all required files through `astrabridge_sidecar.agent_orchestration_cli`.
- Completed: Fixed the desktop template-instantiation race in `TaskGraphWorkspace` so rapid template selection followed immediately by `实例化模板` resolves the most recently clicked template instead of a stale prior selection.
- Completed: Proved Step 14 through visible in-app interaction:
  - opened the task graph,
  - expanded the template rail,
  - instantiated at least five templates from the visible template surface,
  - inspected template defaults through visible node/edge selection,
  - reproduced the formerly risky rapid `Custom Blank Graph` instantiation path,
  - edited the instantiated node label through the visible inspector and `保存节点` control,
  - returned to chat and reopened the graph from the visible `任务图` control,
  - confirmed the persisted graph reopened as `Custom Blank Graph` with the edited node label `Start Here Revised`.
- Completed: Preserved the Step 14 evidence pack and final validation note under `PRIVATE/agent-orchestration/productization/step14/20260708/validation-note.md`.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step14/20260708/validation-note.md`
- Validation:
  - Ran `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx`
  - Ran `cmd /c npm run build`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli lint D:\\AstraBridge\\PRIVATE\\agent-orchestration\\productization\\step14\\20260708\\template-files\\supervisor_worker_synthesizer.json`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli lint D:\\AstraBridge\\PRIVATE\\agent-orchestration\\productization\\step14\\20260708\\template-files\\fanout_fanin_research.json`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli lint D:\\AstraBridge\\PRIVATE\\agent-orchestration\\productization\\step14\\20260708\\template-files\\code_fix_test_review.json`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli lint D:\\AstraBridge\\PRIVATE\\agent-orchestration\\productization\\step14\\20260708\\template-files\\multimodal_capability_adapter.json`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli lint D:\\AstraBridge\\PRIVATE\\agent-orchestration\\productization\\step14\\20260708\\template-files\\custom_blank_graph.json`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli lint D:\\AstraBridge\\examples\\agent-orchestration\\code_fix_review.json`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli lint D:\\AstraBridge\\examples\\agent-orchestration\\provider_update_smoke.json`
  - Used the in-app browser as the primary proof surface throughout the final validation pass.
- Screenshots reviewed during implementation:
  - stale/pre-restart and post-restart template rail: `step14-04-before-reload-current-surface.png`, `step14-05-after-reload-post-sidecar-restart.png`, `step14-07-template-rail-expanded.png`
  - multi-template instantiation and default inspection: `step14-08-template-instantiated-supervisor-worker-synthesizer.png`, `step14-09-supervisor-template-inspector-defaults.png`, `step14-10-template-instantiated-fanout-fanin-research.png`, `step14-11-template-instantiated-code-fix-test-review.png`, `step14-12-code-fix-worker-inspector-defaults.png`, `step14-13-template-instantiated-multimodal-capability-adapter.png`, `step14-14-template-instantiated-custom-blank-graph.png`
  - post-fix rapid custom-blank path, follow-on edit, and reopen persistence: `step14-20-postfix-custom-blank-instantiated.png`, `step14-21-custom-blank-node-selected-inspector-open.png`, `step14-23-custom-blank-label-edited-saved.png`, `step14-24-returned-to-chat-after-custom-blank-edit.png`, `step14-25-reopened-graph-after-chat-custom-blank-persisted.png`
  - constrained-width review: `step14-27-constrained-width-graph-custom-blank-persisted.png`, `step14-28-constrained-width-graph-scrolled-into-view.png`
- UI issues observed from those screenshots:
  - the template rail is usable but still text-heavy for a canvas-first surface;
  - the left project/task rail and right status panel still reduce canvas priority during graph work;
  - the constrained-width pass shows the surrounding shell can push the graph lower in the viewport before the canvas becomes the dominant visible surface.
- Visible proof versus diagnosis:
  - visible proof covered template discovery, instantiation, default inspection, follow-on editing, return-to-chat, and reopen persistence;
  - earlier direct sidecar instantiation calls and the stale-sidecar restart were diagnosis/remediation only and were not counted as GUI acceptance evidence.
- The product stayed open in the in-app browser during iteration, and each major UI change in the final pass was rechecked there by visible interaction plus screenshots before moving on.
- In-page script execution was limited to read-only inspection. No `page.evaluate(...)` state mutation, direct sidecar write, store patch, fixture preload, or direct persistence write was used as acceptance evidence.
- Blockers resolved:
  - replaced the stale 5-template sidecar process with the current-source 7-template process;
  - removed the desktop race that could instantiate the previously selected template when the user clicked a new template and immediately clicked the instantiate button.
- Next step: Step 15, Create Main Agent Orchestration Skill.

### 2026-07-08 - Plan Update For In-App Simulated Interaction And Continuous Screenshot Review

- Completed: Tightened the plan again so future agents must keep the running in-app browser surface open and treat that same visible surface as the required primary proof path whenever the product is already available there locally.
- Completed: Clarified that acceptable simulated interaction means user-like operation only: visible clicks, typing, dragging, hovering, scrolling, expand/collapse actions, and reload or reopen passes from the real product surface.
- Completed: Raised the evidence bar so UI-facing notes must now include intermediate screenshot-review notes and progress logs must disclose whether each major UI change was rechecked in the in-app browser before the agent moved on.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for evidence convention, mandatory GUI operation, execution rules, current progress, and Step 14-15 context before editing.
  - Verified the updated plan now explicitly requires in-app simulated interaction, continuous screenshot review, and intermediate screenshot critique disclosure for future UI-facing steps.
- Blockers: None.
- Next step: Step 14, Add Graph Templates And Example Library.

### 2026-07-08 - Step 13 Add Runtime Trace And Debugger Surface

- Completed: Added clickable timeline-event selection in `TaskGraphWorkspace`, including visible selected-row state and mapping from selected event back to the related graph node or edge when the run metadata provides that relationship.
- Completed: Added lightweight run-dock retry/replay affordances so dry-run results expose `重试 Dry-run` and non-active fixture runs expose `重放夹具` without forcing the user back to the top toolbar.
- Completed: Extended compact run timeline events in the sidecar to preserve optional `edge_id` and `artifact_id` fields, and added a provider-update approval fixture event `node_id` so approval timeline selection can map back to the gate node through the visible UI.
- Completed: Added focused tests for timeline-event mapping, approval-event fallback selection, and latest-run retry affordances.
- Completed: Preserved the Step 13 evidence pack and validation note under `PRIVATE/agent-orchestration/productization/step13/20260708/`.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `apps/astrabridge-desktop/src/types.ts`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step13/20260708/validation-note.md`
- Validation:
  - Ran `node .\\node_modules\\vitest\\vitest.mjs run src\\features\\runtime\\TaskGraphWorkspace.test.tsx`
  - Ran `cmd /c npm run build`
  - Ran `python -m unittest D:\\AstraBridge\\apps\\astrabridge-sidecar\\tests\\test_task_graph_api.py`
  - Used the in-app browser as the primary proof environment.
  - Used read-only browser DOM inspection only after the visible click path existed, to confirm event ids and scroll-revealed controls.
- Visible interaction proven through the running product:
  - opened the task graph from chat,
  - expanded the latest run dock,
  - started a fixture run,
  - captured the synthetic pending/running state,
  - expanded the timeline,
  - scrolled inside the run dock to reach the `approval_requested` event,
  - selected that timeline row,
  - opened a worker artifact,
  - rejected the approval gate to force a failed run state,
  - reloaded the app,
  - reopened the task graph,
  - expanded the failed latest run and reselected the timeline event after reload.
- Screenshots reviewed by the implementing agent:
  - before-state: `step13-01-chat-before-open.png`
  - entry/open: `step13-02-graph-opened.png`, `step13-03-run-panel-expanded.png`
  - run transition: `step13-04-run-started.png`, `step13-05-run-after-transition.png`
  - trace/debug navigation: `step13-06-timeline-expanded.png`, `step13-07a-run-panel-scrolled.png`, `step13-08-event-selected-highlighted-node.png`, `step13-16-failed-event-selected-node-highlighted.png`
  - artifact open: `step13-09-artifact-opened.png`
  - failure state: `step13-10-rejected-failure-state.png`
  - reload persistence: `step13-11-after-reload.png`, `step13-12-graph-reopened-after-reload.png`, `step13-13-failed-run-expanded-after-reload.png`, `step13-14-failed-run-timeline-expanded.png`, `step13-15-failed-run-scrolled-to-event.png`
- UI issues observed from screenshots:
  - the run dock still becomes scroll-heavy when approval, timeline, diagnostics, and worker outputs are all present in the same narrow region;
  - the selected-node trace highlight is still subtler than ideal on the pale canvas and should likely get stronger contrast or auto-centering in a later pass;
  - the latest-run dock is now more actionable, but its internal scrollbar remains visually dense when the right-side inspector is also open.
- In-page script execution was limited to read-only inspection only. No mutating sidecar call, store patch, fixture preload, or console state injection was used as acceptance evidence.
- The first successful mutating path for Step 13 was completed through simulated interaction from the visible product surface.
- Blockers: None for Step 13.
- Next step: Step 14, Add Graph Templates And Example Library.

### 2026-07-08 - Plan Update For In-App Click-First Proof And Dense Screenshot Review

- Completed: Tightened the productization plan again so future agents must treat the in-app browser surface as the default proof environment for visible product work and must drive it by simulated user actions rather than API/store shortcuts.
- Completed: Strengthened the evidence contract so UI-facing steps now require an explicit statement that the primary mutating path was attempted from the visible product surface before any backend shortcut was considered.
- Completed: Tightened the remaining Step 13-18 requirements so trace/debugger, templates, orchestration skill, rollback, dogfood scenarios, and maintainer docs all explicitly require screenshot review during implementation, not only final-state documentation.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, evidence convention, execution rules, and remaining Step 13-18 acceptance criteria before editing.
  - Verified the updated plan now makes in-app click-driven proof, dense screenshot review, and explicit separation between visible proof and later backend diagnosis part of the written contract for future agents.
- Blockers: None.
- Next step: Step 13, Add Runtime Trace And Debugger Surface.

### 2026-07-08 - Plan Update For Simulated Product Operation And Screenshot-Led UI Critique

- Completed: Tightened the plan so future agents must keep the running in-app browser surface as the primary proof environment for visible product work and operate it through simulated clicks, typing, dragging, hover, scroll, resize, expand/collapse, and reload instead of hidden state mutation.
- Completed: Strengthened the evidence contract so UI-facing notes must now explicitly disclose that no `page.evaluate(...)` state mutation, store patching, fixture preload, direct sidecar write, or direct persistence write was used as acceptance evidence.
- Completed: Raised the screenshot-review bar again so future agents must preserve a denser review loop and explicitly critique card stacking, over-framing, oversized fonts, low-semantic text, redundancy, detached controls, awkward iconography, and wasted canvas area while the work is still in progress.
- Completed: Tightened Step 14 and Step 15 specifically so template productization and orchestration-skill work both require in-app click-first proof plus screenshot-led UI critique as hard acceptance conditions.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, evidence convention, GUI quality gate, click-driven review loop, execution rules, and Step 14-15 acceptance criteria before editing.
  - Verified the updated plan now treats simulated product interaction and screenshot-led UI critique as mandatory execution behavior rather than soft guidance.
- Blockers: None.
- Next step: Step 14, Add Graph Templates And Example Library.

### 2026-07-08 - Step 12 Add Prompt, Schema, And Contract Editors

- Completed: Added click-driven prompt-variable insertion and payload preview support for node prompt templates in `TaskGraphWorkspace`, including upstream-variable chips and a node payload preview panel.
- Completed: Added click-driven variable insertion and payload preview support for edge handoff message templates in `TaskGraphWorkspace`.
- Completed: Added focused tests covering prompt variable insertion, schema validation failure, and edge payload preview behavior.
- Completed: Fixed a real persistence/export mismatch where a successful edge edit could remain newer in the browser fallback graph than the last server-returned graph. The desktop app now overwrites the local fallback graph with the server-returned graph after successful node and edge saves so reload, export, and dry-run converge on the same saved graph.
- Completed: Preserved the full Step 12 evidence pack and final validation note under `PRIVATE/agent-orchestration/productization/step12/20260708/`.
- Files changed:
  - `apps/astrabridge-desktop/src/App.tsx`
  - `apps/astrabridge-desktop/src/api.ts`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step12/20260708/validation-note.md`
- Validation:
  - Performed visible product interaction in the in-app browser for prompt edit, prompt-variable insertion, invalid schema validation, valid save, edge contract edit, edge save, export, dry-run, reload, and re-open.
  - Reviewed preserved screenshots including:
    - `step12-06-prompt-variable-inserted.png`
    - `step12-07-invalid-schema-validation.png`
    - `step12-09-edge-variable-payload-preview.png`
    - `step12-12-node-persisted-after-reload.png`
    - `step12-13-edge-persisted-after-reload.png`
    - `step12-23-edge-save-after-fallback-sync-fix.png`
    - `step12-24-export-after-fix.png`
  - Ran `node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx` from `apps\astrabridge-desktop`
  - Ran `cmd /c npm run build` from `apps\astrabridge-desktop`
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli dry-run D:\AstraBridge\PRIVATE\demo-runs\native-kernel-provider-neutral-verify-20260623-205312\workspace\PRIVATE\agent-orchestration\productization\step12\20260708\graph_provider_update_smoke_step12_fixed.json`
- UI issues observed from screenshots:
  - the inspector is still vertically dense when communication contract, schema refs, and advanced settings are all open;
  - the right-side global status rail still competes with the graph inspector for horizontal space;
  - exploratory extra nodes and edges remain in the validation graph and add visual noise even though they are useful as persistence/export stress cases.
- Important visible-vs-diagnostic separation:
  - visible proof covered the editor interactions, save actions, reload path, export flow, and dry-run flow;
  - later diagnosis compared the browser-visible graph with the sidecar graph and exported JSON to find and fix the fallback/server divergence.
- Blockers resolved:
  - exported edge handoff messages now match the last successfully saved visible edge editor state;
  - browser fallback graph state is now reconciled with the server-returned graph after successful node and edge saves.
- Next step: Step 13, Add Runtime Trace And Debugger Surface.

### 2026-07-08 - Plan Update For In-App Browser-First Product Proof

- Completed: Tightened the plan so future agents must treat the visible product surface as the default and mandatory proof path for UI-facing work, with the first mutating validation attempt happening through simulated clicks, typing, dragging, scrolling, expand/collapse, and reload from the running app.
- Completed: Raised the evidence bar so UI steps must preserve the starting surface, dense interaction screenshots, an explicit statement separating visible proof from later diagnosis, and a screenshot-review loop that catches card stacking, oversized fonts, low-semantic text, redundant metadata, detached controls, confusing icons, unnecessary framing, clipped content, and wasted canvas area.
- Completed: Strengthened the execution log requirements so future agents must disclose whether the first successful mutating path was completed entirely through simulated product interaction and cannot silently count API/store shortcuts as acceptance evidence.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, evidence convention, mandatory click-driven review loop, and execution rules before editing.
  - Verified the updated plan now explicitly treats screenshot review as part of the implementation loop and makes the in-app browser product surface the preferred proof environment for visible UI work.
- Blockers: None.
- Next step: Step 12, Add Prompt, Schema, And Contract Editors.

### 2026-07-08 - Step 10 Productize Node Inspector For Agent Configuration

- Completed: Extended the node inspector so visible node configuration now covers provider, model, reasoning, permission mode, collaboration mode, execution backend, context policy, memory policy, prompt template, prompt preview, output schema, artifact outputs, and tool or approval settings.
- Completed: Verified the real product flow by simulated clicks in the running app:
  - opened `任务图`,
  - expanded the inspector,
  - selected `Smoke Matrix`,
  - edited provider/model/prompt/schema/tool-policy fields,
  - exercised invalid prompt-variable and unsafe-tools validation states,
  - saved a valid node configuration,
  - reloaded and reopened the inspector,
  - exported the graph through the visible export dialog.
- Completed: Preserved a Step 10 evidence pack under `PRIVATE/agent-orchestration/productization/step10/20260708/`, including the initial stale-sidecar failure screenshots, the passing rerun screenshots, the sidecar restart logs, and `validation-note.md`.
- Completed: Verified the exported graph file at `PRIVATE/demo-runs/native-kernel-provider-neutral-verify-20260623-205312/workspace/step10-node-inspector-export.json` contains the saved `node_smoke` prompt, schema, artifact, and approval fields.
- Files changed:
  - `apps/astrabridge-desktop/src/App.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/taskGraphFallbackState.ts`
  - `apps/astrabridge-desktop/src/styles.css`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step10/20260708/validation-note.md`
- Validation:
  - Performed visible product interaction against `http://127.0.0.1:4181/?astrabridge_launch=dogfood&sidecar=http%3A%2F%2F127.0.0.1%3A8802`.
  - Reviewed the preserved screenshots:
    - `step10-rerun-04-inspector-open.png`
    - `step10-rerun-05b-invalid-variable-visible-error.png`
    - `step10-rerun-06-unsafe-tools.png`
    - `step10-rerun-08-after-reload-node.png`
    - `step10-rerun-10-export-complete.png`
  - Ran `node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx` from `apps\astrabridge-desktop`
  - Ran `cmd /c npm run build` from `apps\astrabridge-desktop`
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  - Verified `GET http://127.0.0.1:8802/api/health` returned `current_source_match: true` before the final rerun.
- UI issues observed from screenshots:
  - the invalid-variable error is rendered, but it sits low in the inspector and requires scrolling to become visible;
  - the inspector remains vertically dense when prompt, schema, artifact, and tool sections are all expanded;
  - the global right-side status panel still competes with the graph inspector for horizontal space.
- Blockers: None for Step 10.
- Next step: Step 11, Productize Edge Wiring And Communication Contracts.

### 2026-07-08 - Step 9 Add Agent Palette And Node Creation UX

- Completed: Added visible node-creation support through a compact role palette in the task graph workspace instead of requiring hidden graph mutation.
- Completed: Added safe defaults for newly created nodes in both the desktop fallback path and the sidecar-backed path, including draft state, output contract defaults, execution defaults, and `ui_hints.palette_role`.
- Completed: Preserved a click-driven Step 9 evidence pack under `PRIVATE/agent-orchestration/productization/step9/20260708/`, including palette open, node creation, fit-view, reload, custom-node selection, and tooltip screenshots.
- Completed: Wrote `validation-note.md` documenting the exact product click path, screenshot review findings, remaining non-blocking UI debt, and the separation between visible proof and secondary diagnostics.
- Files changed:
  - `apps/astrabridge-desktop/src/api.ts`
  - `apps/astrabridge-desktop/src/App.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/taskGraphFallbackState.ts`
  - `apps/astrabridge-desktop/src/styles.css`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step9/20260708/validation-note.md`
- Validation:
  - Performed visible product interaction in the running in-app browser: opened the task graph, expanded the palette, added supervisor/validator/custom nodes, fit the view, reloaded, reopened the graph, selected the custom node, and captured tooltip evidence through visible click/focus interaction.
  - Reviewed the preserved screenshots:
    - `step9-05-node-palette-expanded.png`
    - `step9-07-fit-view-after-add.png`
    - `step9-10-task-graph-after-reload.png`
    - `step9-12-custom-node-selected.png`
    - `step9-20-palette-tooltip-click.png`
  - Ran `node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx` from `apps\astrabridge-desktop`
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  - Ran `cmd /c npm run build` from `apps\astrabridge-desktop`
- UI issues observed from screenshots:
  - the palette itself is compact and readable;
  - the current-node list remains somewhat text-dense compared with the palette;
  - broader shell density outside the canvas is still present but does not block Step 9 usability.
- Blockers: None for Step 9.
- Next step: Step 10, Productize Node Inspector For Agent Configuration.

### 2026-07-08 - Plan Update For Simulated Click And Screenshot Discipline

- Completed: Tightened the productization plan so future agents must treat the running AstraBridge app in the in-app browser as the default proof environment for visible product work.
- Completed: Made the "no API as fake GUI proof" rule more explicit in the global constraints, GUI quality gate, click-driven review loop, and execution rules.
- Completed: Strengthened Steps 9-18 so their acceptance criteria now require an explicit click path, screenshot path, and a clear separation between user-visible proof and any later backend diagnosis.
- Completed: Added stronger screenshot-discipline language so future agents must preserve before-state, entry path, major interaction states, layout-adjustment states, reload confirmation, and constrained-width review for visible UI work.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, GUI proof rules, execution rules, and Steps 9-18 before editing.
  - Verified the updated plan now requires future agents to prove GUI behavior through simulated product interaction first and to document API/log usage only as secondary diagnosis.
- Blockers: None.
- Next step: Step 9, Add Agent Palette And Node Creation UX.

### 2026-07-08 - Plan Update For Replayable Click Proof

- Completed: Tightened the plan again so UI-facing work must start from the visible product surface and attempt the real user flow through simulated clicks, typing, dragging, hover, expand/collapse, scroll, and reload before any mutating backend shortcut is considered.
- Completed: Expanded the screenshot discipline so future agents must preserve a replayable review loop rather than only a final screenshot, and must actively inspect those screenshots for card stacking, oversized fonts, low-semantic text, repeated information, detached controls, unnecessary frames, clipping, and wasted whitespace.
- Completed: Raised the completion bar so another agent should be able to reconstruct the visible flow from the written click sequence and screenshot trail alone, without relying on hidden state injection.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, mandatory GUI operation, mandatory click-driven review loop, and execution rules before editing.
  - Verified the updated plan now treats screenshot critique as a hard completion gate and treats backend mutation as invalid primary proof for visible product work.
- Blockers: None.
- Next step: Step 10, Productize Node Inspector For Agent Configuration.

### 2026-07-07 - Step 8 Redesign Canvas Information Architecture

- Completed: Reworked the task-graph workspace so the canvas is the dominant desktop surface instead of competing with large side panels and nested framed containers.
- Completed: Moved import/export status into the canvas header and shifted dry-run/readiness plus latest-run information into compact bottom docks so secondary status no longer consumes primary canvas space.
- Completed: Tightened the task-graph grid, collapsed rails, node-card density, inspector chips, and toolbar sizing so the graph keeps meaningful width even when surrounding controls are present.
- Completed: Improved narrow-width behavior so the layout stacks instead of squeezing the canvas into a cramped multi-column strip.
- Completed: Preserved a screenshot review pack under `PRIVATE/agent-orchestration/productization/step8/20260707/`, including before/intermediate/final desktop and narrow layouts plus the dry-run dock state.
- Completed: Added `validation-note.md` documenting the click path, screenshots reviewed, UI issues observed, and why the revised layout is more user-friendly.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step8/20260707/validation-note.md`
- Validation:
  - Reviewed the preserved screenshots:
    - `step8-06-desktop-default-final.png`
    - `step8-07-desktop-expanded-final.png`
    - `step8-10-narrow-default-stacked.png`
    - `step8-11-narrow-sidebar-stacked.png`
    - `step8-12-desktop-dry-run-dock.png`
  - Ran `node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx` from `apps\astrabridge-desktop`
  - Ran `cmd /c npm run build` from `apps\astrabridge-desktop`
- UI issues observed from screenshots:
  - loading-state copy is still visible on the canvas while the graph hydrates
  - the expanded template rail remains somewhat text-dense
  - the fully expanded inspector is still dense, though no longer card-heavy
- API/store usage note:
  - no direct API/store mutation was used to advance the visible Step 8 happy path; the evidence pack is based on simulated interaction plus screenshot review
- Blockers: None for Step 8.
- Next step: Step 9, Add Agent Palette And Node Creation UX.

### 2026-07-07 - Step 7 Implement Import And Export Round Trip In The App

- Completed: Added sidecar import/export HTTP routes for canonical orchestration graph files and synced them with the current task-graph runtime state.
- Completed: Added desktop API types and calls for task-graph import/export, plus visible graph-workspace toolbar controls for `Import` and `Export`.
- Completed: Added focused Step 7 regression coverage in:
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
- Completed: Preserved a real click-driven validation pack under `PRIVATE/agent-orchestration/productization/step7/20260707/`, including:
  - graph workspace screenshots before import, during modal entry, after import, after export, and after reload
  - exported graph file `ui-export-provider-update.json`
  - CLI lint output `lint-ui-export-provider-update.json`
  - semantic diff output `diff-provider-update-roundtrip.json`
  - `validation-note.md` with the exact click path and UI review
- Completed: Verified the real product path by simulated clicks against the live app:
  - opened the graph workspace through the visible topbar control,
  - imported `examples/agent-orchestration/provider_update_smoke.json` through the visible modal,
  - exported the resulting graph through the visible modal,
  - reloaded the app and confirmed the imported provider-update graph persisted.
- Important implementation note:
  - the active task was running inside a workspace under `PRIVATE/demo-runs/native-kernel-provider-neutral-verify-20260623-205312/workspace`, so repository example graphs had to be copied into that workspace before the visible import path could succeed. This is now recorded as product behavior, not hidden setup.
- Files changed:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `apps/astrabridge-desktop/src/types.ts`
  - `apps/astrabridge-desktop/src/api.ts`
  - `apps/astrabridge-desktop/src/App.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step7/20260707/validation-note.md`
- Validation:
  - Ran `python -m unittest apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  - Ran `node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx` from `apps\astrabridge-desktop`
  - Ran `cmd /c npm run build` from `apps\astrabridge-desktop`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli lint D:\AstraBridge\PRIVATE\agent-orchestration\productization\step7\20260707\ui-export-provider-update.json`
  - Ran `python -m astrabridge_sidecar.agent_orchestration_cli diff D:\AstraBridge\examples\agent-orchestration\provider_update_smoke.json D:\AstraBridge\PRIVATE\agent-orchestration\productization\step7\20260707\ui-export-provider-update.json`
- UI issues observed from screenshots:
  - stray `Not found` text still appears under the canvas heading
  - import/export paths are workspace-relative and the UI does not yet explain the active workspace root clearly enough
  - import/export confirmation strip is not durable across reload
- Blockers: None for Step 7.
- Next step: Step 8, Redesign Canvas Information Architecture.

### 2026-07-07 - Plan Update For Simulated Click Enforcement

- Completed: Tightened the plan so future agents must validate visible product work through the running app with simulated clicks, typing, hovering, dragging, reload checks, and frequent screenshot review.
- Completed: Added explicit language that the in-app browser is the default proof path for local UI work and that API-first validation is only supplemental.
- Completed: Strengthened the remaining step descriptions so import/export, canvas redesign, palette, inspector, edge editor, contract editors, debugger, templates, skill, safety, and maintainer docs all carry the same click-first and screenshot-first expectation.
- Files changed: `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, GUI proof rules, and Steps 7-18 before editing.
  - Verified the updated plan now treats screenshot critique as a required implementation loop and makes direct API/store mutation invalid as sole GUI proof.
- Blockers: None.
- Next step: Step 7, Implement Import And Export Round Trip In The App.

### 2026-07-07 - Plan Update For Product-First Click Loops

- Completed: Strengthened the handoff plan again so future agents must treat the live product surface as the primary execution path instead of treating APIs or store mutations as interchangeable shortcuts.
- Completed: Added a dedicated click-driven review loop that requires repeated simulated interaction, frequent screenshots, and explicit screenshot critique before a UI step can be accepted.
- Completed: Expanded the UI review checklist so future agents must actively watch for card stacking, oversized fonts, low-semantic text, redundant information, unnecessary frames, cramped inspectors, clipped labels, and wasted canvas space.
- Files changed: `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, GUI proof rules, evidence convention, and execution rules before editing.
  - Verified the updated plan now contains an explicit "product first, API second" execution order for UI-facing work.
- Blockers: None.
- Next step: Step 8, Redesign Canvas Information Architecture.

### 2026-07-07 - Step 0

- Completed: Created this durable handoff plan for productizing AstraBridge agent orchestration across GUI, code-first graph files, runtime validation, and main-agent skill workflows.
- Files changed: `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\references\plan-template.md`.
  - Reviewed existing task-graph plan names and `PLAN/MULTI_AGENT_TASK_GRAPH_CLICK_DRIVEN_PRODUCTIZATION_PLAN.md` to avoid overwriting completed or in-progress plan structure.
- Blockers: None.
- Next step: Step 1, Baseline Current Orchestration Surface.

### 2026-07-07 - Plan Strengthening For GUI-First Validation

- Completed: Strengthened the plan so future agents must operate AstraBridge through visible simulated clicks instead of relying on APIs, stores, unit tests, or DOM inspection as substitutes for user-facing proof.
- Completed: Added a mandatory screenshot cadence and UI quality gate focused on catching card stacking, oversized fonts, low-semantic text, redundant metadata, cramped inspectors, unclear icons, clipped controls, and wasted canvas space.
- Completed: Tightened acceptance criteria for baseline capture, import/export, canvas redesign, palette, node inspector, edge contracts, prompt/schema editors, trace/debugger, templates, end-to-end dogfood, and maintainer runbook steps.
- Files changed: `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the existing plan before editing.
- Verified the updated plan now contains explicit GUI operation, screenshot cadence, UI quality checklist, forbidden API substitution, and tightened step-level acceptance language.
- Blockers: None.
- Next step: Step 1, Baseline Current Orchestration Surface.

### 2026-07-07 - Plan Update For Click-First UI Proof

- Completed: Strengthened the plan again so future agents must use simulated clicks, typing, dragging, reload checks, and screenshot review as the primary validation loop for any visible product change.
- Completed: Added explicit prohibitions against using API/store mutations to create, wire, run, import, export, or persist graph state when claiming a GUI workflow works.
- Completed: Tightened the UI-facing acceptance criteria so evidence notes must include the exact click path, screenshot review conclusions, and any remaining UI rough edges.
- Files changed: `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan before editing.
  - Verified the updated plan now treats screenshot review as part of the implementation loop, not just documentation, and explicitly requires fresh-open verification passes for UI steps.
- Blockers: None.
- Next step: Step 4, Implement Schema Validation And Migration Skeleton.

### 2026-07-07 - Step 1 Baseline Current Orchestration Surface

- Completed: Read the Step 1 plan requirements and the current task-graph desktop and sidecar implementation surface.
- Completed: Drove the live app through visible UI actions only:
  - observed the setup surface,
  - clicked `返回对话`,
  - clicked the visible topbar `任务图` control to reopen the graph,
  - expanded the graph sidebar and graph inspector,
  - captured a constrained-width screenshot after a temporary viewport override.
- Completed: Preserved the Step 1 evidence pack under `PRIVATE/agent-orchestration/productization/step1/20260707/`, including:
  - `step1-setup-surface.png`
  - `step1-chat-after-close.png`
  - `step1-graph-initial.png`
  - `step1-graph-after-reopen.png`
  - `step1-graph-sidebar-inspector-expanded.png`
  - `step1-graph-narrow.png`
  - `baseline-note.md`
- Completed: Documented the current graph schema surface, current GUI affordances, runtime support, known gaps, and a screenshot-based UI quality checklist in `baseline-note.md`.
- Important observations:
  - the current task graph is already a real execution-oriented surface with dry-run, fixture, approval, diagnostics, and worker artifact support;
  - the current gap is productization, not absence of infrastructure;
  - the main UI issues are card/rail competition, redundant metadata, and weak canvas priority on narrow layouts;
  - browser automation `domSnapshot()` is currently broken in this environment, so the evidence used visible clicks, screenshots, and bounded read-only DOM evaluation instead.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step1/20260707/baseline-note.md`
- Validation:
  - Read `apps/astrabridge-desktop/src/types.ts`.
  - Read `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`.
  - Read `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`.
  - Searched desktop and sidecar graph support paths with `rg`.
  - Performed click-driven navigation in the live in-app browser and captured screenshots.
  - Visually inspected the preserved screenshots.
- Blockers: None for Step 1.
- Next step: Step 2, Build Competitive Pattern Matrix.

### 2026-07-07 - Step 2 Build Competitive Pattern Matrix

- Completed: Researched the public product and repository surfaces for Dify, Flowise, Langflow, AutoGen Studio, n8n, LangSmith Studio, CrewAI, and Rivet.
- Completed: Converted that research into a decision-oriented matrix under `PRIVATE/agent-orchestration/productization/step2/20260707/competitive-pattern-matrix.md`.
- Completed: Classified concrete patterns as `adopt`, `adapt`, `defer`, or `reject` instead of leaving the research as a loose product summary.
- Completed: Identified the highest-priority patterns for AstraBridge:
  - one canonical graph contract shared by GUI and code,
  - file-backed graph review and rollback,
  - canvas-first authoring,
  - explicit prompt/schema/contract editing,
  - trace/debugger-first runtime inspection.
- Completed: Identified explicit rejection targets:
  - GUI-only orchestration with no versionable files,
  - cloud-first control-plane assumptions,
  - default deep recursive agent nesting,
  - canvas clutter from always-visible low-value text and stacked panels,
  - hidden prompt/schema/handoff contracts.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step2/20260707/competitive-pattern-matrix.md`
- Validation:
  - Read official docs and public repo entrypoints for Dify, Flowise, Langflow, AutoGen Studio, n8n, LangSmith Studio, CrewAI, and Rivet.
  - Verified the matrix includes source URLs, relevance notes, at least five adopt/adapt patterns, and at least three avoid/reject patterns.
- Blockers: None for Step 2.
- Next step: Step 3, Define Canonical Orchestration Graph Contract.

### 2026-07-07 - Step 3 Define Canonical Orchestration Graph Contract

- Completed: Designed the canonical orchestration graph contract in `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`.
- Completed: Chose a wrapper-and-compiler architecture:
  - canonical authoring contract = `AgentOrchestrationGraph`
  - short-term lowering target = current `TaskGraphDefinition`
- Completed: Defined first-class contract areas that are missing from the current task graph:
  - prompt templates and variables
  - tool policy
  - node input/output contracts
  - edge handoff contracts
  - graph-level defaults and depth limits
  - authoring-time UI metadata
- Completed: Wrote compatibility and migration guidance from current
  `TaskGraphDefinition` into the canonical contract.
- Completed: Added two example graph payloads:
  - `Code Fix / Test / Review`
  - `Provider Update / Smoke / Gate`
- Completed: Added a short step validation note under
  `PRIVATE/agent-orchestration/productization/step3/20260707/validation-note.md`.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step3/20260707/validation-note.md`
- Validation:
  - Read `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`.
  - Read `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md`.
  - Read `PLAN/MULTI_AGENT_TASK_GRAPH_SCOPE_AND_UX_PRINCIPLES.md`.
  - Verified the new contract document explicitly states wrapper vs extension,
    includes two examples, and includes compatibility and migration notes.
- Blockers: None for Step 3.
- Next step: Step 4, Implement Schema Validation And Migration Skeleton.

### 2026-07-07 - Step 4 Implement Schema Validation And Migration Skeleton

- Completed: Added canonical orchestration graph validation in `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`.
- Completed: Added legacy lift and minimal lowering helpers:
  - `lift_task_graph_to_agent_orchestration_graph`
  - `lower_agent_orchestration_graph_to_task_graph`
- Completed: Enforced Step 4 contract checks for:
  - schema version
  - node and edge id uniqueness
  - role/kind compatibility
  - routing references
  - prompt validation
  - output schema references
  - same-node edge rejection
  - cycle rejection
  - graph depth limit
  - high-risk safety approval requirements
- Completed: Added focused tests in `apps/astrabridge-sidecar/tests/test_agent_orchestration_contract.py`.
- Completed: Verified all existing task-graph fixtures can be lifted into canonical orchestration graphs with explicit migration warnings and lowered back into valid `astrabridge-task-graph-v1` payloads.
- Completed: Preserved Step 4 evidence under `PRIVATE/agent-orchestration/productization/step4/20260707/`, including:
  - `validation-note.md`
  - `test-agent-orchestration-contract.txt`
  - `test-task-graph-contract.txt`
- Files changed:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
  - `apps/astrabridge-sidecar/tests/test_agent_orchestration_contract.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step4/20260707/validation-note.md`
- Validation:
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agent_orchestration_contract.py`
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_contract.py`
- Preserved raw command outputs in the Step 4 evidence root.
- Blockers: None for Step 4.
- Next step: Step 5, Add Code-First Graph File Format.

### 2026-07-07 - Step 5 Add Code-First Graph File Format

- Completed: Added a code-first graph file-format module in `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`.
- Completed: Chose `JSON` as the first supported graph file format, with:
  - explicit canonical graph schema version embedded in every file
  - stable pretty-printed serialization
  - file load/write helpers with extension validation
  - a format spec helper for later CLI or API integration
- Completed: Added example graph coverage for the required workflows:
  - `examples/agent-orchestration/code_fix_review.json`
  - `examples/agent-orchestration/provider_update_smoke.json`
  - `examples/agent-orchestration/fanout_research_synthesis.json`
- Completed: Added focused tests in `apps/astrabridge-sidecar/tests/test_agent_orchestration_file_format.py` covering:
  - format spec
  - example catalog coverage
  - repository example file parity
  - text round-trip
  - file round-trip
  - invalid extension / invalid JSON failure behavior
- Completed: Verified the example graphs still lower into valid `astrabridge-task-graph-v1` payloads through the existing lowering path.
- Completed: Preserved Step 5 evidence under `PRIVATE/agent-orchestration/productization/step5/20260707/`, including:
  - `validation-note.md`
  - `test-agent-orchestration-file-format.txt`
  - `test-agent-orchestration-contract.txt`
  - `example-file-list.txt`
- Files changed:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
  - `apps/astrabridge-sidecar/tests/test_agent_orchestration_file_format.py`
  - `examples/agent-orchestration/code_fix_review.json`
  - `examples/agent-orchestration/provider_update_smoke.json`
  - `examples/agent-orchestration/fanout_research_synthesis.json`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step5/20260707/validation-note.md`
- Validation:
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agent_orchestration_file_format.py`
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agent_orchestration_contract.py`
- Preserved raw command outputs and the repository example file inventory in the Step 5 evidence root.
- Blockers: None for Step 5.
- Next step: Step 6, Add Graph Lint, Dry-Run, And Diff Commands.

### 2026-07-07 - Step 6 Add Graph Lint, Dry-Run, And Diff Commands

- Completed: Added lint, dry-run, and diff report builders in `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`.
- Completed: Added a local command entrypoint in `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py`.
- Completed: Provided one documented command per acceptance path:
  - `python -m astrabridge_sidecar.agent_orchestration_cli lint <graph.json>`
  - `python -m astrabridge_sidecar.agent_orchestration_cli dry-run <graph.json>`
  - `python -m astrabridge_sidecar.agent_orchestration_cli diff <old-graph.json> <new-graph.json>`
- Completed: Added focused tests in `apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py` covering:
  - lint success
  - dry-run success
  - dry-run warning behavior
  - semantic diff detection
  - CLI JSON + markdown output
- Completed: Preserved sample lint/dry-run/diff reports under `PRIVATE/agent-orchestration/productization/step6/20260707/`.
- Files changed:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py`
  - `apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step6/20260707/validation-note.md`
- Validation:
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agent_orchestration_checks.py`
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agent_orchestration_file_format.py`
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agent_orchestration_contract.py`
  - Ran the real CLI commands against repository example graphs and preserved their JSON + markdown outputs.
- Blockers: None for Step 6.
- Next step: Step 7, Implement Import And Export Round Trip In The App.

### 2026-07-08 - Plan Update For Simulated Product Operation And Screenshot-First UI Review

- Completed: Tightened the plan so future agents must prove GUI behavior by operating the visible product surface through real simulated clicks, typing, dragging, hover, scroll, expand/collapse, resize, and reload, instead of using in-page script mutation, API shortcuts, or store patching.
- Completed: Raised the evidence bar for UI work by requiring a denser screenshot trail, a written interaction transcript, a fresh-open persistence pass, and a constrained-width or alternate-viewport pass for layout-affecting changes.
- Completed: Added a mandatory UI review checklist so future agents must explicitly inspect screenshots for card stacking, oversized fonts, low-semantic text, redundant information, detached controls, confusing icons, unnecessary framing, clipping, cramped inspectors, and lack of canvas priority.
- Files changed: `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, evidence convention, GUI quality gate, click-driven review loop, and execution rules before editing.
  - Verified the updated plan now makes visible product interaction the only valid primary proof path for UI-facing work and makes screenshot review an explicit implementation discipline rather than loose documentation.
- Blockers: None.
- Next step: Step 11, Productize Edge Wiring And Communication Contracts.

### 2026-07-08 - Plan Update For Click-First Product Proof And Screenshot Density

- Completed: Tightened the UI evidence rules again so future agents must preserve screenshots not only for entry/save/reload states, but also after meaningful canvas drags, panel expand/collapse actions, viewport changes, and selection changes that materially affect the visible workflow.
- Completed: Added an explicit rule that any mutating API call, sidecar endpoint, store patch, fixture preload, or script shortcut used during debugging is non-acceptance evidence until the same result is reproduced from the real product surface by simulated interaction.
- Completed: Required future progress logs to disclose any such shortcut explicitly instead of silently mixing backend mutation with claimed GUI proof.
- Files changed: `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for evidence convention, click-driven review loop, and execution rules before editing.
  - Verified the updated plan now makes click-first proof, screenshot density, and explicit shortcut disclosure part of the written contract for future agents.
- Blockers: None.
- Next step: Step 11, Productize Edge Wiring And Communication Contracts.

### 2026-07-08 - Step 11 Productize Edge Wiring And Communication Contracts

- Completed: Proved visible edge creation, contract editing, invalid-contract blocking, reload persistence, dry-run validation, export, and hover-style edge summary behavior through the running app in the in-app browser.
- Completed: Preserved the Step 11 evidence pack and wrote the final validation note under `PRIVATE/agent-orchestration/productization/step11/20260708/validation-note.md`.
- Completed: Diagnosed a real blocker where the old `8810` sidecar process still exported a stale 2-edge orchestration payload even though the persisted task graph contained more edges.
- Completed: Fully restarted the `8810` sidecar, reloaded the app, re-exported the graph through visible controls, and verified that `graph_provider_update_smoke_step11_v3.json` now contains the current `5`-edge orchestration graph.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step11/20260708/validation-note.md`
- Validation:
  - Ran `node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx` from `apps\astrabridge-desktop`
  - Ran `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  - Ran `cmd /c npm run build` from `apps\astrabridge-desktop`
  - Performed click-driven validation in the running app for edge save, invalid contract, reload, dry-run, export, post-restart export, and post-restart dry-run.
- Evidence:
  - `PRIVATE/agent-orchestration/productization/step11/20260708/validation-note.md`
  - `PRIVATE/agent-orchestration/productization/step11/20260708/step11-04-invalid-contract.png`
  - `PRIVATE/agent-orchestration/productization/step11/20260708/step11-18-dry-run-rerun-pass.png`
  - `PRIVATE/agent-orchestration/productization/step11/20260708/step11-24-export-modal-v3.png`
  - `PRIVATE/agent-orchestration/productization/step11/20260708/step11-25-export-complete-v3.png`
  - `PRIVATE/agent-orchestration/productization/step11/20260708/step11-26-final-dry-run-after-restart.png`
  - `PRIVATE/agent-orchestration/productization/step11/20260708/step11-27-edge-hover.png`
- UI issues observed from screenshots:
  - the latest-run dock can remain stale until the next dry-run refreshes it
  - export paths are workspace-relative and still easy to misread from the UI alone
  - the edge hover chip is concise but cramped for longer labels
  - the validation graph accumulated exploratory persisted edges, which proves persistence/export but also shows the need for an easier cleanup path
- Blockers resolved:
  - normalized `required_output_only` artifact handling so the placeholder `required_output` no longer blocks dry-run for these edges
  - ensured fresh exports include task-graph edges that were missing from stale embedded orchestration metadata once the sidecar process was fully restarted
- Next step: Step 12, Add Prompt, Schema, And Contract Editors.

### 2026-07-08 - Plan Update For Product-Surface Simulation And Screenshot-Dense UI Review

- Completed: Tightened the plan again so future agents must treat the live in-app browser surface as the primary workbench for UI-facing steps, not merely as a final preview after backend mutation.
- Completed: Made it explicit that "simulate the product" means the implementing agent must personally drive visible controls through click, type, hover, drag, scroll, expand/collapse, resize, reload, reopen, and menu selection instead of depending on API-first state changes.
- Completed: Raised the screenshot discipline again by requiring denser screenshot cadence whenever there is doubt about whether a layout change, state transition, or canvas interaction is obvious enough from the current evidence.
- Completed: Strengthened execution-log requirements so future agents must disclose that they operated the visible surface themselves and must say whether screenshot cadence was sufficient to catch intermediate UI issues early.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the current plan sections for constraints, GUI gate, click-driven review loop, and execution rules before editing.
  - Verified the updated plan now treats simulated product operation and screenshot-dense UI review as part of the implementation loop itself rather than as a weak acceptance add-on.
- Blockers: None.
- Next step: Step 16, Add Safety, Versioning, And Rollback Boundaries.

### 2026-07-08 - Plan Update For Agent-Self-Operated Click Validation

- Completed: Tightened the plan so future agents must personally operate the visible product surface during validation instead of relying on sidecar APIs, store mutation, fixture seeding, console injection, or another agent's prior UI state.
- Completed: Added explicit evidence requirements for hover states, collapse/expand states, and narrow-width states because those are where the current UI most often exposes clutter, weak canvas priority, oversized text, and low-semantic noise.
- Completed: Required screenshot-review notes to name at least one UI choice that was simplified, removed, or rejected after screenshot inspection so the review loop cannot degrade into blind screenshot collection.
- Completed: Strengthened the progress-log contract so future agents must explicitly say they personally clicked through the acceptance path and must list which density-sensitive states they exercised.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Re-read `C:\Users\cyz19\.codex\skills\durable-handoff-plan\SKILL.md`.
  - Re-read the plan sections for constraints, evidence convention, GUI quality gate, and execution rules before editing.
  - Verified the updated plan now makes self-operated click validation and screenshot-driven UI critique a hard requirement rather than a soft preference.
- Blockers: None.
- Next step: Step 16, Add Safety, Versioning, And Rollback Boundaries.

### 2026-07-08 - Step 16 Safety, Versioning, And Rollback Boundaries (Partial Progress)

- Completed in this round:
  - Preserved visible in-app-browser evidence for the first unstable snapshot attempt on the older `8811` sidecar session.
  - Confirmed through visible interaction on a fresh `8812` sidecar session that the graph workspace can still be opened and that `快照` succeeds from the product surface, producing a success banner and snapshot chips.
  - Preserved the current Step 16 validation note under `PRIVATE/agent-orchestration/productization/step16/20260708/validation-note.md`.
  - Ran the focused secret scan and preserved `PRIVATE/agent-orchestration/productization/step16/20260708/secret-scan-report.json` with `status = pass` and `finding_count = 0`.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step16/20260708/validation-note.md`
- Validation:
  - Used the in-app browser as the primary proof surface.
  - Preserved screenshots for the unstable `8811` snapshot attempt, the restored `8812` graph-open path, and the successful visible snapshot creation on `8812`.
  - Ran `python D:\AstraBridge\scripts\agent_orchestration_secret_scan.py D:\AstraBridge\.astrabridge\task-graph\snapshots D:\AstraBridge\PRIVATE\agent-orchestration\productization\step16\20260708 --output D:\AstraBridge\PRIVATE\agent-orchestration\productization\step16\20260708\secret-scan-report.json`
- Blockers:
  - Step 16 is still incomplete because the remaining visible `对比 -> 回滚 -> reload/re-open` chain was repeatedly interrupted by in-app browser control resets and by instability in the earlier `8811` sidecar session.
  - The visible graph edit path also needs one shorter, more stable mutation sequence before the diff and rollback clicks can be closed confidently from the product surface.
- Next step: Step 16, Add Safety, Versioning, And Rollback Boundaries. Resume from the fresh `8812` sidecar session, confirm one persisted visible graph edit, then complete visible `对比`, visible `回滚`, and post-rollback re-open proof.

### 2026-07-08 - Step 16 Safety, Versioning, And Rollback Boundaries (Environment Blocker Captured)

- Completed in this round:
  - Re-checked the desktop save-entry path in `apps/astrabridge-desktop/src/App.tsx` and confirmed the node and edge inspector still persist through explicit save actions rather than hidden blur-only behavior.
  - Re-checked `sidecar-8812.out.log` and confirmed that `POST /api/task-graphs/snapshot/diff` answered successfully at least once on the healthy `8812` sidecar, so the remaining gap is visible proof, not missing backend support.
  - Preserved two new screenshots showing that the accessible top-level window had drifted away from the expected AstraBridge task-graph surface:
    - `step16-18-codex-window-current.png`
    - `step16-19-codex-window-after-nav.png`
  - Rewrote `PRIVATE/agent-orchestration/productization/step16/20260708/validation-note.md` into a clean ASCII record so future agents can continue Step 16 without mojibake or ambiguous next actions.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step16/20260708/validation-note.md`
- Validation:
  - Read the current desktop save-handler path in `apps/astrabridge-desktop/src/App.tsx`.
  - Re-read the current Step 16 validation note and evidence directory.
  - Verified via sidecar log review that `8812` handled snapshot creation and compare requests successfully, while the visible proof surface remained the unresolved gap.
  - Preserved fresh blocker screenshots rather than claiming a synthetic pass from backend evidence.
- Blockers:
  - The thread-reported in-app browser URL and the accessible visible desktop window no longer matched the same live AstraBridge surface.
  - Browser-control reacquisition kept timing out after earlier resets, preventing a trustworthy continuation of the visible `compare -> rollback -> reopen` chain in this round.
- Next step: Step 16, Add Safety, Versioning, And Rollback Boundaries. Re-establish a trustworthy visible AstraBridge surface first, then resume the missing `visible edit -> compare -> rollback -> reopen` chain on the healthy `8812` sidecar.

### 2026-07-08 - Step 16 Safety, Versioning, And Rollback Boundaries (Completed)

- Completed in this round:
  - Fixed snapshot compare and rollback so they resolve snapshot artifacts from the task's real workspace instead of assuming the currently projected workspace.
  - Shortened newly written snapshot artifact filenames so rollback snapshot writes no longer fail on Windows path length.
  - Added focused regression coverage for cross-project snapshot resolution and rollback in `apps/astrabridge-sidecar/tests/test_task_graph_api.py`.
  - Re-established the visible in-app-browser product surface on sidecar `8812` and completed the visible `对比 -> 回滚 -> reload/re-open` chain on `Fan-out / Fan-in Research`.
  - Preserved fresh evidence showing:
    - visible compare result with `Status: changed` and `node_routing_changed`,
    - visible rollback result with `Rollback to Before save: Fan-out / Fan-in Research v15`,
    - post-reload re-open proof on the graph workspace.
  - Updated `PRIVATE/agent-orchestration/productization/step16/20260708/validation-note.md` to a completed record and refreshed the focused secret scan report with `status = pass`.
- Files changed:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step16/20260708/validation-note.md`
  - `PRIVATE/agent-orchestration/productization/step16/20260708/secret-scan-report.json`
- Validation:
  - `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  - Visible in-app-browser click path:
    - open `Provider Switch Live 20260622-224524`
    - open `Step 11 source for compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run`
    - enter `任务图`
    - select `Before save: Fan-out / Fan-in Research v14`
    - click `对比`
    - confirm visible diff result with `Status: changed` and `node_routing_changed`
    - click `回滚`
    - reload and re-open `任务图`
    - confirm the rollback snapshot chip remains visible in the reopened workspace
  - Supplemental backend confirmation after the visible path:
    - current `node_supervisor` route restored to `provider_id = qwen`, `model_id = qwen3-coder-plus`, `reasoning_effort = medium`
  - Evidence preserved under `PRIVATE/agent-orchestration/productization/step16/20260708/`, including:
    - `step16-27-after-visible-rollback.png`
    - `step16-28-reopened-rollback-graph.png`
    - updated `validation-note.md`
    - updated `secret-scan-report.json`
- Blockers:
  - None for Step 16 completion.
- Next step: Step 17, Add End-To-End Click-Driven Dogfood Scenarios.

### 2026-07-09 - Step 17 End-To-End Click-Driven Dogfood Scenarios (Partial Progress)

- Completed in this round:
  - Re-established the live in-app-browser product surface and resumed Step 17 directly from the visible AstraBridge app rather than backend shortcuts.
  - Preserved a fresh Step 17 evidence root at `PRIVATE/agent-orchestration/productization/step17/20260709/`.
  - Reproduced two real UI blockers on the visible `Code Fix / Test / Review` workflow:
    - entering `任务图` could inherit stale `chat-canvas` scroll and push the graph inspector toggle above the viewport,
    - after opening the node inspector, the save actions rendered below the fold with no usable panel scroll path.
  - Fixed the first blocker in `apps/astrabridge-desktop/src/App.tsx` by resetting the `chat-canvas` scroll position whenever the task-graph workspace opens in chat view.
  - Fixed the second blocker in `apps/astrabridge-desktop/src/styles.css` by making the task-graph sidebar and inspector independently scrollable and by adding `min-height: 0` to the panel bodies.
  - Re-proved the first fix from the visible UI:
    - reloaded the app,
    - re-entered `任务图`,
    - confirmed the chat canvas returned to `scrollTop = 0`,
    - confirmed the `检查器 / 展开面板` toggle returned into the visible viewport.
  - Re-instantiated `Code Fix / Test / Review`, reopened the node inspector from the visible surface, and re-edited the `Plan Fix` prompt textarea after the scroll-reset fix.
  - Wrote the current round evidence note to `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`.
- Files changed:
  - `apps/astrabridge-desktop/src/App.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`
- Validation:
  - `node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx`
  - `cmd /c npm run build`
  - Visible in-app-browser proof included:
    - open the current task from the sidebar,
    - enter `任务图`,
    - open the template rail,
    - instantiate `Code Fix / Test / Review`,
    - select `Plan Fix`,
    - expand `检查器`,
    - edit the node prompt,
    - reload and re-enter `任务图` after the scroll reset fix,
    - confirm the inspector toggle is no longer rendered above the viewport.
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step17/20260709/`, including:
  - `step17-20-after-reload-post-fix.png`
  - `step17-21-reenter-task-graph-post-fix.png`
  - `step17-23-codefix-instantiated-final.png`
  - `step17-24-codefix-inspector-open-final.png`
  - `step17-25-codefix-prompt-edited.png`
  - `step17-27-after-inspector-scroll-fix-reload.png`
  - `validation-note.md`
- Blockers:
  - Step 17 is still incomplete because the full end-to-end visible chain has not yet been re-proven for all three required workflows.
  - `Code Fix / Test / Review` still needs the post-fix visible `保存节点 -> 边编辑 -> Dry-run -> 夹具运行 -> trace -> artifact -> export -> reload` chain.
  - `Provider Update / Smoke / Gate` has not yet been exercised in this Step 17 evidence pack.
  - `Fan-out / Fan-in Research` has not yet been freshly re-run under the latest scroll/layout fixes in this Step 17 evidence pack.
- Next step: Step 17, Add End-To-End Click-Driven Dogfood Scenarios. Resume from the live `Code Fix / Test / Review` workspace on sidecar `8812`, finish the newly unblocked save path, then complete the remaining code-fix, provider-update, and fan-out scenario packs from the visible product surface.

### 2026-07-09 - Step 17 End-To-End Click-Driven Dogfood Scenarios (Graph Persistence Repair Progress)

- Completed in this round:
  - Reproduced a real visible `Code Fix / Test / Review` failure where `Dry-run` reported `Graph not found.` immediately after visible template instantiation.
  - Diagnosed the persistence bug after the visible failure and found that new task graphs could be dropped when the task had already reached `GRAPH_DEFINITION_LIMIT`.
  - Fixed `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py` so incoming graph definitions now win on both ordering and content during `_save_task()` merge.
  - Added a regression test in `apps/astrabridge-sidecar/tests/test_task_graph_api.py` proving that the newest instantiated graph remains retained and addressable by `graph_id` even when the task is already at the definition limit.
  - Restarted sidecar `8812` on the current source tree, preserved fresh restart logs under the Step 17 evidence root, reloaded the live in-app browser surface, and re-ran visible `Code Fix / Test / Review -> Dry-run`.
  - Re-proved from the visible UI that the previous `Graph not found.` failure is gone; the same click path now reaches a real dry-run result surface with:
    - overall status `blocked`,
    - visible node/edge counts,
    - visible diagnostics,
    - visible report link,
    - visible latest-run entry `dry_run_blocked`.
- Files changed:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`
- Validation:
  - `python -m unittest D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  - `cmd /c npm run build` from `apps\astrabridge-desktop`
  - Visible in-app-browser proof included:
    - reload the live app after restarting sidecar `8812`
    - re-enter `任务图`
    - open the template rail
    - instantiate `Code Fix / Test / Review`
    - click visible `Dry-run`
    - confirm the result is a real dry-run panel instead of `Graph not found.`
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step17/20260709/`, including:
  - `step17-52-codefix-dry-run-triggered.png`
  - `step17-53-after-sidecar-restart-reload.png`
  - `step17-54-reenter-task-graph-after-sidecar-restart.png`
  - `step17-55-template-open-after-sidecar-restart.png`
  - `step17-56-codefix-instantiated-after-sidecar-restart.png`
  - `step17-57-codefix-after-extra-wait-post-restart.png`
  - `step17-58-codefix-dry-run-after-sidecar-fix.png`
  - `sidecar-8812-restart.out.log`
  - `sidecar-8812-restart.err.log`
  - updated `validation-note.md`
- UI issues observed from screenshots:
  - the template rail still dominates vertical space once opened and continues to compete with the canvas
  - the code-fix dry-run is now functionally real, but the node-save feedback remains weak; the UI still does not make it obvious enough when a save actually lands
  - the canvas still allocates prime space to the expanded template rail during execution, which is too dense for the end-state UX
- Blockers:
  - Step 17 is still incomplete because only the `Code Fix / Test / Review` instantiate and dry-run portion has been re-closed after the persistence repair.
  - The remaining visible `Code Fix / Test / Review` chain still needs edge edit, fixture run, trace, artifact open, export, and reload/re-open verification.
  - `Provider Update / Smoke / Gate` still has not been exercised in this Step 17 evidence pack.
  - `Fan-out / Fan-in Research` still needs a fresh end-to-end replay under the latest layout and persistence fixes.
- Next step: Step 17, Add End-To-End Click-Driven Dogfood Scenarios. Resume from the current visible `Code Fix / Test / Review` graph on sidecar `8812`, close `edge edit -> fixture run -> trace -> artifact -> export -> reload`, then complete `Provider Update / Smoke / Gate` and a fresh `Fan-out / Fan-in Research` pass from the visible product surface.

### 2026-07-09 - Step 17 End-To-End Click-Driven Dogfood Scenarios (Code-Fix Export And Reopen Progress)

- Completed in this round:
  - Stayed on the live in-app-browser product surface and resumed from the already-open `Code Fix / Test / Review` graph instead of using backend shortcuts.
  - Preserved a fresh baseline screenshot before the next visible `trace -> artifact -> export -> reload` chain.
  - Clicked visible `导出`, confirmed the visible export modal opened, and completed the visible export from the modal's `Export` action.
  - Verified that the export wrote a real JSON file under the live workspace:
    - `D:\AstraBridge\PRIVATE\demo-runs\provider-switch-live-20260622-224524\workspace\PRIVATE\agent-orchestration\productization\step7\20260707\graph-20260709T004851100362-a217e0.json`
  - Reloaded the live app, returned to the conversation workspace, and re-opened the same `任务图` from the visible topbar.
  - Re-expanded `最近一次运行`, opened the visible `Run summary` artifact into the file panel, and re-opened the visible `时间线` trace section after reload.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`
- Validation:
  - Visible in-app-browser proof included:
    - keep the live `Code Fix / Test / Review` graph open
    - click visible `导出`
    - confirm the visible export modal
    - click visible `Export`
    - confirm the export-complete banner
    - reload the live app
    - re-open `任务图`
    - expand `最近一次运行`
    - click visible `Run summary`
    - confirm the run-summary artifact opens in the file panel
    - click visible `时间线`
    - confirm the trace section expands
  - Supplemental filesystem confirmation after the visible path:
    - `Get-ChildItem -Path D:\AstraBridge -Recurse -Filter 'graph-20260709T004851100362-*.json'`
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step17/20260709/`, including:
  - `step17-69-codefix-current-graph-before-trace-artifact-export-reload.png`
  - `step17-71-codefix-export-clicked.png`
  - `step17-72-codefix-export-complete.png`
  - `step17-73-codefix-after-reload.png`
  - `step17-74-codefix-task-graph-reopened-after-reload.png`
  - `step17-75-codefix-latest-run-expanded-after-reload.png`
  - `step17-76-codefix-run-summary-opened-after-reload.png`
  - `step17-77-codefix-timeline-trace-expanded.png`
  - updated `validation-note.md`
- UI issues observed from screenshots:
  - the export dialog still mixes English copy into the Chinese workflow and feels out of place
  - `正在加载任务图...` can linger while the graph is already visible behind it, which reads like a stale loading overlay
  - opening artifacts in the right file panel while the latest-run dock is expanded still compresses the canvas too aggressively
  - the latest-run dock hierarchy is functional but visually dense, so trace and artifact affordances remain harder to scan than they should be
- Blockers:
  - Step 17 is still incomplete because `Code Fix / Test / Review` still needs one stronger current-pack fixture-run re-trigger and at least one more visible artifact-open path beyond run summary.
  - `Provider Update / Smoke / Gate` still has not been exercised in this Step 17 evidence pack.
  - `Fan-out / Fan-in Research` still has not been freshly replayed in this Step 17 evidence pack after the latest UI and persistence fixes.
- Next step: Step 17, Add End-To-End Click-Driven Dogfood Scenarios. Stay on sidecar `8812`, finish the remaining visible `Code Fix / Test / Review` run/artifact closure, then execute `Provider Update / Smoke / Gate` and `Fan-out / Fan-in Research` from the visible product surface.

### 2026-07-09 - Step 17 End-To-End Click-Driven Dogfood Scenarios (Code-Fix Fixture Rerun Progress)

- Completed in this round:
  - Stayed on the same live in-app-browser `Code Fix / Test / Review` graph and re-triggered a fresh visible fixture run for the current Step 17 pack.
  - Preserved a before-shot, a `RUNNING` shot, and a returned-to-`COMPLETED` shot for the current-pack rerun.
  - Confirmed from the visible latest-run dock that the rerun produced a new run id:
    - `graph-run-fixture-20260709T011120545551-302282`
  - Expanded `Worker 输出` and scrolled the latest-run dock until concrete artifact chips for the rerun were visible.
  - Preserved evidence showing the current rerun exposed worker artifacts such as `structured_json: output.json`, `text_report: summary.md`, and `structured_json: handoff.json`.
  - Attempted to close the second artifact-open path from those visible worker chips, but browser-kernel instability resumed before a clean final file-panel confirmation screenshot could be preserved.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`
- Validation:
  - Visible in-app-browser proof included:
    - keep the live `Code Fix / Test / Review` graph open
    - click visible `夹具运行`
    - confirm the latest-run dock switches to `RUNNING`
    - wait for the same visible dock to return to `COMPLETED`
    - expand `Worker 输出`
    - scroll until current-run artifact chips become visible
    - attempt worker-artifact opening from the visible chips
  - No backend mutation was used as acceptance evidence for the rerun itself.
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step17/20260709/`, including:
  - `step17-78-codefix-before-fixture-rerun.png`
  - `step17-79-codefix-fixture-rerun-triggered.png`
  - `step17-80-codefix-fixture-rerun-completed.png`
  - `step17-81-codefix-worker-outputs-expanded.png`
  - `step17-82-codefix-worker-outputs-scrolled-into-view.png`
  - `step17-83-codefix-worker-output-artifact-opened.png`
  - updated `validation-note.md`
- UI issues observed from screenshots:
  - the latest-run dock becomes noticeably too dense once current-run worker artifact chips are exposed
  - the dock scrollbar is too easy to miss, which weakens discoverability of the deeper worker-output section
  - keeping the right file panel open while the dock expands still compresses the canvas more than it should
- Blockers:
  - Step 17 is still incomplete because the second artifact-open path from the current rerun was attempted but not fully re-confirmed with a clean final file-panel screenshot after browser-kernel resets resumed.
  - `Provider Update / Smoke / Gate` still has not been exercised in this Step 17 evidence pack.
  - `Fan-out / Fan-in Research` still has not been freshly replayed in this Step 17 evidence pack after the latest UI and persistence fixes.
- Next step: Step 17, Add End-To-End Click-Driven Dogfood Scenarios. Re-enter the same `Code Fix / Test / Review` graph on sidecar `8812`, close one clean worker-artifact file-panel confirmation from the current rerun, then move to `Provider Update / Smoke / Gate`.

### 2026-07-09 - Step 17 End-To-End Click-Driven Dogfood Scenarios (Code-Fix Artifact Closure And Provider-Update Progress)

- Completed in this round:
  - Closed the missing second artifact-open path for `Code Fix / Test / Review` by confirming that the visible file panel switched to:
    - `PRIVATE/task-graph/workers/graph-run-fixture-20260709T011120545551-302282/node_code_fix/output.json`
  - Preserved a fresh screenshot for that code-fix artifact-panel confirmation.
  - Switched workflows from the visible template rail and instantiated `Provider Update / Smoke / Gate`.
  - Re-proved that the provider-update graph renders on the canvas with:
    - `Discover Provider Update`
    - `Generate Smoke Matrix`
    - `Manual Promotion Gate`
  - Ran a visible `Dry-run` on the provider-update graph and confirmed a real `DRY_RUN_BLOCKED` result with blocked extractor/validator nodes and concrete missing-profile diagnostics.
  - Ran a visible provider-update fixture run and confirmed a fresh current-pack fixture execution path.
  - Confirmed via workspace filesystem inspection that the provider-update fixture run wrote fresh run roots:
    - `graph-run-fixture-20260709T012217075220-c2eb59`
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`
- Validation:
  - Visible in-app-browser proof included:
    - click current-run `output.json` from code-fix `Worker 输出`
    - confirm file-panel content switches to `node_code_fix/output.json`
    - expand the template rail
    - select `Provider Update / Smoke / Gate`
    - click `实例化模板`
    - click visible `Dry-run`
    - confirm `DRY_RUN_BLOCKED` and the missing-profile diagnostics
    - click visible `夹具运行`
    - confirm the run starts and then completes
  - Supplemental filesystem confirmation after the visible path:
    - `Get-ChildItem ...\\PRIVATE\\task-graph\\fixture-run | Sort-Object LastWriteTime -Descending`
    - `Get-ChildItem ...\\PRIVATE\\task-graph\\workers | Sort-Object LastWriteTime -Descending`
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step17/20260709/`, including:
  - `step17-84-codefix-worker-output-panel-confirmed.png`
  - `step17-85-before-provider-update-switch.png`
  - `step17-86-provider-update-instantiated.png`
  - `step17-87-provider-update-dry-run.png`
  - `step17-88-provider-update-fixture-triggered.png`
  - `step17-89-provider-update-fixture-completed.png`
  - updated `validation-note.md`
- UI issues observed from screenshots:
  - the template rail plus the carried-over file panel compresses the provider-update canvas too aggressively during graph switching
  - the provider-update dry-run diagnostics are useful but still too dense in the central workspace
  - carrying over the prior code-fix artifact inside the right file panel while a different graph is active is visually confusing and suggests the file panel needs a stronger graph/run context indicator
- Blockers:
  - Step 17 is still incomplete because `Provider Update / Smoke / Gate` still needs export, reload/re-open proof, and one artifact-open path from its own run.
  - `Fan-out / Fan-in Research` still has not been freshly replayed in this Step 17 evidence pack after the latest UI and persistence fixes.
- Next step: Step 17, Add End-To-End Click-Driven Dogfood Scenarios. Re-enter the existing `Provider Update / Smoke / Gate` graph on sidecar `8812`, close `export -> reload -> artifact open`, then execute a fresh `Fan-out / Fan-in Research` replay plus constrained-width review.

### 2026-07-09 - Step 17 End-To-End Click-Driven Dogfood Scenarios (Provider-Update Closure And Fan-Out Replay Progress)

- Completed in this round:
  - Closed the missing `Provider Update / Smoke / Gate` export path, reload/re-open path, and run-summary artifact-open path.
  - Confirmed from the visible file panel that provider-update `Run summary` opened the current run artifact:
    - `fixture-run/graph-run-fixture-20260709T012217075220-c2eb59/report.md`
  - Confirmed the provider-update export also wrote a fresh graph file:
    - `graph-20260709T012010146878-386783.json`
  - Switched to `Fan-out / Fan-in Research` from the visible template rail and instantiated the fresh graph.
  - Triggered a fresh fan-out fixture run from the visible surface and confirmed by filesystem that it wrote a new run root:
    - `graph-run-fixture-20260709T013123046441-3bc83d`
  - Exported the fan-out graph, reloaded the live app, re-opened `任务图`, and preserved one constrained-width pass.
  - Confirmed the fan-out export also wrote a fresh graph file:
    - `graph-20260709T012845593603-d660e9.json`
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`
- Validation:
  - Visible in-app-browser proof included:
    - finish provider-update export
    - reload and re-open the provider-update graph
    - expand latest run and open `Run summary`
    - open the template rail
    - select and instantiate `Fan-out / Fan-in Research`
    - trigger a fresh fan-out fixture run
    - export the fan-out graph
    - reload and re-open the task graph
    - capture a constrained-width pass
  - Supplemental filesystem confirmation after the visible path:
    - `Get-ChildItem ...\\graph-*.json | Sort-Object LastWriteTime -Descending`
    - `Get-ChildItem ...\\fixture-run | Sort-Object LastWriteTime -Descending`
    - `Get-ChildItem ...\\workers | Sort-Object LastWriteTime -Descending`
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step17/20260709/`, including:
  - `step17-90-provider-update-export-complete.png`
  - `step17-91-provider-update-after-reload.png`
  - `step17-92-provider-update-task-graph-reopened.png`
  - `step17-93-provider-update-latest-run-expanded.png`
  - `step17-94-provider-update-run-summary-opened.png`
  - `step17-95-fanout-instantiated.png`
  - `step17-96-fanout-fixture-triggered.png`
  - `step17-98-fanout-export-complete.png`
  - `step17-99-fanout-after-reload.png`
  - `step17-100-fanout-task-graph-reopened.png`
  - `step17-101-fanout-constrained-width-pass.png`
  - updated `validation-note.md`
- UI issues observed from screenshots:
  - the template rail still crowds the canvas during graph switching
  - the constrained-width fan-out pass remains dense because the left rail and top controls consume too much prime space
  - the file panel still does not communicate graph/run ownership strongly enough when artifacts from different runs are opened across graph switches
- Blockers:
  - Step 17 is still incomplete because the fresh fan-out replay still lacks a clean artifact-open proof from its own `graph-run-fixture-20260709T013123046441-3bc83d` run.
  - `Code Fix / Test / Review` still has a thinner current-pack edge-edit re-proof than the rest of its now-closed chain.
- Next step: Step 17, Add End-To-End Click-Driven Dogfood Scenarios. Re-open the fresh fan-out run on sidecar `8812`, close one artifact-open proof from `graph-run-fixture-20260709T013123046441-3bc83d`, then decide whether the existing code-fix edge-edit evidence is sufficient or needs one final replay before Step 17 can be closed.

### 2026-07-09 - Step 17 End-To-End Click-Driven Dogfood Scenarios (Node Card Density Tightening Progress)

- Completed in this round:
  - Reviewed the live fan-out canvas screenshot and confirmed that node cards were still larger than necessary for the current single-label visual payload.
  - Tightened the task-graph node-card sizing contract in the desktop app by reducing:
    - node width from `104` to `96`
    - node height from `44` to `40`
    - node padding, spacing, badge size, and state-pill size
  - Switched node labels from a two-line clamp to a single-line ellipsis so the box shrink does not create uneven vertical growth.
  - Rebuilt the desktop app, re-ran the focused task-graph test suite, reloaded the live in-app browser surface, and re-opened the current `Fan-out / Fan-in Research` graph on sidecar `8812`.
  - Preserved a fresh screenshot showing that `Research Planner`, `Research Branch A`, `Research Branch B`, and `Research Synthesizer` now occupy less canvas area.
- Files changed:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
  - `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - `node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx`
  - `cmd /c npm run build`
  - Visible in-app-browser proof included:
    - reload the live app
    - re-open `任务图`
    - confirm the current fan-out graph renders with visibly smaller node cards
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step17/20260709/`, including:
  - `step17-102-node-cards-compacted.png`
- UI issues observed from screenshots:
  - the reduced node size is better, but `正在加载任务图...` can still linger over the canvas after nodes are already visible
  - the latest-run dock still steals a meaningful amount of bottom canvas height once expanded
- Blockers:
  - Step 17 is still incomplete because the fresh fan-out replay still lacks a clean artifact-open proof from `graph-run-fixture-20260709T013123046441-3bc83d`.
  - `Code Fix / Test / Review` still has a comparatively thin current-pack edge-edit re-proof.
- Next step: Step 17, Add End-To-End Click-Driven Dogfood Scenarios. Stay on sidecar `8812`, open one artifact from the fresh fan-out run, then decide whether code-fix needs one final edge-edit replay before Step 17 can be closed.

### 2026-07-09 - Step 17 End-To-End Click-Driven Dogfood Scenarios (Closure)

- Completed in this round:
  - Re-opened the live `Fan-out / Fan-in Research` graph on sidecar `8812`.
  - Expanded the latest-run dock for fresh run `graph-run-fixture-20260709T013123046441-3bc83d`.
  - Opened the visible `Run summary` artifact from that exact fresh run and confirmed the right file panel switched to:
    - `fixture-run/graph-run-fixture-20260709T013123046441-3bc83d/report.md`
    - markdown content headed by `Fixture run`
    - run id `graph-run-fixture-20260709T013123046441-3bc83d`
  - Audited the remaining `Code Fix / Test / Review` edge-edit concern and confirmed the existing visible screenshots already close that requirement:
    - `step17-59-codefix-before-edge-edit.png`
    - `step17-60-codefix-edge-inspector-open.png`
    - `step17-61-codefix-edge-dirty-before-save.png`
    - `step17-62-codefix-edge-scrolled-to-save.png`
    - `step17-63-codefix-edge-save-area.png`
    - `step17-64-codefix-edge-saved.png`
  - Determined that Step 17 acceptance is now met across all three workflow packs.
- Files changed:
  - `PRIVATE/agent-orchestration/productization/step17/20260709/validation-note.md`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Validation:
  - Visible in-app-browser proof included:
    - stay on the live fan-out graph
    - expand `最近一次运行`
    - click visible `Run summary`
    - confirm the right file panel shows `fixture-run/graph-run-fixture-20260709T013123046441-3bc83d/report.md`
  - Acceptance audit also confirmed that the earlier visible code-fix edge-edit screenshots already satisfy the edge-edit requirement for Step 17.
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step17/20260709/`, including:
  - `step17-104-fanout-run-summary-opened.png`
  - existing code-fix edge-edit screenshots `step17-59` through `step17-64`
- UI issues observed from screenshots:
  - `正在加载任务图...` can still linger above an already rendered graph after reload
  - the latest-run dock still compresses the lower canvas more than it should when expanded
  - the file panel still lacks a stronger graph/run ownership cue after graph switches
- Blockers:
  - none for Step 17 acceptance
- Next step: Step 18, Publish Maintainer Runbook And Product Boundary.

### 2026-07-09 - Step 18 Publish Maintainer Runbook And Product Boundary

- Completed in this round:
  - Added the final maintainer-facing runbook at `PLAN/AGENT_ORCHESTRATION_MAINTENANCE_RUNBOOK.md`.
  - Documented the orchestration product boundary, canonical ownership surfaces, compatibility policy, evidence roots, code-validation matrix, click-validation rules, migration rules, rollback rules, secret-scan requirements, and the screenshot-review loop.
  - Added an explicit `Do Not Fake The UI` section that forbids API/store mutation as sole proof for visible product work.
  - Added an explicit section for adding a new provider/model-sensitive agent template without hardcoding secrets.
  - Linked the runbook from:
    - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
    - `apps/astrabridge-sidecar/skills/agent-orchestration-operator/references/operating-surfaces.md`
  - Preserved Step 18 validation notes under `PRIVATE/agent-orchestration/productization/step18/20260709/`.
- Files changed:
  - `PLAN/AGENT_ORCHESTRATION_MAINTENANCE_RUNBOOK.md`
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
  - `apps/astrabridge-sidecar/skills/agent-orchestration-operator/references/operating-surfaces.md`
  - `PRIVATE/agent-orchestration/productization/step18/20260709/validation-note.md`
- Validation:
  - Focused content verification:
    - `rg -n "click validation|dry-run|rollback|secret|screenshot cadence|UI Quality Checklist|Do Not Fake The UI|Screenshot Review Loop|provider or model-sensitive agent template|in-app browser is the default proof environment|API calls.*must not be the primary happy-path proof" PLAN/AGENT_ORCHESTRATION_MAINTENANCE_RUNBOOK.md`
  - Focused secret scan:
    - `rg -n "api[_-]?key|bearer|authorization|cookie|sk-[A-Za-z0-9]|xoxb-|AKIA|BEGIN PRIVATE KEY|token" PLAN/AGENT_ORCHESTRATION_MAINTENANCE_RUNBOOK.md PRIVATE/agent-orchestration/productization/step18/20260709`
  - Validation review confirmed that the secret-scan hits were explanatory policy text only, not real secrets.
- Evidence preserved under `PRIVATE/agent-orchestration/productization/step18/20260709/`, including:
  - `validation-note.md`
- Remaining follow-on work:
  - stale `正在加载任务图...` overlay after some reloads
  - latest-run dock still compresses the lower canvas too aggressively
  - file panel still needs stronger graph/run ownership cues after graph switches
- Blockers:
  - none
- Next step: numbered plan complete; future work should start from the runbook plus the relevant follow-on product slice rather than reopening this plan.
