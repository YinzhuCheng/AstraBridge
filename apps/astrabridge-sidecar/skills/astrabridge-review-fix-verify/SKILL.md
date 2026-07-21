---
name: astrabridge-review-fix-verify
description: Run a bounded code-change workflow with separate planner, code worker, test validator, and reviewer nodes over AstraBridge's canonical graph. Use when edits need explicit file scope, reproducible tests, independent review, MCP policy, and approval rather than an unrestricted coding swarm.
---

# AstraBridge Review Fix Verify

Use the `astrabridge.review-fix-verify` manifest and the existing
`code_fix_test_review` graph template. This skill packages review discipline;
it does not grant permission to edit files, install dependencies, or bypass
approval.

## Resolve and validate

1. Read `orchestration-manifest.json`, the taxonomy contract, and the
   canonical graph contract.
2. Declare the target files, intended patch, test command, and review criteria
   as bounded parameters. Reject unclear or repository-wide scope.
3. Resolve the manifest to the canonical graph, then lint, compile, and
   dry-run before any live provider or workspace mutation.
4. Keep the planner result, immutable code diff, test report, and review report
   on typed ports and workspace-scoped artifact references.
5. Route read, edit, shell, and test actions through the declared MCP workspace
   policy. Lower budgets or narrow routes at request time; never widen them.

## Topology and contracts

- `planner` → `code worker` → parallel `validator` and `reviewer`.
- Planner output: `schema.plan_fix_result` with target files and approach.
- Code worker output: `schema.code_fix_result` plus `code_diff:bounded_patch`.
- Validator output: `schema.test_result` plus `test_report:test_report`.
- Reviewer output: `schema.review_result` plus `validation_report:review_report`.
- Default limits: 4 agents, 2 parallel lanes, 80,000 total tokens, 6
  provider calls, and 2 retries; graph depth is 2.

## Approval and isolation

- Only the code worker may request the declared write effect. File writes,
  shell/test execution, installs, provider calls, and external writes require
  explicit approval and a preserved attempt artifact.
- Validator and reviewer must see the declared diff and outputs, not private
  scratchpads or provider-private reasoning, and cannot approve their own
  mutation.
- Keep nested subagents and direct teammate messages disabled. Never use a
  dynamic file glob, hidden install, destructive command, or direct provider
  SDK call as a substitute for the MCP policy.
- A failed test, stale revision, missing review, or over-budget retry is a
  blocker; do not report a successful fix from a human summary alone.
