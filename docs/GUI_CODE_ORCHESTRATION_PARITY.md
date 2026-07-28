# GUI / Code Orchestration Parity

## Status and scope

This is the public, deterministic reference for one native AstraBridge
workflow represented as source code, a Desktop Task Graph, and a runtime
orchestration manifest. It proves a deliberately bounded subset, not a
universal graph-conversion promise.

The canonical source is
[`examples/agent-orchestration/code_fix_review.json`](../examples/agent-orchestration/code_fix_review.json):
`graph_code_fix_review_v1` / `code_fix_test_review`. It contains four visible
stages:

1. `Plan Fix`
2. `Apply Code Fix`
3. `Run Tests`
4. `Review Result`

The code-fix stage deliberately retains its `ask` approval posture and
`filesystem_write_gate`. The reference does not make a provider request,
perform an autonomous code write, or grant tool authority.

## What the supported native path proves

The deterministic runner imports the source file into an isolated `.abproj`
workspace, then verifies the following sequence:

```text
native JSON source
  -> source-owned Desktop Task Graph
  -> dry-run + deterministic fixture run
  -> native JSON export
  -> re-import + semantic diff
```

It checks the graph identifier, template, graph policy, nodes, edges, ports,
input/output contracts, execution and safety fields, schema registry, rendered
node labels/positions, and the code-change approval boundary. The final native
JSON comparison must report `no_change`.

The current evidence packet records all of the following as successful:

| Boundary | Result |
| --- | --- |
| Source JSON -> Desktop Task Graph | `pass` with 4 nodes and 3 edges |
| Direct GUI write to a source-owned graph | blocked as `graph_source_owned` |
| Runtime dry-run | `pass` |
| Deterministic fixture run | `completed` |
| GUI/runtime export -> re-import | `no_change` / 0 changes |
| Provider and network calls | none |

The secret-free evidence is preserved at
[`PRIVATE/open-source-productization/validation/step6-gui-code-parity-20260727/evidence.md`](../PRIVATE/open-source-productization/validation/step6-gui-code-parity-20260727/evidence.md).
The same isolated project was opened in the AstraBridge in-app browser; its
Task Graph rendered the four declared nodes and source-owned banner. The UI
captures and [browser observation record](../PRIVATE/open-source-productization/validation/step6-gui-code-parity-20260727/in-app-browser-evidence.md)
are retained beside the evidence as `task-graph-ui.png` and
`task-graph-ui-full.png`.

## Start from code

1. Put the native graph file inside an AstraBridge workspace, for example at
   `workflows/code_fix_review.json`.
2. Open the `.abproj` project and choose **Task Graph** for the relevant task.
3. Use **Import** to select the workspace-relative JSON graph. The imported
   graph becomes *source-owned*: the Desktop surface renders and inspects it,
   but direct GUI mutation is rejected.
4. Use **Dry-run** or **Fixture Run** to inspect deterministic behavior. They
   are separate from a live provider run.

This is intentionally code-authoritative: edit the source file and import it
again when the canonical workflow should change.

## Start from the GUI

1. Open the task's **Task Graph** surface and inspect the source-owned graph,
   including its node ports, input/output contracts, and approval boundary.
2. Use **Export** to inspect the native JSON representation of the loaded
   supported graph.
3. If a GUI-only experiment is desired, choose **Disconnect and edit in GUI**.
   This explicitly creates a `detached_gui_edit` copy; it never writes the
   original source file. Export that detached copy to make a new explicit
   native JSON artifact.

The source-owned banner is a safety feature, not an inconvenience: it stops a
GUI click from silently changing version-controlled workflow code or its
authority semantics.

## Explicit boundaries and non-claims

- The exact lossless proof applies to this native JSON reference graph and the
  supported task-graph subset only. It does not prove lossless conversion for
  every GUI graph, external workflow format, or third-party adapter.
- Source-owned graphs do not write back to their source file. The only
  supported mutation path is an explicit detach followed by an explicit
  export.
- The deterministic fixture proves graph semantics and state transitions, not
  live model behavior, route eligibility, tool authority, or autonomous file
  writes.
- A provider/model selection shown in a task is metadata or review state unless
  its exact route has separately passed the authority gates in the
  [Provider Truth and Authority Surface](PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md).

Any future import/export adapter that cannot preserve a declared field must
report an explicit loss or reject the transform. It must not silently lower
permissions, tool policy, task state, or approval requirements.

## Reproduce locally

Choose a new, empty artifact directory; the runner refuses to overwrite an
existing non-empty directory.

```powershell
python scripts\run_gui_code_orchestration_parity.py `
  --output-root PRIVATE\demo-runs\gui-code-orchestration-parity

Push-Location apps\astrabridge-sidecar
python -m unittest discover -s tests -p test_gui_code_orchestration_parity.py
python -m unittest discover -s tests -p test_agent_orchestration_file_format.py
Pop-Location
```

The runner writes `source-graph.json`, `runtime-orchestration-manifest.json`,
`gui-surface.json`, `round-trip-diff.json`, `evidence.json`, and `evidence.md`.
These are secret-free, provider-free artifacts. Preserve them when comparing a
future parity change; do not substitute a visual screenshot for the semantic
diff.

## Owners

- Native orchestration/file-format contract: `agent-orchestration`.
- Task Graph import/export, source ownership, and runtime projection:
  `task-graph` / `astrabridge-sidecar`.
- Desktop rendering and inspector: `astrabridge-desktop`.
- Public claim wording and evidence boundary: `open-source-productization`.

See the [claim-evidence matrix](OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md)
for the precise public wording and [the flagship coding-agent reference](FLAGSHIP_CODING_AGENT_REFERENCE.md)
for the larger deterministic code-fix/test/review scenario.
