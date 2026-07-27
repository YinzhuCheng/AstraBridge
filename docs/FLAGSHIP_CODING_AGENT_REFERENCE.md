# Flagship Coding-Agent Reference

Status: deterministic no-provider reference.

Last verified: 2026-07-27

## Purpose

This reference is the smallest source-inspectable coding-agent value loop that
AstraBridge currently proves without a provider credential. It gives a
developer a concrete scenario to inspect before relying on a live model route:
reject whitespace-only task titles while preserving valid-title behavior.

The reference deliberately separates a declared provider/model route snapshot
from provider access. The snapshot lets the task graph validate its pinned
routes and port contracts; it contains no credential and the runner makes no
network or provider call.

## What It Demonstrates

The checked-in [scenario manifest](../examples/flagship-coding-agent-reference/flagship-coding-agent-reference.json)
uses the Code Fix / Test / Review graph template. Its deterministic runner:

1. creates an isolated .abproj project and task;
2. creates the four-node plan, code-fix, test, and review graph;
3. checks the code-fix node's filesystem_write_gate and human-approval
   declaration;
4. records an exported graph, a failed fixture run, its blocked downstream
   nodes, and the preserved run manifest;
5. retries the failed planning node and its dependency-blocked downstream
   nodes into a new completed fixture run; and
6. writes a secret-free evidence.json and evidence.md packet.

The small seed project begins with a failing
[task-title check](../examples/flagship-coding-agent-reference/before/task_title_checks.py).
The expected bounded patch and recovered check demonstrate the task's intended
code result. The fixture itself does not give an agent write authority or
perform a provider-backed code change.

## Inspect Or Run

Read the manifest, the
[runner](../scripts/run_flagship_coding_agent_reference.py), and its focused
[test](../apps/astrabridge-sidecar/tests/test_flagship_coding_agent_reference.py).
Then choose a new, empty local output directory:

    cd D:\AstraBridge
    python scripts\run_flagship_coding_agent_reference.py --output-root PRIVATE\demo-runs\flagship-coding-agent-reference

The packet contains an isolated workspace, its .abproj file, the exported
orchestration graph, failure/recovery manifests, the initial failing check, and
the recovered passing check. It contains no API key, cookie, authorization
header, provider payload, or raw provider response.

For a focused regression check:

    cd D:\AstraBridge\apps\astrabridge-sidecar
    python -m unittest tests.test_flagship_coding_agent_reference

## No-Key UI Path

After creating or opening a local project, open Task Graph, choose the Code Fix
/ Test / Review template, and run Fixture Run. This makes the four-node
workflow and its task/run artifacts visible in the normal Project -> Task
surface without activating a provider route. Use the CLI runner when failure
injection and retry evidence are required; the UI fixture run is not a live
coding-provider smoke test.

## Ownership And Boundaries

| Concern | Named owner | Source boundary |
| --- | --- | --- |
| Project and task state | ProjectService and TaskService | apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py and task_service.py |
| Graph shape and write gate | task-graph contract | apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py |
| Fixture artifacts and recovery | TaskService fixture/recovery path | apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py |
| Visible graph/run surface | TaskGraphWorkspace | apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx |

The code-fix node declares human approval and a filesystem_write_gate. A
configured endpoint, catalog row, or graph template never removes that
boundary.

## Claim Boundary

This evidence supports only this statement:

> AstraBridge has a deterministic, no-provider coding-agent reference that
> exposes task state, an approval-gated code-change boundary, artifacts, a
> bounded failure, and retry recovery.

It does not prove live provider responses, an authorized coding route,
autonomous code writes, tool authority, release-installer behavior, or a
published distribution. Those claims require their own authorized evidence
lanes.
