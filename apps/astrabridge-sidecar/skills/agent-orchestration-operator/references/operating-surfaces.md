# Operating Surfaces

Use this reference when the orchestration task needs concrete repository entry points or a repeatable validation checklist.

## Canonical Files

- Active durable execution plans:
  - `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
  - `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`
  - `PLAN/AGENT_GRAPH_GUI_RUNTIME_EXECUTION_CHECKLIST.md`
- Durable execution plan:
  - `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md`
- Maintainer runbook:
  - `PLAN/AGENT_ORCHESTRATION_MAINTENANCE_RUNBOOK.md`
- Canonical graph contract:
  - `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`
- CLI:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py`
- Task-graph runtime:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- Task-graph contract:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`
- Desktop workspace:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`

## Canonical Example Graphs

- `examples/agent-orchestration/code_fix_review.json`
- `examples/agent-orchestration/provider_update_smoke.json`
- `examples/agent-orchestration/fanout_research_synthesis.json`

Use these as starting points before inventing a new graph shape.

## Validation Checklist

For code-first work:

1. Run `lint`.
2. Run `dry-run`.
3. Run `diff` if an existing graph changed.
4. Preserve the command outputs in a task-local or evidence-local artifact root.

Suggested commands:

```powershell
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli lint <graph.json>
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli dry-run <graph.json>
.\.venv\Scripts\python.exe -m astrabridge_sidecar.agent_orchestration_cli diff <old-graph.json> <new-graph.json>
```

When runtime compatibility or task-graph execution changed, also run focused tests such as:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_task_graph_worker_runtime.py -k "<focused-case>"
.\.venv\Scripts\python.exe -m pytest tests/test_task_graph_api.py -k "<focused-case>"
```

For visible product work:

1. Use the in-app browser when the app is already open there.
2. Operate the graph through visible controls.
3. Capture screenshots before change, during the key interaction, after the result, and after reopen or reload.
4. Review those screenshots for:
   - card stacking,
   - oversized fonts,
   - low-semantic text in prime space,
   - redundant information,
   - detached controls,
   - unclear icons,
   - cramped inspectors,
   - wasted canvas area.
5. Prefer this visible operator path when the step touches runtime state:
   - open `任务图`
   - run fixture, cancellable fixture, or dry-run from the toolbar
   - open the inspector
   - switch to the run-inspection workspace
   - inspect node or edge state, or trigger cancel/recover actions
   - return to conversation
   - reopen the graph to confirm persistence

Default evidence root for the active Agent Graph plan family:

- `PRIVATE/agent-graph-dynamic-workflow/<step-slug>/<YYYYMMDD>/`

## Approval Checklist

Require explicit user approval before:

- graph depth greater than `2`,
- enabling risky code-write or install behavior,
- broad permission escalation,
- live provider execution,
- promotion of a graph that has not passed `dry-run`.

## Example Request Patterns

- "Design a bounded code-fix/test/review graph for this task and keep it code-first."
- "Modify this orchestration graph to add a manual gate and give me the diff."
- "Validate this exported graph before I import it back into AstraBridge."
- "Prove this graph workflow in the real app with screenshots, not API-only traces."
- "Repair this saved task graph so cancellable fixture and recovery work again."
- "Validate cancel, resume, rerun, or partial rerun from the visible GUI."
