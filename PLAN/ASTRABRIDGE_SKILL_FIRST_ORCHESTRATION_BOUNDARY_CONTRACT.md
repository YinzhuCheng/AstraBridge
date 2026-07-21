# AstraBridge Skill-First Orchestration Boundary Contract

Status: normative for the skill-first multi-provider orchestration track  
Version: `astrabridge-skill-first-boundary-v1`  
Last updated: 2026-07-21

## Purpose and authority

This document freezes the product boundary for the skill-first upgrade track
defined by
`PLAN/ASTRABRIDGE_SKILL_FIRST_MULTI_PROVIDER_AGENT_ORCHESTRATION_EXECUTION_PLAN.md`.
It is a boundary and release-policy contract, not a replacement for the
canonical graph schema, protocol schema, MCP broker, or external A2A gateway.

The ownership chain is:

1. `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md` owns the authoring and
   interchange shape of `AgentOrchestrationGraph`.
2. `astrabridge_sidecar.agent_orchestration_contract` owns backend validation,
   migration, and canonical vocabulary for that graph.
3. `astrabridge_sidecar.agent_orchestration_compiler` lowers a valid graph to
   the task-graph execution representation.
4. `astrabridge_sidecar.protocol` owns durable `AgentEnvelope`, `AgentTask`,
   `ContentPart`, `ArtifactRef`, and delivery-event schemas.
5. `astrabridge_sidecar.external_a2a_gateway` and
   `astrabridge_sidecar.external_a2a_conformance` own external A2A cards,
   negotiation, trust, replay protection, and wire adaptation.
6. The MCP broker and first-party MCP servers own normal tool, resource, and
   multimodal dispatch semantics.

This contract may tighten defaults or add a required validation gate, but no
skill, provider adapter, GUI projection, or compatibility shim may weaken the
boundaries below or create a parallel owner.

## Product position and scope

AstraBridge is a multi-provider, multi-model Codex shell with bounded agent
orchestration. In this track, orchestration patterns are distributed as
reviewable skills or skill-backed presets. A skill is an authoring and reuse
surface; the canonical graph and runtime remain the only execution truth.

### In scope

- Skill-authored supervisor-worker, review-fix-verify, fanout-synthesis,
  provider-smoke, multimodal-adaptation, and future bounded patterns.
- Provider/model routing declared at graph-node or execution-lane level.
- Typed input, output, artifact, context, approval, tool, and subagent policy
  contracts.
- MCP-normalized tool, resource, and multimodal calls, including AstraBridge
  first-party loopback implementations.
- Cross-provider handoff through AstraBridge's internal protocol envelope.
- External peer calls through the explicit external A2A gateway boundary.
- Code-authored and skill-authored graphs compiling to the same canonical
  graph and scheduler.
- Lint, compile, dry-run, deterministic fixtures, runtime evidence, evaluation
  gates, and operator runbooks.

### Explicitly deferred in this track

- Net-new GUI authoring or a second visual workflow editor. Existing GUI
  surfaces may display or operate a graph only when that is needed to preserve
  compatibility or prove an operator path.
- Provider-specific orchestration DSLs or provider-direct graph runtimes.
- Runtime skill nesting, recursive skill invocation, or unbounded agent-team
  expansion.
- Treating ComfyUI, LangGraph, LangChain, Claude-style teams, or an external
  A2A implementation as an alternative AstraBridge execution engine. Their
  useful patterns may be represented as AstraBridge skills or adapters only.

## Non-negotiable invariants

The following statements are normative. `MUST` and `MUST NOT` are release
requirements; `SHOULD` describes a preferred compatible behavior.

### One graph and one runtime

- Every productized skill MUST resolve to an `AgentOrchestrationGraph` or a
  named graph preset before execution.
- Skill-authored, code-authored, imported, and GUI-edited definitions MUST
  converge on the same graph validator, compiler, scheduler, run store, and
  recovery semantics.
- A skill MUST NOT launch agents by maintaining its own scheduler, queue,
  retry loop, run-state store, or hidden provider-client pool.
- `TaskGraphDefinition` is a compiled compatibility projection during the
  transition; it is not a second authoring truth.
- UI metadata, prompt previews, and skill prose MUST NOT mutate live run state
  or change execution policy implicitly.

### Skill package and skill-to-graph boundary

A productized orchestration skill MUST expose a machine-readable manifest (the
exact file format is finalized in Step 3) containing at least:

- stable `skill_id` and semantic `version`;
- a graph template or preset reference;
- declared input and output contract references;
- allowed parameters and their types/defaults;
- routing, tool, approval, context, artifact, and subagent policy defaults;
- compatibility requirements and required evidence level.

The prose `SKILL.md` remains useful for an agent author or operator, but prose
alone is not a productized execution contract. Helper scripts or assets may
prepare graph data, but they MUST return to the canonical graph compiler and
MUST NOT spawn an out-of-band agent or call a provider directly.

Skill composition is compile-time only. A skill MAY reference a named graph
template or preset, but a running node MUST NOT invoke another skill as a new
recursive orchestration root. Template references MUST be acyclic and
resolved before lint/dry-run. If a future feature needs nested composition, it
requires an explicit contract revision, a bounded depth budget, and user
approval; it is not enabled by this document.

### MCP capability boundary

- All normal tool, resource, image, vision, audio, video, document, and other
  multimodal execution MUST pass through the MCP broker contract.
- AstraBridge-owned in-process or loopback calls are MCP implementations, not
  exceptions: they MUST retain the MCP request/result shape plus authorization,
  timeout, cancellation, policy, audit, and typed-result semantics.
- A skill MUST NOT embed provider HTTP calls, SDK calls, raw tool transports,
  or direct filesystem/network capability calls as a bypass around MCP.
- Provider adapters may translate model protocols, but they MUST NOT become a
  second multimodal/tool/resource plane.
- `web.search` remains a standalone web lane even if its operator surface is
  exposed through MCP; it is not silently reclassified as a model-backed
  capability.

### Internal envelope and external A2A boundary

- Agent-to-agent and cross-provider handoff MUST use the AstraBridge-owned,
  versioned `AgentEnvelope`, `AgentTask`, `ContentPart`, `ArtifactRef`, and
  delivery-event contracts.
- Provider-private transcripts, hidden reasoning, credentials, cookies,
  authorization headers, and provider response internals MUST NOT enter a
  durable envelope or a skill handoff.
- Typed parts and artifact references are authoritative. Human summaries and
  UI previews are projections and MUST NOT be the only machine handoff.
- External A2A wire messages, Agent Cards, task IDs, transport/auth details,
  trust decisions, and replay state MUST terminate at the external A2A gateway.
- A graph or skill MAY reference an approved `a2a_card:` entry, but the
  compiler MUST resolve and snapshot the gateway decision; external A2A fields
  MUST NOT become a parallel durable protocol schema or registry.
- Delivery semantics are at-least-once with durable idempotency and
  deduplication. The product MUST NOT claim network-level exactly-once
  delivery.

### Shallow orchestration and budget boundary

- `graph_policy.max_depth` MUST be explicit. The normal product default and
  promotion ceiling for this track is depth `2`.
- `allow_nested_subagents` MUST default to `false` and a productized skill
  MUST declare it explicitly. A request for nested subagents MUST fail closed
  unless a later contract revision grants an approved bounded exception.
- `allow_direct_teammate_messages` MUST default to `false`. Communication is
  through declared typed edges unless a bounded template explicitly opts in
  and the runtime supports that path.
- Every live launch MUST carry explicit limits for total agents, maximum
  parallel agents, total tokens, provider calls, retries, and per-provider or
  per-model concurrency where the runtime supports those dimensions.
- Omitted, malformed, or exceeded limits MUST fail closed before provider
  dispatch. A skill MUST NOT use an unbounded default to make a graph pass.
- `requires_dry_run_before_live` MUST be true for productized patterns.
- Risky filesystem writes, code changes, installs, paid provider calls,
  external writes, and non-local worktree changes MUST remain behind an
  explicit approval policy and preserve recovery evidence.
- A graph that exceeds the shallow default, requests nested agents, or lacks a
  finite token/agent budget is a candidate or warning-only artifact, never a
  productized launchable skill.

## What counts as productized

The lifecycle below separates authoring progress from a shippable product
claim.

| Level | Meaning | Minimum evidence |
| --- | --- | --- |
| `candidate` | A skill or preset is being authored or adapted. | Manifest draft, graph/template reference, and human-readable intent. It is not launchable as a product feature. |
| `validated` | The candidate is structurally safe to test. | Canonical graph validation, lint, compile, deterministic dry-run, secret scan, and explicit policy snapshot. |
| `productized` | The pattern is a supported AstraBridge skill-backed orchestration feature. | All `validated` evidence, a deterministic canonical-runtime fixture run through MCP loopback, typed edge/envelope checks, fail-closed guardrail checks, durable run artifacts, and an operator/authoring runbook. |
| `provider-qualified` | The productized pattern has a verified live provider route. | Authorized, bounded provider smoke evidence with route/model truthfulness, fallback/downgrade semantics, redacted usage, and preserved rollback/recovery evidence. |
| `external-a2a-qualified` | The pattern is approved for external peer use. | `provider-qualified` evidence where applicable plus gateway negotiation, trust, replay, artifact, cancellation, and negative-conformance evidence. |

The word “supported”, a default template, or a GUI listing MUST NOT be used
for a pattern below `productized`. Provider and external-A2A qualification are
additional claims, not implied by fixture success.

## Release-blocking violations and degradable warnings

### Release-blocking violations

The following MUST fail lint, admission, promotion, or live launch as
appropriate:

- a skill-backed path bypasses the canonical graph/compiler/runtime;
- a tool, resource, or multimodal call bypasses MCP or a loopback-equivalent
  MCP policy surface;
- a required typed input/output/handoff contract, envelope field, artifact
  lineage, or context policy is absent or invalid;
- private memory, provider-private reasoning, credentials, or secret-bearing
  payloads cross an edge or enter durable evidence;
- nested subagents, unrestricted teammate messaging, cyclic template
  composition, unbounded agent creation, or a missing/invalid budget is
  requested;
- a limit is exceeded without a fail-closed admission decision;
- a risky mutation, paid call, or external write lacks the declared approval
  and recovery path;
- provider capability, modality support, fallback, or downgrade semantics are
  claimed without evidence or are represented falsely;
- an external A2A peer is contacted outside the gateway, trust, replay, and
  conformance boundary;
- runtime state is written into the graph definition, or retry evidence is
  overwritten instead of recorded as a distinct attempt;
- required compile/dry-run/runtime/evaluation evidence is missing for a
  pattern labeled `productized`;
- any durable artifact contains an API key, bearer token, cookie, authorization
  header, raw credential, or unredacted peer secret.

### Degradable warnings

The following MAY remain warnings only when the launch remains safe and the
limitation is explicit in the status and operator surface:

- optional GUI layout hints or a missing convenience GUI projection in this
  no-new-GUI track;
- an unavailable optional provider route when the graph has an explicit
  approved fallback or is kept in `validated` status;
- an optional modality or tool not requested by the current graph;
- missing non-required human-summary polish when the typed machine result and
  artifact contract are complete;
- an adapter-specific feature that is declared unsupported and is not silently
  advertised as supported;
- documentation, metrics, or template ergonomics debt that does not weaken
  runtime safety, truthfulness, or reproducibility.

Warnings MUST be preserved in validation or run evidence and MUST NOT be
silently promoted to a pass by the GUI or a skill prompt.

## Success criteria for this track

The skill-first track is successful only when all of the following are true:

1. Every shipped initial pattern has a versioned skill/preset manifest and a
   canonical graph representation.
2. The same graph compiler and runtime accept skill-authored and code-authored
   definitions; there is no skill-only scheduler.
3. MCP is the observable capability boundary for all normal tool/resource/
   multimodal execution, including first-party loopback calls.
4. Cross-provider handoff is represented by the internal envelope, and every
   external peer path is visibly attributable to the A2A gateway.
5. Default runs are shallow, finite, isolated, and fail closed on agent-count,
   parallelism, token, retry, approval, or nesting violations.
6. A candidate cannot be labeled `productized` without lint, dry-run, fixture
   runtime, typed communication, secret-scan, guardrail, and runbook evidence.
7. Provider and external-A2A claims are separately qualified and retain
   truthful downgrade behavior.
8. No new GUI authoring surface is required to author, validate, dry-run, or
   launch the initial skill set in this track.

## Change and evidence policy

Changes to this boundary require an entry in the active skill-first plan's
progress log explaining the evidence, affected owner, and compatibility path.
Changing a numeric default in a later step is allowed only if the invariant
remains finite, explicit, fail-closed, and covered by tests/evidence.

Preserve plans, graph files, compiled plans, dry-run reports, run manifests,
envelopes, traces, screenshots, validation notes, and sanitized raw results by
default. Never persist secrets. A new implementation MUST link its evidence
back to this contract and the owning schema/runtime source rather than copying
the contract into a parallel document.

## Related sources

- [Skill-first execution plan](./ASTRABRIDGE_SKILL_FIRST_MULTI_PROVIDER_AGENT_ORCHESTRATION_EXECUTION_PLAN.md)
- [Canonical graph contract](./AGENT_ORCHESTRATION_GRAPH_CONTRACT.md)
- [Protocol/runtime baseline](./ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md)
- [Product stability/interoperability plan](./ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md)
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_compiler.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/`
- `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`
- `apps/astrabridge-sidecar/skills/agent-orchestration-operator/SKILL.md`
