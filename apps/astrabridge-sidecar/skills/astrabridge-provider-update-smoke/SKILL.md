---
name: astrabridge-provider-update-smoke
description: Qualify a provider, model, adapter, or routing update with source-backed discovery, a bounded smoke matrix, and an explicit approval gate over AstraBridge's canonical graph. Use when compatibility evidence must be reviewed before promotion; never use it for automatic rollout or silent catalog writeback.
---

# AstraBridge Provider Update Smoke

Use the `astrabridge.provider-update-smoke` manifest and the existing
`provider_update_smoke_gate` graph template. This skill produces qualification
evidence and a gate decision; it does not promote providers or mutate external
platforms.

## Resolve and validate

1. Read `orchestration-manifest.json`, the taxonomy contract, the provider
   compatibility matrix, and the canonical graph contract.
2. Define the provider/model change, source references, bounded smoke cases,
   success criteria, and promotion owner.
3. Resolve, lint, compile, and dry-run before any cost-bearing provider call.
   Treat a manual gate timeout or incomplete matrix as a blocker.
4. Preserve a provider diff bundle, per-case smoke matrix, blocked/conflicting
   cases, and an `approval_record:promotion_decision` artifact.
5. Use `astrabridge_web` MCP for public source discovery. Provider calls stay
   in declared provider adapters and route policy; never call a provider SDK
   directly from the skill.

## Topology and contracts

- `discovery extractor` → `smoke validator` → `manual gate`.
- Discovery output: `schema.provider_update_discovery` with provider changes
  and candidate models.
- Smoke output: `schema.provider_smoke_matrix` with per-case status and
  blocked cases.
- Gate output: `schema.provider_gate_decision` plus the approval record.
- Default limits: 3 agents, 1 parallel lane, 60,000 total tokens, 6 provider
  calls, and 1 retry; graph depth is 2.

## Truth and approval boundary

- Keep `documented`, `wired`, `verified`, and `exposed` facts separate;
  provider-wide defaults or catalog presence never prove model compatibility.
- Promotion is manual/approval-gated. Do not write credentials, provider
  configuration, external platforms, or hidden catalog state.
- Keep nested subagents and direct teammate messages false. Preserve each
  attempt and downgrade/blocked result rather than silently retrying or
  falling back.
- A conflicting route, failed smoke, unresolved source, missing approval,
  manual gate timeout, or over-budget matrix is a blocker.
