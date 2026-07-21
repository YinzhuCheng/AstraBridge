# AstraBridge Skill-Backed Orchestration MCP Surface Contract

Status: normative for the skill-first orchestration track
Version: `astrabridge-skill-backed-orchestration-mcp-v1`
Schema: [astrabridge-skill-backed-orchestration-mcp-v1.schema.json](./schemas/astrabridge-skill-backed-orchestration-mcp-v1.schema.json)
Related contract: [ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md](./ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md)

## Purpose and ownership

This contract defines the single MCP-facing control surface for proposing,
reviewing, and operating skill-backed orchestration. It is a control-plane
contract, not a second scheduler or a second skill runtime.

The ownership chain is fixed:

```text
MCP tools/call
  -> McpBrokerService (transport, policy, audit, idempotency)
  -> skill-to-graph resolver
  -> canonical AgentOrchestrationGraph compiler
  -> existing durable graph scheduler and run/event store
  -> AgentEnvelope, ArtifactRef, and redacted projections
```

The MCP server is named `astrabridge-orchestration`. Every normal caller,
including AstraBridge loopback callers, uses the broker and the same MCP
request/result, policy, approval, timeout, and audit semantics. A caller must
not call the graph HTTP routes, provider SDKs, scheduler, or capability runtime
directly to implement an orchestration operation.

This track does not add GUI authoring. Existing GUI and HTTP routes remain
compatibility/operator projections until the canonical MCP surface is
implemented in Step 11.

## Tool names and operation IDs

The MCP `tools/list` response exposes exactly these v1 orchestration tools.
Each tool receives one request object from the schema and returns one response
object through `structuredContent` plus a bounded text projection.

| MCP tool | `operation` | Side effect | Canonical owner used by the implementation |
| --- | --- | --- | --- |
| `astrabridge_orchestration_propose` | `propose` | none | skill resolver plus graph compiler |
| `astrabridge_orchestration_patch` | `patch` | immutable candidate only | resolution/graph contract and snapshot services |
| `astrabridge_orchestration_validate` | `validate` | none | manifest validator, graph contract, compiler, policy checks |
| `astrabridge_orchestration_dry_run` | `dry_run` | preserved validation artifacts only | existing graph dry-run/compiler path |
| `astrabridge_orchestration_diff` | `diff` | none | orchestration diff and graph snapshot services |
| `astrabridge_orchestration_launch` | `launch` | queues a bounded run | `runtime_graph_run_dispatch_service` and durable scheduler |
| `astrabridge_orchestration_inspect` | `inspect` | none | durable graph run status/events projection |
| `astrabridge_orchestration_cancel` | `cancel` | monotonic run cancellation | graph dispatch cancellation and durable run store |
| `astrabridge_orchestration_recover` | `recover` | creates a bounded recovery run | graph recovery service and durable scheduler |

The operation ID is the unprefixed value in the table. The tool name and
operation must agree; a mismatch is a protocol error and is not guessed or
silently remapped.

## Common request rules

Every request has:

- `direction: "request"`;
- `schema_version: "astrabridge-skill-backed-orchestration-mcp-v1"`;
- a caller-generated `request_id`;
- an optional `operation_id`, `idempotency_key`, and `trace_id`;
- an optional `policy_tightening` object.

The `skill_ref` contains the stable skill ID and semantic version. A resolved
operation additionally carries a `resolution_ref` containing the resolution
ID, manifest digest, and canonical graph digest. Digests are SHA-256 values
formatted as `sha256:<64 hexadecimal characters>`.

Parameters are checked against the manifest's `parameter_schema` before graph
binding. Unknown parameters, undeclared graph paths, private-memory fields,
credentials, authorization material, raw provider reasoning, and secret-like
values are rejected. The schema's `x-forbidden-properties` list is a minimum
deny list; the runtime performs a case-insensitive recursive value/key scan as
well.

Request-level changes are monotonic tightening only. A request may lower a
budget, narrow a provider/model route, require approval, or reduce context.
It may not widen the manifest, graph, MCP, A2A, approval, communication, or
composition policy.

## Operation semantics

### `propose`

`propose` resolves a `skill_ref` and parameters into a `resolution_ref`, a
canonical graph, a compiled-plan digest, and diagnostics. It never launches a
provider call or agent. `evidence_mode` may request resolve-only, validation,
or dry-run evidence; any requested mode still stops before live dispatch.

The resolver must reject a missing/ambiguous manifest, multiple graph sources,
unknown parameters, unsafe bindings, cyclic template references, or a
candidate that has no launchable evidence. A proposal is not a productized
skill merely because it has a graph payload.

### `patch`

`patch` creates a new immutable resolution candidate from an existing
`resolution_ref`. Patches are bounded (at most 64) and may address only
`/parameters/...` or `/graph/...` paths. They are validated and re-digested;
the original resolution remains immutable. Patches cannot edit runtime state,
provider credentials, hidden prompt/reasoning state, MCP server registration,
A2A trust, approval requirements, or budget ceilings. A patch that attempts to
remove a required field or widen a policy is rejected.

### `validate`

`validate` runs the selected checks (`manifest`, `graph`, `compile`, `policy`,
`mcp`, `a2a`, and `secrets`) against a resolution or a skill plus parameters.
It returns actionable warnings and blockers and preserves no live state. The
minimum product admission checks are manifest/schema validation, canonical
graph validation, compile, policy/budget validation, MCP declaration/policy
validation, and secret scan.

### `dry_run`

`dry_run` requires a resolved graph and a complete finite `budget`. It executes
the existing fixture/compiler dry-run path with no live provider calls, emits
the compiled plan and policy snapshot, and returns a `dry_run_receipt`-eligible
digest. A live launch must prove that its resolution and policy digests match
an unexpired dry-run receipt.

### `diff`

`diff` compares two immutable resolution references. The caller may request
manifest, parameter, graph, compiled-plan, or policy differences. The result
must identify topology, route, MCP, approval, budget, context, and artifact
changes separately; a text-only summary is not sufficient for admission.

### `launch`

`launch` is the only operation that may queue a run. It requires:

1. a `resolution_ref` with manifest and graph digests;
2. a complete `budget` object;
3. an explicit `approval` object;
4. an `idempotency_key` bound to the complete request fingerprint;
5. an unexpired `dry_run_receipt` whose graph and policy digests match;
6. an explicit `mode` (`fixture` or `live`).

The runtime re-checks lifecycle status, provider/model capability, MCP policy,
A2A gateway/card trust, graph depth, typed contracts, and all limits before
provider dispatch. `candidate` and unresolved `validated` resolutions cannot
be launched as product features. A launch returns `accepted` with a durable
`run_id` or a fail-closed `blocked`/`failed` response; it must not silently
fall back to an unbounded or GUI-only route.

### `inspect`

`inspect` reads a durable run projection by `run_id`. `compact` is the default;
`summary` adds bounded run/node summaries; `events` uses an explicit cursor and
at most 200 events per call. Private memory, provider-private reasoning, raw
credentials, and unredacted transcripts are never returned. MCP Tasks, if
negotiated, are transport conveniences only and never replace AstraBridge's
durable run/event source.

### `cancel`

`cancel` requires a run ID, a human-readable bounded reason, and an
`idempotency_key`. An optional expected state version provides compare-and-swap
protection. Cancellation is monotonic and preserves cancellation reports,
event lineage, and diagnostic artifacts. There is no `force` escape hatch in
v1; a stale state version or terminal run returns a structured conflict or
terminal projection rather than mutating unrelated state.

### `recover`

`recover` creates a new bounded recovery run from an existing run. The strategy
must be explicit: `resume_run`, `retry_failed_nodes`, `rerun_selected_nodes`,
or `partial_execution`. The latter two require a non-empty, bounded
`selected_node_ids` list. Recovery also requires a complete budget, approval,
idempotency key, mode, source state version when available, and a fresh
dry-run receipt for the recovery selection. The runtime validates dependency
closure and typed artifacts before scheduling. Unsupported live recovery,
unknown nodes, stale state, or a request to retry beyond the declared budget
fails closed; it never silently turns into a whole-graph rerun.

## Bounded launch and recovery policy

These are v1 protocol ceilings, not permission to consume the full values.
The effective value is the minimum of the hard product boundary, manifest,
graph, runtime, and request limits. Step 8 may lower ceilings but may not raise
them without a contract revision.

| Field | Required | v1 ceiling/default deny |
| --- | --- | --- |
| `max_depth` | yes | exactly `2` |
| `max_total_agents` | yes | `1..16` |
| `max_parallel_agents` | yes | `1..8` and never above total agents |
| `max_total_tokens` | yes | `1..1,000,000` |
| `max_provider_calls` | yes | `1..64` |
| `max_retries` | yes | `0..8` |
| provider/model concurrency | yes | each entry `1..8` |
| `allow_nested_subagents` | yes | exactly `false` |
| `allow_direct_teammate_messages` | yes | exactly `false` |
| dry-run before live | yes for launch/recovery | receipt required and digest-bound |

There is no unbounded, omitted, `null`, or implicit budget. An invalid,
missing, or exceeded value blocks admission before provider dispatch. Fan-out
must be represented by finite canonical graph nodes and edges; MCP calls cannot
spawn new orchestration roots, and a running node cannot recursively invoke a
skill as a subagent.

## Response envelope and fail-closed behavior

Every response has `direction: "response"`, the same schema version,
`operation`, `operation_id`, a status, immutable `provenance`, a complete
`policy_snapshot`, and arrays for `warnings` and `blockers`. `blocked` and
`failed` responses must include a structured `error`; warnings are not a
substitute for blockers. `accepted` responses include a durable run reference;
`completed` responses include operation-specific result data and preserved
artifacts.

The following conditions are release-blocking protocol errors:

- unknown tool/operation or tool/operation mismatch;
- schema-version mismatch, missing identity/digest, malformed parameters, or
  secret-like content;
- unresolved or ambiguous skill source, cyclic composition, unsafe graph path,
  invalid typed contract, or graph/compiler failure;
- policy widening, missing finite launch/recovery budget, nested subagents,
  direct teammate messaging, unbounded fan-out, or exceeded concurrency;
- missing/mismatched dry-run receipt, approval, provider capability, MCP policy,
  A2A card, or gateway trust;
- idempotency-key reuse with a different request fingerprint;
- stale graph/run revision, unsupported recovery strategy, or missing selected
  node/dependency closure.

Transport timeout or an uncertain remote MCP delivery is represented as
`pending` with durable operation identity when possible. The product claims
at-least-once delivery plus durable idempotency/deduplication, never
network-level exactly-once execution.

## Current owner mapping and implementation boundary

Step 4 freezes this contract only. Step 11 will expose these tools through the
existing `McpServerCore` and `McpBrokerService`, and will delegate to the
existing graph compiler, `TaskGraphService`, `runtime_graph_run_dispatch_service`,
durable run store, internal envelope, and A2A gateway. No graph scheduler,
provider adapter, MCP transport, or GUI state is duplicated here.

The existing HTTP/CLI routes remain compatibility evidence and implementation
adapters. They do not become a second public skill protocol. The first MCP
implementation must preserve redaction, workspace-scoped artifacts, audit
events, approval state, and recovery evidence already owned by those services.

## Reference request and response

The following examples are schema-valid protocol shapes. Digests are synthetic
fixtures and do not contain credentials.

```json
{
  "direction": "request",
  "schema_version": "astrabridge-skill-backed-orchestration-mcp-v1",
  "operation": "launch",
  "request_id": "req_skill_launch_001",
  "idempotency_key": "idem_skill_launch_001",
  "resolution_ref": {
    "resolution_id": "resolution_supervisor_001",
    "skill_ref": {
      "skill_id": "astrabridge.supervisor-worker-synthesizer",
      "version": "1.0.0",
      "manifest_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    },
    "manifest_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "graph_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  },
  "budget": {
    "max_depth": 2,
    "max_total_agents": 4,
    "max_parallel_agents": 2,
    "max_total_tokens": 80000,
    "max_provider_calls": 4,
    "max_retries": 2,
    "provider_concurrency": [{"provider_id": "qwen", "max_active_agents": 2}],
    "model_concurrency": [{"provider_id": "qwen", "model_id": "qwen3.7-plus", "max_active_agents": 2}],
    "allow_nested_subagents": false,
    "allow_direct_teammate_messages": false
  },
  "approval": {
    "mode": "manual",
    "approval_ref": "approval_workspace_review_001",
    "risky_effects_require_approval": ["provider_call", "file_write"]
  },
  "dry_run_receipt": {
    "operation_id": "dry_run_supervisor_001",
    "graph_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "policy_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "expires_at": "2026-07-21T12:00:00Z"
  },
  "mode": "fixture"
}
```

```json
{
  "direction": "response",
  "schema_version": "astrabridge-skill-backed-orchestration-mcp-v1",
  "operation": "launch",
  "operation_id": "op_skill_launch_001",
  "status": "accepted",
  "provenance": {
    "resolution_id": "resolution_supervisor_001",
    "skill_ref": {
      "skill_id": "astrabridge.supervisor-worker-synthesizer",
      "version": "1.0.0",
      "manifest_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    },
    "manifest_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "graph_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  },
  "policy_snapshot": {
    "max_depth": 2,
    "max_total_agents": 4,
    "max_parallel_agents": 2,
    "max_total_tokens": 80000,
    "max_provider_calls": 4,
    "max_retries": 2,
    "allow_nested_subagents": false,
    "allow_direct_teammate_messages": false
  },
  "warnings": [],
  "blockers": [],
  "result": {
    "run_id": "graph-run-live-fixture-001",
    "run_status": "queued",
    "scheduler": "durable_graph_scheduler_v1"
  },
  "artifacts": []
}
```
