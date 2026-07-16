# Task Graph Maintainer Runbook

## Purpose

This runbook is the maintainer entry point for AstraBridge's multi-agent task graph surface. It documents the contract layers, sidecar APIs, desktop UI ownership, artifact roots, and the click-driven evidence expected before claiming a task-graph change is done.

The product boundary remains `Project -> Task`. Graph nodes, worker lanes, provider threads, and subagent execution remain internal execution details unless surfaced as graph state or run activity.

## Key Source Surfaces

- Plan and progress:
  - `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
  - `PLAN/AGENT_GRAPH_GUI_RUNTIME_HANDOFF_EXECUTION_PLAN.md`
  - `PLAN/AGENT_GRAPH_GUI_RUNTIME_EXECUTION_CHECKLIST.md`
- Desktop UI:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/App.tsx`
  - `apps/astrabridge-desktop/src/styles.css`
- Sidecar state and execution:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`
- Local regression coverage:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`
  - `apps/astrabridge-desktop/src/features/runtime/taskThreadRestore.test.ts`
  - `apps/astrabridge-desktop/src/features/runtime/taskGraphRunRefs.test.ts`

## Contract Layers

## 1. Graph definition

The task graph definition lives under task state and is restored with the task, not as a separate top-level product object.

Important fields:

- `graph_id`, `task_id`, `template_id`, `state_version`
- `nodes[]`
- `edges[]`
- `graph_policy.entry_node_ids`

The desktop surface should treat node and edge configuration as structured state, not infer critical behavior from free-form labels.

## 2. Run reference

Graph execution snapshots are compacted into `graph_run_refs` on the task. The UI should rely on these compact refs for latest-run status, worker artifact links, approval state, and timeline visibility.

Important fields:

- `run_id`, `graph_id`, `status`
- `timeline_events[]`
- `worker_bindings[]`
- `diagnostic_refs[]`
- `approval_state` and `approval_details`

## 3. Artifact-first handoff

Downstream nodes should consume artifact references and bounded summaries rather than raw full-thread transcripts. This is the main safety boundary preventing private scratchpad leakage.

## Sidecar APIs

Current task-graph HTTP entry points are exposed in `server.py`:

- `GET /api/task-graphs/templates`
- `GET /api/task-graphs/graph`
- `GET /api/task-graphs/current`
- `POST /api/task-graphs/instantiate`
- `POST /api/task-graphs/node/update`
- `POST /api/task-graphs/edge/update`
- `POST /api/task-graphs/dry-run`
- `POST /api/task-graphs/worker/start`
- `POST /api/task-graphs/worker/output`
- `POST /api/task-graphs/fixture-run`
- `POST /api/task-graphs/run/cancel`
- `POST /api/task-graphs/approval/resolve`

Step 16 added safety and rollback endpoints:

- `POST /api/task-graphs/snapshot`
- `POST /api/task-graphs/snapshot/diff`
- `POST /api/task-graphs/rollback`

## Snapshot And Rollback Procedure

Task-graph snapshots are stored under workspace-local state:

- `.astrabridge/task-graph/snapshots/<task_id>/<graph_id>/<snapshot_id>/`

Each snapshot directory preserves:

- `task-graph.json`
- `orchestration-graph.json`
- `migration-report.json`
- `snapshot-manifest.json`
- optional `comparison-diff.json`
- optional `comparison-diff.md`

The desktop workspace is the primary rollback surface. The intended operator path is:

1. Open the task graph in the live app.
2. Click `Snapshot` before a risky graph edit or import.
3. Make the visible graph change.
4. Click `Compare` on the selected snapshot to inspect the current graph against that saved state.
5. Click `Rollback` on the selected snapshot when the current graph should be restored.
6. Reload or reopen the task graph from the visible UI and confirm the restored state persists.

Backend inspection is secondary. If the visible flow fails, preserve the failing click path and screenshots first, then inspect snapshot artifacts or sidecar responses afterward.

## Focused Secret Scan

Use the focused scan helper before claiming Step 16-style evidence is clean:

```powershell
python scripts/agent_orchestration_secret_scan.py <path1> <path2> --output <report.json>
```

Recommended targets:

- graph snapshot roots under `.astrabridge/task-graph/snapshots/**`
- orchestration graph exports under `PRIVATE/**`
- Step validation notes and reports under `PRIVATE/**`

This scan is intentionally narrow: it looks for secret-like tokens, desktop key-path leaks, and secret-bearing query parameters in graph, prompt, and evidence text files.

Maintenance rule:

- keep template instantiation, node/edge updates, dry-run, run state, and approval resolution secret-free at the UI boundary
- preserve provider/private execution details in sidecar-owned state unless there is an explicit reason to surface them

## Execution Model

## Template-first

The first-class entry path is template instantiation, not blank-canvas authoring. Usability and validation assume bounded templates with explicit context policy and output expectations.

### Built-in template catalog

The live template picker and `GET /api/task-graphs/templates` should stay aligned on these bounded starting points:

| Template | Primary use | Common node mix | Key operator expectation |
| --- | --- | --- | --- |
| `supervisor_worker_synthesizer` | One planner, one worker, one synthesis pass | `supervisor`, `worker`, `synthesizer` | Keep the worker lane bounded and artifact-first into synthesis. |
| `fanout_fanin_research` | Parallel bounded research branches | `supervisor`, `worker`, `worker`, `synthesizer` | Validate fan-out edge policy before run and keep branch outputs mergeable. |
| `code_fix_test_review` | Code change workflow with explicit review | `supervisor`, `worker`, `validator`, `reviewer` | Keep code-write, test, and review responsibilities separated. |
| `provider_update_smoke_gate` | Provider or model update triage | `extractor`, `validator`, `gate` | Promotion stays blocked behind visible approval. |
| `document_extract_analyze_report` | Document pipeline with explicit extract and report phases | `extractor`, `worker`, `synthesizer` | Report must derive from declared extract artifacts, not hidden context. |
| `multimodal_capability_adapter` | Capability probing and multimodal fallback validation | `extractor`, `worker`, `validator` | Confirm modality support explicitly and document fallback behavior before live provider use. |
| `custom_blank_graph` | Minimal authoring scaffold | `artifact_source` | Treat it as a scaffold only; rename the seed node and add downstream structure before run. |

### Reuse boundaries

- Template reuse is the supported reuse path today. Instantiate from the visible picker, then specialize labels, prompts, schemas, and edge policy to the current task.
- The product does not yet expose standalone subgraph packaging or nested reusable graph blocks as a first-class UI feature. Document those limits rather than implying they exist.
- `custom_blank_graph` is versioned as a seed scaffold, not a claim that freeform blank-canvas authoring is the primary workflow.
- `multimodal_capability_adapter` should only be offered against models whose modality claims are backed by product metadata, docs, or preserved smoke evidence.
- Template metadata must remain version-aware at the API boundary: `template_id`, counts, recommended providers/models, artifact expectations, validation hints, and constraints should round-trip from the sidecar list endpoint into the desktop picker.

## Fixture-first verification

Use dry-run and fixture-run paths first when validating behavior. Live provider-backed execution is not the baseline for UI or contract regression work.

## Maintainer Change Recipes

### Add or revise a node type

Touch these layers together:

- graph contract and canonical fixtures:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`
- runtime behavior:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- desktop editing surface:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/types.ts`
  - `apps/astrabridge-desktop/src/styles.css`

Minimum acceptance:

1. The new node shape round-trips through import, export, save, dry-run, and task restore.
2. The inspector exposes its bounded configuration without introducing hidden required fields.
3. Click-driven proof exists for `任务图 -> 模板或现有节点 -> 检查器 -> 选中对象`.

### Add or revise provider or model routing

Touch these layers together:

- provider metadata and transport:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/providers/`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/`
- runtime routing and capability validation:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
- graph defaults or templates when the route should be user-visible:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`
  - `examples/agent-orchestration/*.json`

Maintenance rules:

- Do not offer a provider/model for a graph port unless the modality claim is backed by docs, preserved smoke evidence, or explicit capability metadata.
- Keep managed-key and approval-gated behavior explicit when the route can trigger paid or high-risk calls.
- Preserve a sanitized smoke note or route summary under `PRIVATE/**` whenever a new route becomes operator-visible.

### Add or revise modality support

Touch these layers together:

- typed port and modality contract:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/`
- runtime validation and handoff shaping:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- desktop labels and inspector affordances:
  - `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  - `apps/astrabridge-desktop/src/types.ts`

Minimum acceptance:

1. Unsupported modality routes are blocked or warned before execution.
2. Output envelopes stay typed and secret-free.
3. The visible inspector explains the modality path through labels, icons, or tooltips instead of long prose.

### Add or revise templates

Primary files:

- `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`
- `examples/agent-orchestration/*.json`
- `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`

Minimum acceptance:

1. The template appears in `GET /api/task-graphs/templates`.
2. Instantiation produces a graph that passes dry-run without manual JSON repair.
3. The live picker can instantiate it by click from the visible task-graph sidebar.

### Add or revise runtime features

Typical examples: retry modes, recovery, run metrics, approval flow, budgets, export fields, artifact indexing.

Primary files:

- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`
- `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`
- `apps/astrabridge-sidecar/tests/test_task_graph_api.py`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`

Minimum acceptance:

1. Runtime artifacts remain durable under `PRIVATE/task-graph/**`.
2. Compact run refs expose only operator-meaningful state.
3. The desktop surface shows the new state without adding another decorative canvas card.

### Required UI validation workflow

UI acceptance is not satisfied by API calls or DOM mutation alone.

1. Open the live app in the in-app browser.
2. Reach the target task through visible clicks.
3. Open `任务图` from the product chrome.
4. Exercise the changed path by click, hover, scroll, expand, collapse, drag, or resize as appropriate.
5. Preserve screenshots under `PRIVATE/agent-graph-dynamic-workflow/<step>/.../screenshots/`.
6. Record the exact visible path and any residual density, truncation, or wasted-space issues in `validation-note.md`.

## Approval gates

High-risk transitions must remain visible in run state and block until explicit user approval. Approval UI is not decorative; it is part of the execution contract.

## Artifact Roots

Preserve task-graph evidence by default under `PRIVATE/**`.

Important roots:

- Active productization family:
  - `PRIVATE/agent-graph-dynamic-workflow/<step-slug>/<YYYYMMDD>/`
- Task-local runtime outputs:
  - `PRIVATE/demo-runs/<task-or-project>/workspace/PRIVATE/task-graph/<run-id-or-surface>/`
- Snapshot and rollback artifacts:
  - `.astrabridge/task-graph/snapshots/<task_id>/<graph_id>/<snapshot_id>/`

Never persist API keys, bearer tokens, cookies, auth headers, vault contents, or raw provider secrets in any report, screenshot, or artifact.

## Click-Driven Validation Standard

Task-graph UI work is not complete from tests alone. Before closing a UI-facing step:

1. Open the running app in the in-app browser.
2. Enter `Task graph` from the visible app surface.
3. Select a real template card.
4. Exercise the affected controls by simulated clicks.
5. Preserve screenshots and a short validation note under `PRIVATE/**`.

For layout and usability work, the proof must come from the visible product surface, not only DOM inspection or direct API calls.

## Evidence Links

- Step 11 fixture dogfood pack:
  - `PRIVATE/agent-graph-dynamic-workflow/step11-e2e-fixture-dogfood/20260709/`
- Step 12 approval-boundary pack:
  - `PRIVATE/agent-graph-dynamic-workflow/step12-human-approval-boundary-dogfood/20260709/`
- Step 12 residual inspector cleanup:
  - `PRIVATE/agent-graph-dynamic-workflow/step12-residual-inspector-cleanup/20260709/`
- Master execution record:
  - `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`

## Current Known Backlog

- Desktop inspector still truncates some long enum-like values.
- Narrow-width layout still requires too much vertical travel to reach run and inspector sections.
- The canvas interaction model still needs a stronger circuit-editor-style usability pass beyond copy reduction.
- Reusable subgraph packaging is still not a first-class visible feature; reuse remains template-first.

These are backlog items, not reasons to regress the current contract or remove evidence.
