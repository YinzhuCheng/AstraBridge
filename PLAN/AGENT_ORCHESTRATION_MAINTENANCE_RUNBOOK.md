# Agent Orchestration Maintenance Runbook

Last updated: 2026-07-09

## Purpose

This runbook is the maintainer-facing operating manual for AstraBridge agent
orchestration.

Use it when a future agent or maintainer needs to:

- extend the orchestration graph model
- add or revise node types, edge types, prompt editors, schema editors, or
  templates
- change the code-first graph file format or migration behavior
- validate GUI-visible orchestration behavior without faking the UI
- add a new provider/model-sensitive agent template without hardcoding secrets
- roll back a regressed orchestration change while preserving evidence

This runbook is the final handoff artifact for:

- `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`

## Product Boundary

Agent orchestration in AstraBridge is a bounded product surface, not a free-form
internal experiment area.

Keep these boundaries explicit:

- The user-facing product surface is:
  - task graph authoring in the desktop app
  - code-first orchestration graph files
  - dry-run, fixture execution, trace review, artifact review, import, export,
    compare, and rollback
- The canonical authoring model is `AgentOrchestrationGraph`.
- The execution runtime remains the existing `TaskGraphDefinition` engine after
  lowering.
- The orchestration layer must not bypass the existing runtime with a second
  hidden execution engine.
- Official OpenAI account login is not a product path.
- Secrets, vault material, cookies, bearer tokens, raw provider keys, and auth
  headers must never enter graph files, runbooks, screenshots, exported graphs,
  or preserved evidence.

## Governing Artifacts

Read these in order before changing orchestration behavior:

1. `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
2. `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`
3. `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
4. `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`
5. `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`
6. `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py`
7. `apps/astrabridge-sidecar/skills/agent-orchestration-operator/SKILL.md`
8. `apps/astrabridge-sidecar/skills/agent-orchestration-operator/references/operating-surfaces.md`

## Ownership And Compatibility Policy

### Canonical ownership

The canonical contract owner is:

- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`

The canonical file-format owner is:

- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`

The canonical validation and reporting owner is:

- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`

The canonical desktop authoring surface is:

- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`

### Compatibility rules

When changing orchestration behavior:

1. Do not introduce a second authoring contract.
2. Keep GUI authoring, code-first files, import/export, dry-run, and lowering
   aligned to the same `AgentOrchestrationGraph`.
3. Treat new fields as compatibility-sensitive:
   - if a field changes authoring semantics, update the contract doc, file
     format, examples, CLI checks, and UI if visible
   - if a field changes lowering semantics, update dry-run expectations and
     runtime evidence
4. Prefer additive evolution over breaking rewrites.
5. If a breaking change is unavoidable, add or update migration behavior and
   preserve before/after diff evidence.
6. Never claim compatibility from tests alone if exported graphs, reload,
   import, or visible UI behavior are not re-verified.

## Runtime Surface Map

Primary implementation surfaces:

- contract validation and lowering:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
- file parsing, serialization, and examples:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`
- lint, dry-run, diff, and markdown reporting:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`
- CLI entrypoint:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py`
- desktop graph workspace:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
- desktop integration and import/export dialogs:
  - `apps/astrabridge-desktop/src/App.tsx`
- server import/export handling:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`
- task persistence and runtime graph ownership:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`

## Evidence Roots

Preserve orchestration evidence under:

- `PRIVATE/agent-orchestration/productization/step*/<YYYYMMDD>/`

Useful baseline packs already in the repository:

- Step 7 import/export round-trip:
  - `PRIVATE/agent-orchestration/productization/step7/20260707/`
- Step 10 node inspector:
  - `PRIVATE/agent-orchestration/productization/step10/20260708/`
- Step 11 edge wiring and communication contracts:
  - `PRIVATE/agent-orchestration/productization/step11/20260708/`
- Step 12 prompt/schema editors:
  - `PRIVATE/agent-orchestration/productization/step12/20260708/`
- Step 13 runtime trace:
  - `PRIVATE/agent-orchestration/productization/step13/20260708/`
- Step 14 template library:
  - `PRIVATE/agent-orchestration/productization/step14/20260708/`
- Step 15 orchestration skill:
  - `PRIVATE/agent-orchestration/productization/step15/20260708/`
- Step 16 safety/versioning/rollback:
  - `PRIVATE/agent-orchestration/productization/step16/20260708/`
- Step 17 end-to-end workflow proof:
  - `PRIVATE/agent-orchestration/productization/step17/20260709/`

## Standard Change Workflow

### 1. Start from the smallest canonical surface

Pick the minimal owner surface that actually governs the change:

- contract-only change
- file-format change
- CLI/reporting change
- desktop authoring change
- runtime persistence or lowering change
- template/example change
- skill/rules change

Do not patch multiple layers blindly before locating the real owner.

### 2. Update code-first artifacts first when semantics changed

If semantics change, update as needed:

- `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`
- `examples/agent-orchestration/*.json`
- CLI output expectations
- tests covering contract, file format, or lowering

### 3. Run code validation

Minimum code-validation matrix for orchestration changes:

1. focused unit tests for the touched runtime or desktop slice
2. `lint` against at least one affected graph
3. `dry-run` against at least one affected graph
4. `diff` when an existing graph file changed
5. `npm run build` for desktop-visible changes
6. migration verification when schema or lowering semantics changed
7. rollback verification when compare/rollback or compatibility behavior changed

Suggested commands:

```powershell
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli lint <graph.json>
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli dry-run <graph.json>
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli diff <old-graph.json> <new-graph.json>
cmd /c npm run build
node .\node_modules\vitest\vitest.mjs run src\features\runtime\TaskGraphWorkspace.test.tsx
```

### 4. Run click validation for visible product work

When the change affects visible product behavior:

- the in-app browser is the default proof environment when the local product is
  already running there
- the primary acceptance path must use simulated clicks, typing, hover, drag,
  scroll, expand/collapse, resize, reopen, and reload
- API calls, sidecar endpoints, store patches, fixture preloads, localStorage
  writes, console injection, or direct persistence writes may diagnose failures
  later but must not be the primary happy-path proof

## Do Not Fake The UI

Forbidden as sole proof for visible product work:

- mutating app state through backend APIs before reproducing the same result in
  the visible product
- mutating store state through console injection or `page.evaluate(...)`
- writing task/graph state directly on disk and then claiming the UI works
- skipping import/export, dry-run, or reload because runtime logs look correct
- claiming a node, edge, trace, artifact, or compare/rollback flow works based
  only on test output or server logs

Acceptable proof means:

1. the visible product path was attempted first
2. screenshots were captured during the path
3. any backend diagnosis happened only after the visible behavior or failure was
   already preserved

## Screenshot Review Loop

Future agents must run this loop for every visible orchestration change:

1. capture the current surface
2. perform one meaningful visible interaction
3. capture the new state
4. inspect the screenshot for obvious UI debt
5. critique what is cluttered, oversized, redundant, detached, clipped, or
   hiding the canvas
6. fix the highest-value issue
7. reload or reopen the product and prove the result again
8. either continue iterating or explicitly log the remaining debt

Do not wait until the end of a step to look at screenshots.

## Screenshot Cadence

Minimum screenshot cadence for visible orchestration work:

- before change
- entry into the target orchestration surface
- node or edge selection state
- during the key edit or action
- after save, validation, or run-state change
- after artifact open, trace expand, compare, rollback, or export
- after reload or reopen
- at one constrained-width or alternate viewport for layout-affecting changes

## UI Quality Checklist

Review each screenshot for:

- card stacking
- oversized fonts
- redundant metadata already visible elsewhere
- low-semantic helper text occupying prime space
- unclear icons or badges
- detached controls that should live near the object they affect
- cramped inspector forms
- stale overlays or loading states
- clipped text or overlapping controls
- wasted canvas area
- file-panel or run-panel context confusion after graph switches

## Acceptable Click-Driven Evidence Examples

Good evidence examples:

- instantiate `Code Fix / Test / Review`, edit one node, edit one edge,
  `Dry-run`, fixture run, open `Run summary`, export, reload, and reopen the
  same graph with screenshots at each stage
- import a code-first graph file from `examples/agent-orchestration/`, confirm
  the graph appears in the desktop surface, export it back out, and run `lint`
  plus `dry-run` on the exported file
- trigger `compare` and `rollback` from the visible controls, then reload and
  prove the rolled-back graph state persisted

Weak evidence that is not sufficient by itself:

- a passing unit test without a visible replay
- a server log that says save succeeded
- a graph file on disk without visible import or export proof
- a successful API response from an internal orchestration endpoint

## Migration Requirements

When changing schema shape, lowering semantics, or compatibility behavior:

1. update `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`
2. update the canonical examples under `examples/agent-orchestration/`
3. preserve at least one before/after diff report
4. preserve at least one dry-run report for the migrated graph
5. verify import/export round-trip still works
6. verify reload/reopen still works for visible product paths

If a migration shim is introduced:

- document what source state it accepts
- document the expected destination state
- document the planned removal condition

## Rollback Requirements

When a change affects visible behavior or canonical graph semantics:

1. keep the pre-change graph or exported graph artifact
2. preserve a `diff` artifact when possible
3. verify compare/rollback behavior if the change touches graph persistence or
   safety/versioning
4. confirm the reopened product matches the intended post-rollback state
5. preserve the rollback evidence root rather than cleaning it up

## Secret Scan Requirements

Before considering orchestration work complete:

1. confirm no API keys, cookies, bearer tokens, auth headers, vault material,
   or plaintext secret dumps were added to:
   - graph files
   - screenshots
   - validation notes
   - runbook updates
   - logs staged for sharing
2. redact any raw provider request or response records before preserving them
3. do not store Desktop key files or other plaintext secret sources in evidence

At minimum, run a focused repo scan over changed artifacts when the change
touches preserved reports or examples.

## How To Add A New Provider Or Model-Sensitive Agent Template

Use this path when adding a template whose node routing, prompt, or tool policy
depends on provider or model behavior.

1. Start from the closest existing example:
   - `examples/agent-orchestration/provider_update_smoke.json`
   - `examples/agent-orchestration/code_fix_review.json`
   - `examples/agent-orchestration/fanout_research_synthesis.json`
2. Copy it to a task-local or evidence-local graph file first.
3. Change only the provider/model-sensitive parts explicitly:
   - `routing.selection_mode`
   - `routing.provider_id`
   - `routing.model_id`
   - prompt text
   - allowed tool classes
   - output schema refs
   - safety and approval settings
4. Never hardcode:
   - API keys
   - bearer tokens
   - cookies
   - local vault paths
   - machine-specific secret-bearing directories
5. If the template relies on a provider capability assumption, record the source:
   - official provider docs
   - current AstraBridge provider metadata
   - validated local smoke evidence
6. Run:
   - `lint`
   - `dry-run`
   - `diff` against the source template
7. Instantiate the template in the visible desktop surface and prove:
   - render
   - expected default node routing
   - expected prompt or schema defaults
   - dry-run behavior
   - export and reload behavior
8. Preserve the evidence under a new step-local or task-local root in
   `PRIVATE/agent-orchestration/productization/`

## Change-Specific Guidance

### Adding a node type

Update:

- contract enum or compatibility rules
- desktop iconography and inspector behavior if visible
- example graphs if the new node type is product-relevant
- dry-run logic if safety or output expectations differ

### Adding an edge type

Update:

- contract enum
- edge label/icon mapping in desktop UI
- handoff contract expectations
- edge dry-run checks
- at least one example graph using the new edge type

### Adding or revising prompt editors

Update:

- prompt-variable behavior
- prompt preview behavior
- invalid-variable validation
- export/import persistence

### Adding or revising schema editors

Update:

- schema parsing and validation behavior
- output-contract persistence
- dry-run schema-ref checks
- export/import persistence

### Adding DSL or graph-file fields

Update:

- file format parsing and serialization
- canonical contract validation
- examples
- CLI reporting where relevant
- migration notes

## Minimum Completion Note For Future Agents

A future orchestration change is not complete until the final note states:

- what canonical owner surfaces changed
- what code validations were run
- what visible click path was executed
- which screenshots were reviewed during the implementation loop
- what UI debt was fixed because of those screenshots
- what UI debt remains and its severity
- where the preserved evidence root lives

## Next Entry Point After This Runbook

When the orchestration plan needs follow-on work, resume from:

- `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`

When ordinary bounded graph work is needed, use:

- `apps/astrabridge-sidecar/skills/agent-orchestration-operator/SKILL.md`
