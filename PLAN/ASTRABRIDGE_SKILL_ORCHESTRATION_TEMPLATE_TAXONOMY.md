# AstraBridge Skill Orchestration Template Taxonomy

Status: normative v1 taxonomy for the skill-first orchestration track
Version: `astrabridge-skill-template-taxonomy-v1`
Updated: 2026-07-21

Related contracts:

- [Skill-first boundary](./ASTRABRIDGE_SKILL_FIRST_ORCHESTRATION_BOUNDARY_CONTRACT.md)
- [Skill-to-graph contract](./ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md)
- [Skill-backed MCP surface](./ASTRABRIDGE_SKILL_BACKED_ORCHESTRATION_MCP_SURFACE_CONTRACT.md)
- [Canonical graph contract](./AGENT_ORCHESTRATION_GRAPH_CONTRACT.md)

## Purpose and selection rule

This document freezes the first finite set of reusable orchestration patterns
that may be packaged as AstraBridge skills or skill-backed presets. It is a
taxonomy and admission rubric, not a second runtime. Every record resolves to
an existing canonical `AgentOrchestrationGraph` template and then follows the
existing compiler, MCP broker, internal envelope, durable scheduler, and
artifact/run-event owners.

The v1 set is intentionally small enough to validate deeply across serial,
bounded parallel, code-changing, provider-qualification, and multimodal
capability lanes. A pattern is a product candidate only when its manifest,
graph topology, typed handoffs, MCP policy, approval policy, budgets, dry-run,
and evidence gates are all present. A graph example or a prose `SKILL.md` by
itself does not create a skill.

## Initial v1 set

| Pattern | Skill ID | Canonical `template_id` | Topology | v1 fit |
| --- | --- | --- | --- | --- |
| Supervisor / worker / synthesizer | `astrabridge.supervisor-worker-synthesizer` | `supervisor_worker_synthesizer` | planner → worker → synthesizer | bounded general decomposition and synthesis |
| Review / fix / verify | `astrabridge.review-fix-verify` | `code_fix_test_review` | planner → code worker → validator + reviewer | bounded code changes that require independent evidence |
| Fan-out research / synthesis | `astrabridge.fanout-research-synthesis` | `fanout_fanin_research` | planner → two research branches → synthesizer | attributable public research with bounded parallelism |
| Provider update / smoke / gate | `astrabridge.provider-update-smoke` | `provider_update_smoke_gate` | discovery → smoke matrix → approval gate | provider/model change qualification and promotion decisions |
| Multimodal capability adapter | `astrabridge.multimodal-capability-adapter` | `multimodal_capability_adapter` | probe → adapt contract → validate fallback | modality-aware routing and truthful downgrade behavior |

The existing `document_extract_analyze_report` graph remains a supported
canonical template but is deferred from the first skill package until the five
patterns above have passed the initial skill resolver, MCP, guardrail, and
dogfood gates. `custom_blank_graph` remains an authoring scaffold, never a
finished skill pattern. Adding either requires a taxonomy revision and a new
bounded evidence record.

## Shared v1 invariants

Every pattern in the initial set MUST declare the following in its skill
manifest:

- `resolution.mode: builtin_template` with exactly one canonical
  `graph_template_ref`;
- graph schema `astrabridge-agent-orchestration-graph-v1` and a stable semantic
  skill version;
- explicit node roles, entry nodes, edge ports, typed input/output schemas,
  artifact specifications, and prompt variables;
- MCP preset IDs and per-tool rules. Normal web, capability, resource, image,
  vision, audio, and document calls use MCP, including loopback. `web.search`
  remains a standalone web lane;
- `history_mode`/artifact projection, private-memory exclusion, no direct
  teammate messages, no provider-private reasoning, and no unredacted raw
  transcripts in handoffs;
- an explicit finite budget, graph depth `2`,
  `allow_nested_subagents: false`, and
  `allow_direct_teammate_messages: false`;
- approval requirements for provider calls, file writes, shell/code changes,
  external writes, and promotion effects;
- provider/model routing restrictions that consult model-level compatibility
  evidence. Recommended routes are hints, not proof of eligibility;
- `requires_dry_run_before_live: true`, immutable resolution/graph digests,
  durable idempotency, and preserved validation/run artifacts;
- external A2A disabled unless a later qualified manifest names approved
  `a2a_card:` references and uses the gateway.

The effective budget is the minimum of the hard boundary, manifest, graph,
runtime, and request values. The following defaults are taxonomy defaults for
Step 6 fixtures; Step 8 may lower them, but no implementation may turn them
into unbounded values.

| Default | Value |
| --- | ---: |
| Maximum graph depth | 2 |
| Nested subagents | denied |
| Direct teammate messages | denied |
| Maximum total agents | 4 |
| Maximum parallel agents | 2 |
| Maximum retries per node/run policy | 2 |
| Provider/model concurrency | at most 2 per declared route |

## Pattern records

### 1. Supervisor / worker / synthesizer

**Identity and topology**

- Skill: `astrabridge.supervisor-worker-synthesizer@1.0.0`
- Template: `supervisor_worker_synthesizer`
- Nodes: `supervisor` → `worker` → `synthesizer`; one active lane at a time;
  three agents, two edges, depth two.
- Existing graph evidence: `examples/agent-orchestration/supervisor_worker_synthesizer.json`.

**Fit criteria**

- The task has one bounded goal, one independently executable work package,
  and a final synthesis that can consume a declared worker artifact.
- Use when decomposition is useful but parallel branches or code mutation are
  not required.

**Typed handoffs and artifacts**

| Edge/output | Required contract |
| --- | --- |
| supervisor → worker | `schema.supervisor_plan`; goal, constraints, scope, and acceptance checks |
| worker → synthesizer | `schema.worker_result`; result, evidence, and `text_report:worker_report` |
| final output | `schema.synthesis_result`; summary, open questions, and `run_summary:final_summary` |

**MCP, routing, and approvals**

- Supervisor may use declared read-only MCP tools such as web research or
  workspace reads; worker may use only declared read/analysis tools unless a
  separate manifest explicitly adds a risky effect; synthesizer is read-only.
- Current template metadata recommends Qwen/Kimi families. The resolver must
  verify the concrete model route through the compatibility matrix and may
  downgrade to a validated route or block.
- Provider calls and any file write require the manifest approval policy; no
  hidden write is allowed.

**Taxonomy defaults**

- `max_total_agents: 3`, `max_parallel_agents: 1`, `max_total_tokens: 60000`,
  `max_provider_calls: 3`, `max_retries: 1`.

**Disallowed variants**

- supervisor dynamically spawning workers or invoking another skill;
- more than one worker lane without switching to the fan-out pattern;
- synthesis from undeclared history/private memory instead of worker artifacts;
- a worker writing files without a bounded patch scope and approval;
- direct provider API, non-MCP tool, or direct teammate-message bypass.

### 2. Review / fix / verify

**Identity and topology**

- Skill: `astrabridge.review-fix-verify@1.0.0`
- Template: `code_fix_test_review`
- Nodes: `planner` → `code worker`, then bounded parallel `validator` and
  `reviewer`; four agents, three edges, depth two, maximum parallelism two.
- Existing graph evidence: `examples/agent-orchestration/code_fix_review.json`.

**Fit criteria**

- A requested code change has an explicit target scope, a reproducible test
  command, and a review decision independent from the code-writing node.
- Use only when the workspace and approval context permit the declared edit
  effect. Read-only diagnosis belongs in the supervisor pattern.

**Typed handoffs and artifacts**

| Edge/output | Required contract |
| --- | --- |
| planner → code worker | `schema.plan_fix_result`; target files, approach, constraints, and test plan |
| code worker → validator | `schema.code_fix_result` plus `code_diff:bounded_patch` |
| code worker → reviewer | the same immutable diff/reference and change summary |
| validator output | `schema.test_result` plus `test_report:test_report` |
| reviewer output | `schema.review_result` plus `validation_report:review_report` |

**MCP, routing, and approvals**

- File reads, edits, and shell/test execution must be represented by declared
  MCP tools/presets and node policies; the code worker is the only write-capable
  node.
- `file_write`, `shell`, install, and external-write effects require explicit
  approval. Validator and reviewer cannot approve their own code changes.
- Current metadata recommends Qwen/DeepSeek/Kimi families. Concrete routes are
  qualified per model; no provider-wide optimistic fallback.

**Taxonomy defaults**

- `max_total_agents: 4`, `max_parallel_agents: 2`, `max_total_tokens: 80000`,
  `max_provider_calls: 6`, `max_retries: 2`.

**Disallowed variants**

- unbounded file globs, repository-wide destructive edits, or hidden install;
- code worker also acting as validator/reviewer without independent evidence;
- skipping tests/review, merging their outputs through full history, or
  treating a human-summary-only pass as verification;
- retrying a failed write without preserving the earlier attempt artifact;
- direct shell/provider calls that bypass the MCP policy and approval ledger.

### 3. Fan-out research / synthesis

**Identity and topology**

- Skill: `astrabridge.fanout-research-synthesis@1.0.0`
- Template: `fanout_fanin_research`
- Nodes: `planner` → exactly two bounded `researcher` branches → `synthesizer`;
  four agents, four edges, depth two, maximum parallelism two.
- Existing graph evidence: `examples/agent-orchestration/fanout_research_synthesis.json`.

**Fit criteria**

- The question benefits from independent public-source branches whose outputs
  can be attributed and merged. It must not require private-memory sharing or
  an unbounded search swarm.

**Typed handoffs and artifacts**

| Edge/output | Required contract |
| --- | --- |
| planner → each branch | `schema.research_plan`; branch scope, query budget, source policy |
| branch A/B → synthesizer | `schema.branch_findings`; findings, source references, and `text_report:branch_a_report` / `branch_b_report` |
| final output | `schema.research_synthesis`; synthesis, gaps, attribution, and `run_summary:research_synthesis` |

**MCP, routing, and approvals**

- Use only the standalone `astrabridge_web` MCP preset for public web search /
  fetch. The branch tool policy must cap queries, fetches, characters, and
  source artifacts; it cannot receive local/private URLs or credentials.
- The synthesizer reads declared branch artifacts only. Web search is not
  silently converted into a model-backed capability.
- Current metadata recommends Qwen/Kimi families; model routing remains
  compatibility-qualified.

**Taxonomy defaults**

- `max_total_agents: 4`, `max_parallel_agents: 2`, `max_total_tokens: 100000`,
  `max_provider_calls: 6`, `max_retries: 2`.

**Disallowed variants**

- dynamic branch creation, branch count above two in v1, recursive fan-out, or
  a branch that spawns another skill;
- direct branch-to-branch messages or synthesis from undeclared full history;
- unbounded crawling, local/private URL access, or source-less conclusions;
- treating a search timeout as a successful source or hiding blocked branches;
- external writeback or provider-direct web search.

### 4. Provider update / smoke / gate

**Identity and topology**

- Skill: `astrabridge.provider-update-smoke@1.0.0`
- Template: `provider_update_smoke_gate`
- Nodes: `discovery extractor` → `smoke validator` → `manual gate`; three
  agents, two edges, depth two.
- Existing graph evidence: `examples/agent-orchestration/provider_update_smoke.json`.

**Fit criteria**

- A provider/model catalog, adapter, route, or protocol update needs a
  source-backed diff, a bounded smoke matrix, and an explicit promotion
  decision. This pattern is for qualification, not automatic rollout.

**Typed handoffs and artifacts**

| Edge/output | Required contract |
| --- | --- |
| discovery → smoke | `schema.provider_update_discovery`; provider changes and candidate models |
| smoke → gate | `schema.provider_smoke_matrix`; per-case matrix, blocked cases, and evidence refs |
| gate output | `schema.provider_gate_decision` plus `approval_record:promotion_decision` |

**MCP, routing, and approvals**

- Public source discovery uses `astrabridge_web` MCP. Provider/model smoke
  calls use the declared provider route and must preserve capability status as
  `documented`, `wired`, `verified`, or `blocked` rather than assuming a
  catalog entry is runnable.
- Promotion is always manual/approval-gated. No external platform writeback,
  credential mutation, or silent provider default update is permitted.
- A manual gate timeout or incomplete matrix is a blocker, not a pass.

**Taxonomy defaults**

- `max_total_agents: 3`, `max_parallel_agents: 1`, `max_total_tokens: 60000`,
  `max_provider_calls: 6`, `max_retries: 1`.

**Disallowed variants**

- auto-promotion, hidden catalog writes, or claiming provider-wide support from
  one model's smoke;
- accepting a provider update with blocked/conflicting cases unresolved;
- live cost-bearing calls without approval, dry-run, and a bounded case matrix;
- direct provider SDK calls outside the provider adapter and MCP policy plane;
- using this pattern as a general task planner or recursive agent pool.

### 5. Multimodal capability adapter

**Identity and topology**

- Skill: `astrabridge.multimodal-capability-adapter@1.0.0`
- Template: `multimodal_capability_adapter`
- Nodes: `input/capability probe` → `contract adapter` → `fallback validator`;
  three agents, two edges, depth two.
- Existing graph evidence: `examples/agent-orchestration/multimodal_capability_adapter.json`.

**Fit criteria**

- A task includes image, vision, audio, document, or another declared content
  part whose provider/model support may differ. The pattern must select or
  downgrade through a capability route and leave an explicit validation record.
- v1 multimodal lanes are `image.generate`, `vision.analyze`,
  `speech.transcribe`, and `speech.synthesize`. Video lanes remain out of
  scope until a separate adapter and exposure gate exist.

**Typed handoffs and artifacts**

| Edge/output | Required contract |
| --- | --- |
| probe → adapter | `schema.multimodal_probe`; detected modalities, limits, and fallback plan plus `image:input_image` or declared artifact refs |
| adapter → validator | `schema.multimodal_adapted`; adapted prompt/content contract and selected route plus `document_extract:adapted_contract` |
| final output | `schema.multimodal_validation`; status, fallback-used flag, and `validation_report:multimodal_validation` |

**MCP, routing, and approvals**

- All capability calls use the `astrabridge_capabilities` MCP preset and the
  stable capability IDs. Provider-specific content shapes remain inside the
  adapter family.
- Model-level exposure states (`documented_unwired`, `wired_unverified`,
  `verified_runnable`, `blocked`, `hidden`, `unknown`) are authoritative;
  catalog presence alone cannot enable a route.
- Image/audio artifacts use workspace-scoped `ArtifactRef` values with size,
  media type, digest, and lineage. Returned provider paths are untrusted.
- Provider calls and generated artifacts require the declared approval and
  redaction policy. Fallback must be explicit; silent modality loss is a
  blocker.

**Taxonomy defaults**

- `max_total_agents: 3`, `max_parallel_agents: 1`, `max_total_tokens: 80000`,
  `max_provider_calls: 6`, `max_retries: 2`.

**Disallowed variants**

- direct provider image/vision/audio calls, provider-specific shapes in the
  AgentEnvelope, or capability calls outside MCP loopback/broker policy;
- catalog-only exposure, provider-wide optimistic inheritance, unverified
  fallback, or silent conversion of unsupported modalities;
- raw local paths, credentials, hidden RGB/audio payloads, or unbounded media
  size/count; video support without an explicit qualified adapter;
- treating a `blocked` or `wired_unverified` lane as runnable.

## Cross-pattern admission rubric

Step 6 may implement a pattern only after all rows below are satisfied. The
rubric is intentionally independent of any GUI surface.

| Gate | Required evidence | Failure result |
| --- | --- | --- |
| Identity | stable skill ID/version, one template ref, manifest digest | candidate only |
| Topology | canonical graph lint/compile, depth and finite parallel groups | blocker |
| Typed handoff | input/output schemas, declared ports, artifact lineage | blocker |
| MCP | preset/tool rules, effect classes, approval and loopback policy | blocker |
| Routing | model-level provider compatibility and truthful downgrade | blocker or warning only |
| Guardrails | finite agent/token/call/retry/concurrency budgets; nested/direct messaging denied | blocker |
| Dry-run | compiled plan, policy snapshot, no live provider call, preserved receipt | blocker |
| Evidence | redacted fixture outputs, diagnostics, and operator interpretation | validated at minimum |
| Promotion | required approval/A2A/exposure evidence for the pattern's effects | productized only after pass |

No pattern may widen this rubric through a request-level override. A request
may only narrow routes, lower budgets, add approval, reduce context, or select a
smaller declared subset.

## Machine-readable taxonomy summary

This summary is intentionally declarative and does not execute anything.

```json
{
  "schema_version": "astrabridge-skill-template-taxonomy-v1",
  "max_patterns": 5,
  "shared": {
    "graph_schema_version": "astrabridge-agent-orchestration-graph-v1",
    "max_depth": 2,
    "allow_runtime_nesting": false,
    "allow_nested_subagents": false,
    "allow_direct_teammate_messages": false,
    "requires_dry_run_before_live": true,
    "mcp_only": true
  },
  "patterns": [
    {
      "skill_id": "astrabridge.supervisor-worker-synthesizer",
      "version": "1.0.0",
      "template_id": "supervisor_worker_synthesizer",
      "node_count": 3,
      "max_parallel_agents": 1,
      "risk_classes": ["provider_call", "optional_file_write"]
    },
    {
      "skill_id": "astrabridge.review-fix-verify",
      "version": "1.0.0",
      "template_id": "code_fix_test_review",
      "node_count": 4,
      "max_parallel_agents": 2,
      "risk_classes": ["provider_call", "file_write", "shell", "external_write"]
    },
    {
      "skill_id": "astrabridge.fanout-research-synthesis",
      "version": "1.0.0",
      "template_id": "fanout_fanin_research",
      "node_count": 4,
      "max_parallel_agents": 2,
      "risk_classes": ["network_read", "provider_call"]
    },
    {
      "skill_id": "astrabridge.provider-update-smoke",
      "version": "1.0.0",
      "template_id": "provider_update_smoke_gate",
      "node_count": 3,
      "max_parallel_agents": 1,
      "risk_classes": ["network_read", "provider_call", "external_write"]
    },
    {
      "skill_id": "astrabridge.multimodal-capability-adapter",
      "version": "1.0.0",
      "template_id": "multimodal_capability_adapter",
      "node_count": 3,
      "max_parallel_agents": 1,
      "risk_classes": ["provider_call", "file_write"]
    }
  ],
  "deferred_templates": ["document_extract_analyze_report"],
  "scaffolds_not_skills": ["custom_blank_graph"]
}
```

## Next implementation boundary

Step 6 will create the five skill/preset artifacts and make each resolve to the
listed canonical graph. Step 7 will connect lint, diff, and dry-run evidence to
these manifests; Step 8 will enforce the taxonomy budgets at runtime; Step 11
will expose the MCP tools defined by the MCP surface contract. None of those
steps may introduce a GUI-only pattern, an unbounded agent pool, or a second
execution truth.

