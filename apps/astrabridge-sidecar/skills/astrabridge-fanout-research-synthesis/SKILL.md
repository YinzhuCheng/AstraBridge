---
name: astrabridge-fanout-research-synthesis
description: Run exactly two bounded public-research branches and merge attributable findings through AstraBridge's canonical graph. Use when a question benefits from independent web research and artifact-first synthesis, while private-memory leakage, recursive fan-out, and unbounded crawling must be denied.
---

# AstraBridge Fanout Research Synthesis

Use the `astrabridge.fanout-research-synthesis` manifest and the existing
`fanout_fanin_research` graph template. This is a fixed two-branch pattern, not
an invitation to create a dynamic agent pool.

## Resolve and validate

1. Read `orchestration-manifest.json`, the taxonomy contract, and the
   canonical graph contract.
2. Provide a bounded research goal, branch scopes, source/domain constraints,
   query limits, and merge criteria. Keep exactly two branches in v1.
3. Resolve, lint, compile, and dry-run the canonical graph before live search
   or provider execution.
4. Keep each branch's findings and source references as typed artifacts; the
   synthesizer consumes declared branch artifacts only.
5. Use the standalone `astrabridge_web` MCP preset for public search/fetch.
   Never pass credentials or local/private URLs and never turn web search into
   a model-backed capability.

## Topology and contracts

- `planner` → `researcher_a` and `researcher_b` → `synthesizer`.
- Planner output: `schema.research_plan` with questions and branch scopes.
- Branch output: `schema.branch_findings` plus attributable
  `text_report:branch_a_report` / `branch_b_report`.
- Final output: `schema.research_synthesis` plus
  `run_summary:research_synthesis`.
- Default limits: 4 agents, 2 parallel lanes, 100,000 total tokens, 6
  provider calls, and 2 retries; graph depth is 2.

## Safety boundary

- Cap queries, fetches, response characters, and preserved source artifacts;
  report blocked or timed-out branches explicitly.
- Do not add branches, recurse, send direct branch messages, use full private
  history, or synthesize source-less claims.
- Keep nested subagents and direct teammate messages false. Narrow route or
  budget constraints at request time, never widen them.
- A source-policy violation, unverified conclusion, missing attribution,
  unresolved artifact, or over-budget request is a blocker.
