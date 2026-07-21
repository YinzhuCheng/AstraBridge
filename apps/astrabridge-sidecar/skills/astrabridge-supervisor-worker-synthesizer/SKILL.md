---
name: astrabridge-supervisor-worker-synthesizer
description: Run a bounded supervisor-worker-synthesizer workflow over AstraBridge's canonical AgentOrchestrationGraph. Use when a task needs one planner, one bounded worker lane, and an artifact-first synthesis result without GUI authoring, recursive subagents, or unrestricted teammate messaging.
---

# AstraBridge Supervisor Worker Synthesizer

Use the `astrabridge.supervisor-worker-synthesizer` manifest and the existing
`supervisor_worker_synthesizer` graph template. This skill is an authoring and
resolution aid; it never becomes a second scheduler or launches an agent by
itself.

## Resolve and validate

1. Read `orchestration-manifest.json`, the taxonomy contract, and the
   canonical graph contract before changing parameters.
2. Supply a non-empty `task_goal`; optionally provide bounded `constraints`
   and a `worker_scope`. Do not add nodes, branches, nested skills, or direct
   teammate messages.
3. Resolve the manifest into the existing canonical graph, then run canonical
   lint, compile, and dry-run checks before any live operation.
4. Keep the supervisor plan, worker report, and synthesis summary on declared
   typed ports and workspace-scoped artifact references only.
5. Route every tool/resource/multimodal action through the declared MCP policy.
   Narrow provider/model routes or lower budgets at request time; never widen
   the manifest policy.

## Topology and contracts

- `supervisor` → `worker` → `synthesizer`
- Input: `schema.skill_supervisor_input` with a declared text goal.
- Worker handoff: `schema.supervisor_plan` and bounded scope/constraints.
- Worker output: `schema.worker_result` plus `text_report:worker_report`.
- Final output: `schema.synthesis_result` plus `run_summary:final_summary`.
- Default limits: 3 agents, 1 parallel lane, 60,000 total tokens, 3 provider
  calls, and 1 retry; graph depth is 2.

## Safety boundary

- Keep `allow_nested_subagents` and `allow_direct_teammate_messages` false.
- Do not use full private history or provider-private reasoning as a handoff.
- Do not let the worker write files or make external changes without a bounded
  MCP rule and explicit approval.
- Treat missing route evidence, failed dry-run, unresolved artifacts, or an
  over-budget request as a blocker; do not silently fall back.
