# AstraBridge Skill-To-Graph Contract

Status: normative for skill-backed orchestration authoring and resolution
Version: `astrabridge-skill-to-graph-v1`
Schema: [astrabridge-skill-to-graph-manifest-v1.schema.json](./schemas/astrabridge-skill-to-graph-manifest-v1.schema.json)
Last updated: 2026-07-21

## Purpose and ownership

This contract defines how a reusable orchestration skill or preset becomes a
canonical `AgentOrchestrationGraph` input. It does not execute agents and does
not replace the graph validator, compiler, scheduler, MCP broker, protocol
store, provider adapters, or external A2A gateway.

The ownership chain is intentionally one-way:

```text
SKILL.md / skill manifest
        |
        v
SkillGraphResolution (derived, immutable for the request)
        |
        v
AgentOrchestrationGraph (canonical authoring/interchange definition)
        |
        v
compiled plan -> durable scheduler -> run events / envelopes / artifacts
```

- The skill registry owns discovery, provenance, install state, enablement,
  and compatibility of skill packages.
- This contract owns the machine-readable orchestration manifest and its
  resolution semantics.
- `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md` and
  `agent_orchestration_contract.py` own the graph shape and validation.
- `agent_orchestration_compiler.py` owns lowering to the execution plan.
- `astrabridge_sidecar.protocol` owns durable envelopes, content parts,
  artifacts, and delivery events.
- MCP and external A2A remain their existing owners. A manifest may reference
  their policies, but it cannot redefine their wire or durable schemas.

A skill manifest is therefore a declarative, reviewable input. It is not a
second scheduler, an executable agent team, or a provider-specific DSL.

## Product boundary

### A skill manifest MUST

- carry a stable `skill_id`, semantic `version`, kind, lifecycle status, and
  provenance-safe metadata;
- reference exactly one graph template/preset or one approved project graph
  source, with a canonical graph schema version;
- declare the parameter schema and the finite set of graph paths those
  parameters may bind to;
- declare typed input/output contracts, artifact expectations, prompt
  variables, provider/model routing policy, MCP policy, approval policy,
  context/communication policy, subagent policy, and finite budgets;
- declare compatibility requirements and the evidence level required before
  the skill may be treated as `productized`;
- remain resolvable without a GUI, a provider call, or an agent invocation.

### A skill manifest MUST NOT

- contain an agent scheduler, queue, retry loop, hidden run-state store, or
  provider SDK/HTTP execution code;
- launch a second skill recursively at runtime;
- widen graph, MCP, approval, context, provider, or A2A permissions through an
  untyped parameter;
- pass private memory, provider-private reasoning, credentials, cookies,
  authorization headers, or raw provider payloads into graph inputs;
- bypass MCP for tools, resources, or multimodal capabilities;
- turn an external A2A card into an internal durable protocol or peer registry.

## Manifest shape

The machine-readable shape is defined by the JSON Schema linked at the top of
this document. The following fields are normative.

| Section | Required responsibility |
| --- | --- |
| `schema_version` | Exact manifest schema identifier. |
| `skill_id`, `version`, `kind`, `status` | Stable identity and product lifecycle. `kind` is `orchestration_skill`; status is `candidate`, `validated`, `productized`, `provider-qualified`, or `external-a2a-qualified`. |
| `metadata` | Human description, tags, owners, and non-secret provenance notes. |
| `resolution` | One graph source (`builtin_template`, `project_graph`, or `inline_graph`), canonical graph schema version, parameter schema, and allowlisted graph-path bindings. |
| `prompt` | Inline or registry-referenced prompt template plus a typed variables schema. Prompt text is graph input, never an execution engine. |
| `contracts` | Typed input/output schema refs, required message parts, and artifact specs. |
| `policies.routing` | Allowed provider/model/profile routes, modality/capability requirements, and fallback/downgrade posture. |
| `policies.mcp` | MCP preset/server/tool references, approval mode, effect classes, and call budgets. |
| `policies.communication` | History/artifact projection, private-memory exclusion, machine-result and summary inclusion, and direct-message posture. |
| `policies.subagent` | Isolation, max turns, nested-agent default deny, and direct-teammate-message default deny. |
| `policies.budget` | Total agents, parallel agents, total tokens, provider calls, retries, and provider/model concurrency caps. |
| `policies.approval` | Default approval mode and effects that always require approval. |
| `policies.a2a` | Whether external A2A is allowed, approved `a2a_card:` refs, minimum trust, and the mandatory gateway boundary. |
| `composition` | Compile-time graph-template references only; runtime nesting is always false in v1. |
| `compatibility` | Canonical graph schema, minimum runtime, supported legacy sources, and migration notes. |
| `evidence` | Required evidence level, deterministic fixture ref, and sanitized artifact root. |

## Reference manifest

This is a minimal, safe shape for a supervisor/worker/synthesizer pattern. It
is illustrative but schema-valid; it does not launch a run by itself.

```json
{
  "schema_version": "astrabridge-skill-to-graph-manifest-v1",
  "skill_id": "astrabridge.supervisor-worker-synthesizer",
  "version": "1.0.0",
  "kind": "orchestration_skill",
  "status": "candidate",
  "metadata": {
    "display_name": "Supervisor / Worker / Synthesizer",
    "description": "Bounded shallow orchestration with typed synthesis.",
    "tags": ["supervisor", "worker", "synthesis"],
    "owners": ["astrabridge-core"]
  },
  "resolution": {
    "mode": "builtin_template",
    "graph_template_ref": "supervisor_worker_synthesizer",
    "graph_schema_version": "astrabridge-agent-orchestration-graph-v1",
    "parameter_schema": {
      "type": "object",
      "properties": {
        "task_goal": {"type": "string", "minLength": 1}
      },
      "required": ["task_goal"],
      "additionalProperties": false
    },
    "bindings": [
      {"parameter": "task_goal", "graph_path": "input.task_context", "required": true}
    ]
  },
  "prompt": {
    "mode": "reference",
    "template_ref": "prompt.supervisor_worker_synthesizer.v1",
    "variables_schema": {"type": "object", "required": ["task_goal"]}
  },
  "contracts": {
    "input": {
      "schema_ref": "schema.skill_supervisor_input",
      "required_message_parts": ["text"],
      "artifact_specs": []
    },
    "output": {
      "schema_ref": "schema.skill_supervisor_output",
      "required_message_parts": ["machine_result", "human_summary"],
      "artifact_specs": [{"kind": "run_summary", "id": "final_summary"}]
    }
  },
  "policies": {
    "routing": {
      "selection_mode": "bounded_pool",
      "allowed_provider_ids": ["qwen"],
      "allowed_model_ids": ["qwen3.7-plus"],
      "fallback_mode": "catalog_verified",
      "required_capabilities": ["text", "structured_json"]
    },
    "mcp": {
      "preset_ids": ["astrabridge_capabilities"],
      "tool_rules": [],
      "approval_mode": "ask",
      "loopback_allowed": true
    },
    "communication": {
      "history_mode": "latest_summary_only",
      "artifact_mode": "required_output_only",
      "exclude_private_memory": true,
      "include_machine_results": true,
      "include_human_summaries": true,
      "allow_direct_teammate_messages": false
    },
    "subagent": {
      "isolation_mode": "lane",
      "max_turns": 8,
      "allow_nested_subagents": false,
      "allow_direct_teammate_messages": false
    },
    "budget": {
      "max_total_agents": 4,
      "max_parallel_agents": 2,
      "max_total_tokens": 80000,
      "max_provider_calls": 4,
      "max_retries": 2,
      "provider_concurrency": [{"provider_id": "qwen", "max_active_agents": 2}],
      "model_concurrency": [{"provider_id": "qwen", "model_id": "qwen3.7-plus", "max_active_agents": 2}]
    },
    "approval": {
      "default_mode": "ask",
      "risky_effects_require_approval": ["file_write", "provider_call", "external_write"]
    },
    "a2a": {
      "external_enabled": false,
      "allowed_card_refs": [],
      "minimum_trust_level": "workspace_trusted",
      "gateway_required": true
    }
  },
  "composition": {
    "allow_runtime_nesting": false,
    "max_expansion_depth": 1,
    "template_refs": []
  },
  "compatibility": {
    "graph_schema_version": "astrabridge-agent-orchestration-graph-v1",
    "min_runtime_version": "0.1.0",
    "legacy_sources": ["astrabridge-task-graph-v1"],
    "migration_notes": []
  },
  "evidence": {
    "required_level": "productized",
    "fixture_ref": "fixture.supervisor_worker_synthesizer",
    "artifact_root": "PRIVATE/skill-first-orchestration/skills/"
  }
}
```

## Resolution contract

The resolver consumes a manifest plus a bounded request:

```text
SkillGraphResolutionRequest
  skill_ref: { skill_id, version, optional_digest }
  parameters: object
  requested_route: optional provider/model/profile restriction
  requested_budget: optional tightening-only overrides
  mode: validate | dry_run | launch
```

It returns a derived, immutable resolution record:

```text
SkillGraphResolution
  manifest_digest
  resolved_skill_ref
  source_ref and source_digest
  canonical_graph (AgentOrchestrationGraph)
  graph_digest
  policy_snapshot
  warnings[]
  blockers[]
  status: candidate | validated | productized | blocked
```

Resolution MUST follow these steps in order:

1. Load the skill record and manifest from the skill registry; verify
   `skill_id`, semantic version, digest when supplied, lifecycle status, and
   compatibility constraints.
2. Resolve exactly one graph source. A builtin template must come from the
   canonical graph/template catalog; a project graph must be workspace-safe;
   an inline graph must already be a canonical graph payload. No prose-only
   inference may create nodes.
3. Validate the parameter object against `resolution.parameter_schema` and
   apply only declared `bindings`. Reject unknown parameters and graph paths.
4. Render the prompt through the existing graph prompt contract. Prompt
   variables may fill declared templates but may not alter policies, tool
   servers, graph topology, or approval requirements.
5. Merge manifest policies into the graph as explicit policy snapshots. A
   request may tighten a limit or route; it may not widen a manifest or
   boundary limit without a new approved manifest version.
6. Attach `skill_provenance` as non-authoritative graph metadata and compiled
   plan metadata: manifest digest, source digest, resolver version, and
   requested parameter names (never parameter secrets or raw prompt payloads).
7. Run the canonical graph validator and compiler, then the normal dry-run.
   The resolver returns blockers; it does not bypass a failed check to launch.
8. For `launch`, pass only the validated canonical graph and policy snapshot
   to the canonical MCP/scheduler entry point defined in later plan steps.

The resolver MUST be deterministic for the same manifest digest, source digest,
parameters, runtime contract, and routing catalog snapshot. It MUST NOT call a
provider, invoke an MCP tool, spawn an agent, or write live run state while
resolving `validate` or `dry_run`.

## Policy precedence and tightening rules

The effective policy is calculated in this order, from strongest to weakest:

1. hard product boundary and runtime safety gates;
2. manifest policy and lifecycle/evidence level;
3. canonical graph/template policy;
4. request-level overrides.

Only monotonic tightening is allowed at request level:

- lower a budget, reduce parallelism, narrow a provider/model allowlist, add an
  approval gate, or reduce context visibility: allowed;
- increase a budget, add a provider/model, expose a new MCP server/tool, share
  private memory, enable nested subagents/direct messages, or bypass A2A
  gateway: blocked;
- a missing manifest field or malformed policy: blocked, never defaulted into
  an unbounded launch.

For v1 the following values are mandatory and fail closed when absent:

- graph depth at most `2`;
- `allow_runtime_nesting=false`;
- `allow_nested_subagents=false`;
- `allow_direct_teammate_messages=false`;
- positive `max_total_agents`, `max_parallel_agents`, `max_total_tokens`, and
  `max_provider_calls`;
- non-negative `max_retries` and explicit provider/model concurrency entries
  whenever more than one route is allowed;
- `exclude_private_memory=true` and `requires_dry_run_before_live=true`.

## Composition and migration rules

### Composition

Manifest composition is a compile-time graph-template reference, not runtime
skill nesting. V1 permits `max_expansion_depth=1`, requires an acyclic
`template_refs` list, and fixes `allow_runtime_nesting=false`. A future nested
composition feature would require a new schema version, explicit total-agent
and token accounting, and user approval.

### Existing `SKILL.md`

The current prose skill remains an authoring/operator companion. A discovery
adapter may create a `candidate` manifest with:

- `skill_id` derived from the stable skill name and source identity;
- `version` from the owning package or `0.0.0-discovered` when absent;
- provenance, description, trigger, and dependency hints copied as metadata;
- no graph source and no launchable policy until a maintainer adds them.

Therefore a discovered prose skill is never silently treated as a
productized orchestration skill.

### Existing project skill refs

`plugin_skill_presets` refs (`record_id`, `skill_name`, owner/source) remain
identity/enablement references. They may select a manifest, but they do not
become a graph, graph template, or launch request without resolution.

### Existing graph `template_id`

`template_id` is a canonical graph/template identifier. A manifest may set
`resolution.graph_template_ref` to it, but the reverse mapping is not inferred:
an arbitrary graph with a matching `template_id` does not acquire a skill
identity, lifecycle status, or product evidence automatically.

### Existing runtime `skill_ids`

Opaque node `skill_ids` are compatibility input only. A resolved run must add
the manifest/version/digest provenance snapshot before those IDs are accepted
as skill-backed execution. Unknown IDs remain a warning for compatibility
inspection and a blocker for `productized` launch.

### Legacy task graphs

Legacy `astrabridge-task-graph-v1` files may be lifted into canonical graphs by
the existing migrator. Migration does not invent a skill manifest. If a legacy
graph is later packaged as a skill, it must receive a new manifest and pass
canonical lint/dry-run/evidence gates.

## Status and failure semantics

- `candidate`: identity or intent exists; not launchable as a product feature.
- `validated`: manifest and graph resolve, compile, lint, dry-run, and secret
  checks pass; deterministic fixture evidence may still be absent.
- `productized`: required fixture, typed envelope, guardrail, evidence, and
  runbook gates pass.
- `provider-qualified`: a bounded authorized provider route is separately
  proven with truthful fallback/downgrade evidence.
- `external-a2a-qualified`: gateway and external conformance evidence is also
  present.
- `blocked`: a release-blocking contract, policy, capability, or evidence
  check failed.

Missing graph source, unknown parameter, unsafe binding, policy widening,
cyclic composition, missing finite budget, missing typed contract, MCP bypass,
unresolved external A2A card, or secret-like content is a blocker. Optional
GUI hints, unavailable optional routes, and non-required presentation polish
remain warnings only when the status is explicit and launch safety is intact.

## Source compatibility and non-goals

This contract intentionally does not:

- change the canonical graph schema in place;
- introduce a skill-only runtime or a second task scheduler;
- expose a new GUI authoring surface;
- define the MCP graph control operations (Step 4 owns that surface);
- implement runtime agent-count enforcement (Step 8 owns those checks);
- promote any existing example graph to a supported skill automatically.

The next implementation must use this contract as the input to Step 4's MCP
surface and Step 6's template library. Any field added later must preserve the
one-way resolution chain and the tightening-only policy.
