---
name: contributor-read-only-brief
description: Candidate example for a bounded, read-only AstraBridge skill extension. It resolves to the existing supervisor-worker-synthesizer graph and never becomes a scheduler, auto-enables itself, or makes a provider call during validation.
---

# Contributor Read-Only Brief

This is a copyable **candidate** skill-manifest example for a first
AstraBridge extension discussion. It turns one bounded task goal into the
existing `supervisor_worker_synthesizer` canonical graph without adding nodes,
runtime composition, direct teammate messages, or write-capable tools.

## Intended use

- Supply a short `task_goal` and optional bounded `constraints` / `worker_scope`.
- Inspect the resolved graph, then run canonical lint, compile, and dry-run
  checks.
- Keep any resulting proposal or evidence local and secret-free.

## Explicit limits

- This example is `candidate`, not productized or provider-qualified.
- It is not auto-discovered, auto-enabled, installed, or runnable as a live
  feature merely because the files exist under `examples/`.
- Its only declared tool is a read-only workspace MCP rule. File writes,
  installs, external writes, direct provider SDK calls, and direct peer
  messaging are not extension mechanisms.
- A requested provider or model outside the manifest allowlist must fail
  closed. A future live launch still needs separately authorized route,
  capability, approval, and lifecycle evidence.

See [the extension and first-contribution surface](../../../docs/EXTENSION_AND_FIRST_CONTRIBUTION_SURFACE.md)
for the supported scope, validation command, ownership, and pre-license
contribution boundary.
