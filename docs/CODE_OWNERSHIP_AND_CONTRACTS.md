# Code Ownership And Contract Boundaries

Last updated: 2026-07-17

## Purpose

This document names the canonical owner for high-risk AstraBridge contracts. It prevents an implementation detail, compatibility representation, or UI projection from becoming a second business contract.

Run the boundary audit before changing any owner or bridge:

```powershell
python scripts/contract_boundary_audit.py
```

The quick local gate runs the same audit.

## Current Boundaries

| Concern | Canonical owner | Compatibility or projection boundary | Required validation |
| --- | --- | --- | --- |
| Provider metadata, capability policy, reasoning and safety defaults | `astrabridge_sidecar.providers.profile` and `providers.registry` | `router_config_service.py` persists user overrides and derives runtime profiles; it must not create a second provider-family policy. | Provider catalog/compatibility tests and transport registry audit. |
| Provider wire selection | `astrabridge_sidecar.providers.transports` | `router_service.py` selects a registered transport, performs HTTP/SSE plumbing, and must not contain provider-specific transport implementations. | `test_router_transport_registry.py` plus retired-symbol governance gate. |
| Provider runtime client lanes and lifecycle leases | `astrabridge_sidecar.runtime_client_pool.RuntimeClientPool` with `runtime_service.py` as the integration owner | Each lane owns its app-server client, private environment, Codex home, concurrency lease, and restart/reap policy; `RuntimeService._client` is only a compatibility projection. | Barrier-controlled lane tests, runtime service regressions, pool snapshot secret scan, and process audit. |
| Normalized provider result | `astrabridge_sidecar.providers.ir` | Individual transports normalize upstream wire payloads into `NormalizedResponse`; router streaming projects that result for the client. | Provider compatibility, tool-call and router transport tests. |
| Versioned cross-provider protocol schemas and generated types | `astrabridge_sidecar.protocol.schema.v1/protocol.json` with `scripts/generate_protocol_types.py` | `agent_orchestration_contract.py`, `task_graph_contract.py`, and inline Desktop types are compatibility bridges; generated AstraBridge types live under `protocol/generated` and `src/astrabridge_protocol/generated`, separate from Codex/app-server generated types. | Protocol schema fixtures, Python/TypeScript generation freshness, migration tests, and this boundary audit. |
| Agent Envelope, delivery events, and artifact references | `astrabridge_sidecar.protocol` | Existing task-graph input/output envelopes and `agent_orchestration_contract.py` are compatibility projections; no provider transcript or UI summary may become a second envelope. | Envelope validation, delivery idempotency, artifact URI safety, and cross-provider handoff tests. |
| MCP protocol core and broker boundary | `astrabridge_sidecar.protocol` (MCP core/broker migration target) | `mcp_config_service.py` owns MCP configuration/presets; existing named MCP servers are compatibility adapters until the shared core/broker steps land. Capability implementations remain in `capabilities/`. | MCP conformance, broker routing, policy/approval, and direct-bypass boundary tests. |
| Persisted project task graph and run history | `task_graph_contract.py` | `task_service.py` owns storage/API lifecycle and validates all persisted graph/run payloads. | `test_task_graph_contract.py`, task-graph API/runtime tests, and contract boundary audit. |
| Durable graph run state, scheduler commands, and ordered events | `astrabridge_sidecar.durable_run_store.DurableRunEventStore` plus `astrabridge_sidecar.graph_scheduler.DurableGraphScheduler` | Workspace-local `.astrabridge/durable_runs.sqlite3` is the transactional source of truth; `DurableGraphScheduler` owns admission/dispatch callbacks; `task_service.py` JSON, run manifests, diagnostics, and UI refs remain redacted compatibility projections/rebuildable exports. | Store migration, CAS/terminal-state, lease/recovery, idempotency, projection-rebuild, bounded scheduler, and request-disconnect tests. |
| Portable, typed agent orchestration graph | `agent_orchestration_contract.py` | `agent_orchestration_compiler.py` compiles canonical graphs. `lift_task_graph_to_agent_orchestration_graph` and `lower_agent_orchestration_graph_to_task_graph` are the only format bridge. | Agent orchestration contract/compiler/check tests and contract boundary audit. |
| Canonical NodeType registry and compiled graph executable metadata | `astrabridge_sidecar.protocol` (registry migration target) | Existing role palette and Desktop graph components are projections/aliases; they may not create a second node schema. | Registry fingerprint, migration, compiler, and unknown-node preservation tests. |
| Desktop graph rendering and edits | Desktop runtime graph components | Desktop may project and edit validated API payloads, but may not invent a different graph schema or bypass Sidecar validation. | Desktop typecheck/build and task-graph UI tests. |

## Task Graph Ownership Rules

- `.abproj` task state remains the persisted lifecycle contract. Its graph and run schema versions are declared in `task_graph_contract.py`.
- `astrabridge-agent-orchestration-graph-v1` is the portable, typed authoring and compilation contract. It carries ports, modality claims, prompts, isolation and handoff rules that the persisted task graph cannot fully express.
- Conversion is intentionally lossy in the canonical-to-persisted direction. New semantics belong in the orchestration contract and require an explicit lowering policy; no caller may copy fields ad hoc between the two dictionaries.
- `TaskService._sync_orchestration_graph_with_task_graph` is the only lifecycle synchronizer. It must preserve graph identity, topology and entry-node ownership. It is not a second validator.
- `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/schema/v1/protocol.json` is the canonical cross-provider schema source. `scripts/generate_protocol_types.py --check` is the freshness gate; `protocol/compatibility.py` is the only legacy graph/artifact migration adapter.
- `DurableRunEventStore` owns live run identity, state-version CAS, ordered events, node attempts, leases, inbox/outbox records, and external-operation lineage. Legacy task JSON and manifests are imported idempotently; active legacy runs become `needs_review` and are never resumed implicitly.
- `DurableGraphScheduler` owns the asynchronous receipt/worker seam. `RuntimeService.execute_task_graph_run` remains a synchronous compatibility adapter for explicit callers/tests; the normal HTTP route uses `queue_task_graph_run` and reads `graph_run_status` from the durable projection.
- Durable projections must be deterministic and rebuildable from the workspace-local store. No provider secret, bearer token, cookie, or external artifact path may be persisted in the store; legacy source files and private evidence remain untouched.

## Provider Ownership Rules

- A provider family is registered once in `providers/transports/__init__.py`. Router code resolves the class through `transport_class_for_profile(...)`.
- Provider-private request fields, response parsing and reasoning conventions stay in the owning transport subclass.
- Shared message conversion, tool projection, image handling, response summary/redaction and normalized result types stay in `providers/transports/base.py` and `providers/ir.py`.
- Historical inline adapters are archived evidence only. Their names are prohibited in current runtime code by `scripts/repo_governance_check.py`.

## Stability Plan Ownership Rules

- `PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md` is the only active scheduler for cross-provider protocol, durable graph runtime, MCP broker, Agent Envelope, NodeType registry, and related release-gate work.
- Capability-specific adapter qualification remains independent, but any shared MCP transport, envelope, artifact, run-state, or scheduler change must be implemented through that stability plan.
- `astrabridge_sidecar.protocol` owns cross-provider schemas; `astrabridge_sidecar.durable_run_store.DurableRunEventStore` owns durable run state. Existing graph, capability, and Desktop modules are bridges until a numbered migration step moves their consumers; they must not silently add parallel schema fields.
- The new owner boundary does not authorize a wholesale rewrite. Each bridge must have a compatibility test, an explicit migration status, and a removal or sunset condition.

## Change Rules

1. Change the canonical owner first, then update bridges and projections.
2. Add a contract test that fails on the old field or route shape before accepting a migration.
3. Extend `scripts/contract_boundary_audit.py` when a new provider family, graph schema or bridge is introduced.
4. Keep a compatibility shim free of business logic. Record its replacement and sunset state in `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md` and `docs/INTERFACE_GOVERNANCE.md`.
5. Do not use source-string replacement or unvalidated dictionary mutation for graph contract conversion.

## Current Automated Evidence

`scripts/contract_boundary_audit.py` validates every built-in persisted task-graph fixture and every built-in orchestration example through validation, conversion and compilation. It fails if graph identity, node/edge topology, entry-node ownership, schema versions or the provider transport registry drift.

The same audit also verifies that the stability plan, protocol package marker, durable run-store owner, capability-plan delegation, and this ownership table agree. A future migration may tighten direct-bypass checks, but it must first update the canonical owner and its compatibility boundary here.
