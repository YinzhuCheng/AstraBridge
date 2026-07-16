# Multi Agent Task Graph Canvas UX Target And Acceptance

## Purpose

This note turns the current canvas backlog into a concrete UI target for the remaining task-graph product work. It is the Step 2 reference for `PLAN/MULTI_AGENT_TASK_GRAPH_CANVAS_DOGFOOD_HANDOFF_PLAN.md`.

The intended interaction model is closer to an operator graph editor than a form-heavy dashboard. The canvas is the primary working surface. Sidebars, inspectors, and run details are secondary surfaces that should reveal detail only when the operator asks for it.

## Baseline Inputs

This target is based on:

- `PRIVATE/task-graph/canvas-dogfood/20260707/step1-baseline-validation-note.md`
- `PLAN/MULTI_AGENT_TASK_GRAPH_SCOPE_AND_UX_PRINCIPLES.md`
- `docs/TASK_GRAPH_MAINTAINER_RUNBOOK.md`

## Canvas-First Product Direction

1. The first user question should be answerable from the canvas:
   - what graph am I looking at
   - which node or edge is selected
   - what is running or blocked
   - where can I click next
2. The canvas should carry topology, selection, status, and direct manipulation.
3. The inspector should carry configuration depth, not primary discovery.
4. The left sidebar should help with graph scope and quick selection, not dominate the screen.
5. The latest-run and timeline surfaces should stay compact until the user expands them.

## Interaction Model Target

### Required canvas controls

- `Fit view`
- `Reset view`
- `Zoom in`
- `Zoom out`
- optional `Pan mode` only if it materially improves manipulation without confusing selection

These controls should live on or immediately adjacent to the canvas, use compact icon buttons, and remain visible without scrolling the page.

### Required direct graph interactions

- click a node to select it
- drag a node from the canvas and persist the new position
- click an edge from the canvas to inspect it
- start edge creation from the canvas or a node-local affordance, not only from a distant sidebar control
- distinguish node selection from edge selection without requiring the inspector to explain it

### Required view behavior

- the canvas area must feel visually dominant on desktop
- the default view should show the active graph with minimal hunting
- the operator should not need native scrollbars as the primary graph-navigation mechanism
- moving between graph editing and run inspection should not bury the canvas

## Information Placement Rules

### Keep on the canvas

- node label
- node role or kind
- compact node status signal
- selected node state
- edge direction
- selected edge state
- enough edge labeling to make selection direct when the graph is moderately dense
- compact canvas-local graph controls

### Keep in the left sidebar

- template list
- quick node list
- quick edge list
- graph-scoped shortcuts such as create-edge only if canvas-local creation is still not implemented yet

The left sidebar should be structured, collapsible, and compact. It should act as an outline, not as the main work surface.

### Keep in the right inspector

- editable node configuration
- editable edge context policy
- advanced context and artifact settings
- save and reset actions

The inspector should show only the high-value core fields by default. Secondary toggles, long artifact lists, resource refs, and checkbox-heavy settings should sit behind a disclosure control.

### Hover-only or tooltip-only

- unfamiliar icon names
- long template summaries
- full artifact paths
- enum-like labels that do not need to stay always visible

## Visible State Definitions

### Nodes

- `normal`: readable card, no ambiguity about role/kind, no excessive chrome
- `hover`: clear invitation to click or drag
- `selected`: stronger border, contrast, and focus treatment than hover
- `dragging`: obvious movement state without collapsing text readability
- `running`: visible active status that reads at a glance
- `blocked`: visually distinct warning or stop state
- `failed`: stronger failure state than blocked
- `completed`: calm success state
- `review-gated`: visibly waiting for human action, distinct from passive blocked

### Edges

- `normal`: direction and relationship are legible
- `hover`: easier to target than a thin static line
- `selected`: obvious active state that maps to the inspector
- `warning`: visible caution state
- `blocked`: visible stop state
- `failed`: stronger failure state than blocked
- `completed/pass`: visible healthy state without dominating the graph
- `review-gated`: distinguishable from ordinary dependency edges when used in a gate path

### Run surfaces

- `collapsed latest-run`: compact summary row or dock
- `expanded latest-run`: timeline, worker outputs, diagnostics, and review actions available
- `approval pending`: clear human action entry point
- `cancelled`: visible final state with durable evidence

## Screenshot Checkpoints

Any step that changes task-graph UI should preserve the screenshots that match its claim.

### Canvas navigation

- before using canvas controls
- after fit/reset or zoom interaction

### Node manipulation

- node visible before drag
- node mid-selection or selected
- node after drag
- node after reload persistence check

### Edge interaction

- edge before selection or creation
- selected edge state on canvas
- corresponding inspector state
- edge after reload persistence check

### Run interaction

- graph before run start
- visible running state
- visible cancellation, failure, or completion state
- latest-run collapsed and expanded states

### Narrow-width QA

- first narrow viewport after entering task graph
- graph area after required interaction
- any clipped or hidden primary action before a fix
- final narrow viewport after a fix

## Click-Driven Proof Recipes

### Recipe A: Open task graph

1. Start from the normal AstraBridge shell.
2. Click the visible `Task graph` control.
3. Verify the graph workspace rendered.
4. Capture the arrival screenshot.

### Recipe B: Navigate the canvas

1. Open task graph through Recipe A.
2. Click `Fit view`, `Zoom in`, `Zoom out`, or `Reset view`.
3. Verify the graph viewport changed visibly.
4. Capture before and after screenshots.

### Recipe C: Drag a node

1. Open task graph through Recipe A.
2. Ensure the target node is visible.
3. Click and drag the node on the canvas.
4. Save if required by the current UI.
5. Reload the app and re-enter task graph.
6. Verify the node remained in the new position.

### Recipe D: Select or create an edge

1. Open task graph through Recipe A.
2. Select an edge directly from the canvas, or begin edge creation from a canvas-local affordance.
3. Verify the inspector reflects the selected or draft edge.
4. Save the edge if edited or created.
5. Reload and verify persistence.

### Recipe E: Inspect run state

1. Open task graph through Recipe A.
2. Start a visible dry-run or fixture run from the toolbar.
3. Verify the latest-run surface updates.
4. Expand the run surface.
5. Open at least one worker output or diagnostic link when relevant.

## Acceptance Checklist For Upcoming Steps

### Step 3: Canvas navigation controls

- visible compact controls exist
- controls are reachable without page scrolling
- controls are proven by simulated clicks and screenshots

### Step 4: Node visual states

- selected, hover, dragging, running, blocked, failed, completed, and review-gated node states are distinguishable
- drag persistence is proven after reload

### Step 5: Edge visual states

- edges are directly selectable from the canvas
- selected and status states are visually distinct

### Step 6: Edge creation

- creation starts from the canvas or node-local affordance
- no API-based edge creation is used for acceptance

### Step 7: Sidebar and inspector

- canvas remains dominant on desktop
- long enum-like values are no longer visibly cramped in the tested path
- advanced settings remain reachable through disclosure

### Step 8 to Step 15: Run and dogfood work

- graph setup, run start, approval, cancellation, artifact inspection, and reload recovery are all proven from visible app controls
- screenshots and validation notes exist for each major transition

## Non-Goals For This Slice

- full freeform whiteboard behavior
- arbitrary external A2A visualization
- dense graph autolayout research
- replacing explicit artifact-first safety with a looser chat-style interaction model

## Next-Step Recommendation

Proceed to Step 3 with a narrow first implementation:

- add canvas navigation controls
- keep them canvas-local
- prove them by visible clicks before taking on deeper node and edge redesign
