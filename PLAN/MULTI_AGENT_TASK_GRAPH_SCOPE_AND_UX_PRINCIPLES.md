# Multi Agent Task Graph Scope And UX Principles

Last updated: 2026-07-07

## Purpose

This document freezes the first product slice for AstraBridge's internal
multi-agent task graph system.

It exists to prevent drift into a vague "AI team chat" feature and to keep the
first implementation aligned with AstraBridge's existing product boundary:

- user-visible `Project -> Task`
- internal execution lanes and provider threads
- artifact-first review and validation

## Product Boundary

The multi-agent system lives inside one AstraBridge task.

The user should still understand the product as:

- one project
- one task
- one visible graph workspace and run timeline

The user should not be forced to understand:

- Codex `thread_id`
- provider thread ownership details
- subagent session trees
- raw runtime thread caches

Those remain internal execution details unless surfaced as:

- graph nodes
- activity rows
- diagnostics
- artifact lineage

## First Supported Workflow Patterns

The first product slice supports only bounded templates with explicit node roles,
artifact contracts, and context policies.

### 1. Supervisor / Worker / Synthesizer

Use when one coordinator decomposes a task, one or more workers execute bounded
subtasks, and one summarizer produces the final user-facing result.

Typical uses:

- repo research
- code change planning
- document analysis

### 2. Fan-out / Fan-in Research

Use when multiple workers can independently gather evidence and a synthesizer
merges their structured outputs.

Typical uses:

- multi-source repository analysis
- multi-provider documentation reconciliation
- comparison workflows

### 3. Code Fix / Test / Review

Use when a bounded coding worker proposes a change, a test worker verifies it,
and a review worker or synthesizer summarizes risk and final status.

Typical uses:

- bug fixes
- capability adapter repairs
- UI regressions with focused validation

### 4. Provider Update / Smoke / Rollout Gate

Use when the task is controlled provider/model update assistance, with explicit
validation, smoke, and human review gates.

This pattern should reuse AstraBridge's existing update and rollout evidence
discipline instead of inventing a separate workflow vocabulary.

### 5. Document Extract / Analyze / Report

Use when one node extracts structured content from files or media, one or more
analysis nodes process it, and a final node produces a summary or report.

Typical uses:

- OCR or PDF extraction followed by analysis
- vision-derived artifact inspection
- spreadsheet or report summarization

## Explicitly Out Of Scope For V1

These are not part of the first product slice:

1. Arbitrary external A2A server exposure.
2. Unbounded group chat among many agents.
3. Shared full-history blackboard memory across all nodes.
4. Silent autonomous writes to external systems.
5. Silent autonomous paid provider calls.
6. Free-form user-authored arbitrary graph semantics without template grounding.
7. Infinite or self-spawning agent recursion.
8. Treating plain chat messages as the durable result channel.
9. Replacing AstraBridge tasks with separate user-visible subagent threads.
10. Hiding approvals, cancellations, blocked states, or rollback evidence from the user.

## Core UX Principles

### Task-first

The graph is an execution surface inside a task, not a new top-level product
object. Users should enter from the task and stay within the task.

### Template-first

Users should start from a small set of high-value templates. Free-form editing
may exist, but the primary path is instantiating and modifying a bounded graph.

### Artifact-first

Critical outputs must be visible as artifacts or structured outputs. Users
should be able to inspect what each node produced without reading raw thread
history.

### Explicit Context Policy

Every edge must make context sharing visible:

- how much history is passed
- which artifacts are included
- whether private memory is excluded
- which structured outputs are forwarded

No hidden default of "share everything".

### Visible Safety State

The user must be able to see:

- blocked nodes
- approval-required nodes
- paid-call gates
- cancellation state
- rollback or retry paths

### Timeline And Graph Together

The graph explains topology. The timeline explains execution. The user should
not need to choose one or lose the other.

### Dense Operational UI

The graph workspace should feel like an operational tool, not a concept demo or
marketing panel. Controls must support repeated use, scanning, and comparison.

## Interaction Principles For The GUI

1. A user can create a graph from a template without typing JSON.
2. A user can drag nodes and wire edges directly on the canvas.
3. A user can inspect and change node role, model/provider, context policy, and
   output contract in a side inspector.
4. A user can dry-run before execution.
5. A user can inspect artifacts, warnings, and diagnostics from the run timeline.
6. A user can cancel a run and later understand what happened.
7. High-risk actions must surface an approval state before they execute.

## Simulated Click Validation Rule

Any GUI-visible workflow change in this project slice is incomplete until an
agent has exercised it through simulated user actions in the in-app browser or
Playwright.

Minimum expectation for a GUI-facing step:

1. open the relevant screen through clicks
2. perform the new interaction through clicks or drag gestures
3. verify the visible result in the rendered UI
4. preserve screenshots or traces under `PRIVATE/**`

Unit tests, schema tests, and API tests are still required, but they do not
replace simulated-click validation for GUI-facing work.

## Product Language Rules

Use user-facing terminology consistent with the existing architecture:

- `Task` is the user-visible work unit
- `execution lane`, `provider thread`, and `subagent thread` are internal unless
  intentionally surfaced as graph or timeline details
- graph nodes may show role and provider/model, but should not expose raw
  `thread_id` as the main label

## Entry Criteria For Step 2

The next step may assume:

- the first product slice is template-driven
- internal orchestration comes before external A2A compatibility
- artifact-first handoff and explicit context policy are mandatory
- open-ended group chat is not the product target
