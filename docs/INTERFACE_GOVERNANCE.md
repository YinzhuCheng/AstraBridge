# AstraBridge Interface Governance

Last verified: 2026-07-16

## Purpose

This document defines how AstraBridge classifies and changes cross-boundary interfaces. The full machine-readable inventory is generated locally at [step4-interface-registry.json](/D:/AstraBridge/PRIVATE/app-standardization-ui-dogfood/docs-api/step4-interface-registry.json).

The registry is an inventory and investigation aid. It does not authorize deletion. Step 5 must revalidate every cleanup candidate against current source, tests, visible product behavior, preserved evidence, and any external caller contract.

## Source Of Truth

Run the read-only audit from the repository root:

```powershell
python scripts/interface_registry_audit.py --repo . --json-out PRIVATE/app-standardization-ui-dogfood/docs-api/step4-interface-registry.json
python -m unittest discover -s apps/astrabridge-sidecar/tests -p test_interface_registry_audit.py
```

The audit derives evidence from:

- sidecar and router HTTP handler ASTs;
- Desktop source HTTP literals and SSE consumers;
- sidecar and Desktop tests;
- registry-selected current and historical documentation;
- runtime scripts and internal callers;
- explicit SSE, payload, provider metadata, MCP, CLI/launcher, and compatibility-shim contracts.

For cross-provider runtime work, the active execution source is [ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md](/D:/AstraBridge/PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md). It owns the migration of protocol schemas, Agent Envelope/delivery events, durable run state, the MCP broker, and the NodeType registry. This governance inventory must not be used to schedule a parallel implementation.

Every interface records owner, schema source, definition evidence, consumer-search evidence, replacement, compatibility dependencies, removal prerequisites, and next investigation. Search evidence is bounded and cannot prove that an external or dynamically constructed caller does not exist.

## Status Taxonomy

| Status | Meaning | Step 5 behavior |
| --- | --- | --- |
| `current` | Defined and backed by a current Desktop, runtime, current-doc, or explicitly canonical contract. | Preserve unless a separately approved migration replaces it. |
| `deprecated` | Intentionally disabled or replaced, with an explicit successor. | Keep actionable rejection/migration behavior until callers are disproved. |
| `shim-only` | Old name or request shape delegates to a maintained implementation. | Prove replacement parity and caller migration before reduction. |
| `test-only` | Explicit fixture/debug surface, not normal product behavior. | Confirm test ownership and product unreachability before removal. |
| `historical` | Retained implementation reference with no intended runtime dispatch. | Confirm zero imports and preserve evidence before removal. |
| `unknown` | Definition exists, but current consumer search is insufficient to assign a stronger status. | Investigate; never delete from inventory evidence alone. |

## Current Inventory

The 2026-07-10 registry contains 251 interfaces:

| Status | Count |
| --- | ---: |
| `current` | 219 |
| `shim-only` | 14 |
| `unknown` | 12 |
| `deprecated` | 3 |
| `test-only` | 2 |
| `historical` | 1 |

| Family | Count |
| --- | ---: |
| HTTP sidecar/router routes | 217 |
| CLI/launcher | 8 |
| Runtime payload | 7 |
| Provider metadata | 7 |
| Compatibility shim | 6 |
| MCP | 4 |
| SSE | 2 |

All 179 HTTP paths found in non-test Desktop source map to at least one server definition. The registry contains 31 remaining cleanup candidates, and every candidate has definition evidence plus consumer-search evidence. All 31 have `safe_to_remove=false`.

## Known Compatibility Interfaces

The main name or request-shape shims are:

- singular project aliases such as `/api/project/current` and `/api/project/open`, replaced by `/api/projects/*`;
- top-level task and turn aliases such as `/api/tasks*` and `/api/turn/*`, replaced by project/runtime-scoped paths;
- path-form agentic-update status/result routes, replaced by query-form routes;
- `sidecar_server.py`, replaced by `python -m astrabridge_sidecar.server`;
- legacy compatibility shims `lcr_web_mcp_server.py` and `LcrWebService`, retained only for old imports and replaced by AstraBridge-named Web implementations; new callers must not use them;
- legacy task-graph lifting, retained while old task graphs still need conversion into typed Agent Orchestration graphs;
- DashScope image/speech base-URL normalization, retained while configured profiles may still carry the older compatible-mode suffix.

The old inline provider adapter classes were removed from `router_service.py` on 2026-07-10 after a zero-import audit and focused transport regression. Their source block is preserved as private Step 5 evidence; runtime transport selection comes from `astrabridge_sidecar.providers.transports`.

The three `/api/official-codex/*` routes are `deprecated` guardrail endpoints. They return disabled responses and point to the LLM API Manager path; they are not OpenAI account-login support.

## Unknown Interfaces

The following definitions have no proven non-test Desktop, runtime, or current-doc consumer in the bounded search:

| Interface | Owner | Next investigation |
| --- | --- | --- |
| `GET /api/router/events` | router-provider | Check external diagnostics and replace with runtime events if equivalent. |
| `GET /api/router/image/prompt-guides` | router-provider | Check image prompt tooling and MCP callers. |
| `GET /api/router/image/yunwu/protocol` | router-provider | Check Yunwu tooling and preserved operator workflows. |
| `POST /api/llm-manager/mode/anonymous` | llm-api-manager | Check migration from older anonymous-session UI paths. |
| `POST /api/project/edit/preview` | project-runtime | Check external coding-tool and native-kernel callers. |
| `POST /api/project/edit/apply` | project-runtime | Check external coding-tool and native-kernel callers. |
| `POST /api/project/tasks/title` | project-runtime | Compare with `/api/project/tasks/title/suggest` and task rename flows. |
| `POST /api/router/image/prompt-rewrite/instruction` | router-provider | Check prompt-rewrite tooling and MCP callers. |
| `POST /api/router/image/yunwu/edit` | router-provider | Check legacy image UI and MCP callers. |
| `POST /api/router/image/yunwu/transparent-asset` | router-provider | Check legacy image UI and MCP callers. |
| `POST /api/router/keys/delete` | router-provider | Compare with LLM Manager key deletion and migration history. |
| `POST /api/router/mcp/preset/astrabridge-web` | router-provider | Check preset onboarding and automation callers. |

Each entry in the private registry includes the exact definition line, handler symbols, all searched scopes, observed matches, and generic removal prerequisites. These rows remain `unknown` until Step 5 collects stronger evidence.

## Change Rules

1. Do not infer obsolescence from a legacy-looking name.
2. Do not infer safety from zero string-search matches; dynamic and external callers need explicit review.
3. A `shim-only` or `deprecated` interface must name a real replacement.
4. A cleanup candidate needs definition evidence, consumer-search evidence, focused tests, and a rollback or compatibility story.
5. Unknown interfaces cannot move directly to deletion. First classify them as current, deprecated, shim-only, test-only, or historical using stronger evidence.
6. Preserve private traces and historical plans. Redact secrets rather than deleting reproducibility evidence.
7. Update this document, regenerate the private registry, and run the focused audit test after interface changes.

## Stability Protocol Ownership

The following ownership boundaries are now explicit:

| Interface family | Canonical owner | Current bridge or projection |
| --- | --- | --- |
| Versioned protocol schemas and generated types | `astrabridge_sidecar.protocol` | Existing inline Python/TypeScript contracts until schema migration completes |
| Agent Envelope, delivery events, and artifact references | `astrabridge_sidecar.protocol` | Task-graph input/output envelopes and UI summaries |
| MCP configuration and preset policy | `mcp_config_service.py` | Existing MCP server adapters |
| MCP protocol core/broker | `astrabridge_sidecar.protocol` migration target | Current named MCP servers and direct capability paths, explicitly temporary |
| Durable run state and scheduler events | `astrabridge_sidecar.protocol` migration target | Task JSON, manifests, and UI projections |
| Graph authoring/runtime NodeType registry | `astrabridge_sidecar.protocol` migration target | Existing role palette and graph components |

The stability plan must update this table when a migration step changes an owner or bridge. A projection may not introduce a new business schema merely because it is easier for a UI or provider adapter to consume.

## Current Limits

- Request and response schemas are still often inline Python/TypeScript compatibility contracts rather than generated JSON Schema. The stability plan's schema/codegen step is the migration path; until it completes, inline definitions are not allowed to become new canonical owners.
- Consumer search covers this repository. It cannot see uncommitted external clients, manually entered URLs, or a third-party integration outside the workspace.
- HTTP method inference comes from the current Python handler definitions; Desktop evidence is path-based because TypeScript helper wrappers centralize method selection.
- This step did not call providers, mutate Vault state, remove routes, or rewrite compatibility behavior.
