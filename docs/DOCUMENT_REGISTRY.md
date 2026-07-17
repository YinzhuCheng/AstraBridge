# AstraBridge Document Registry

Last verified: 2026-07-17

## Purpose

This is the canonical human-readable index for AstraBridge documentation and execution plans. The complete machine-readable inventory is [DOCUMENT_REGISTRY.json](/D:/AstraBridge/docs/DOCUMENT_REGISTRY.json).

The registry classifies the current repository state without rewriting historical execution logs. A plan may still contain an old `Current status: In progress` line while this registry marks the file `superseded`; in that case, the registry decides whether a future agent may resume the file.

## Precedence

Use this order when sources appear to disagree:

1. `AGENTS.md` for repository safety and execution-loop rules.
2. The execution plan explicitly activated by the current user request.
3. This registry for document status, replacement, and archive behavior.
4. Active policy and project-memory documents.
5. Reference contracts, runbooks, evidence summaries, and surface maps.
6. Completed, superseded, and archived records as historical evidence only.

Do not use file modification time, filename wording, or an old progress paragraph as a substitute for this classification.

## Status Taxonomy

| Status | Meaning | Agent behavior |
| --- | --- | --- |
| `active` | Current policy, project memory, or explicitly activatable execution queue. | Use when its activation condition matches the request. |
| `complete` | Finished execution or summary record. | Preserve; do not resume. |
| `superseded` | Earlier queue replaced by a later plan, runbook, or completed record. | Preserve; follow `replacement`. |
| `archived` | Historical compatibility or obsolete guidance stored for audit. | Never treat as current architecture. |
| `reference` | Stable contract, runbook, evidence summary, or surface map. | Read for context; do not execute as a queue. |

## Current Execution Queues

| Path | Activation | Owner | Scope |
| --- | --- | --- | --- |
| [ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md](/D:/AstraBridge/PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md) | Current default queue | `stability-protocol` | Provider isolation, MCP capability boundaries, agent envelopes, durable task-graph runtime, and cross-provider reliability gates. |
| [CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md](/D:/AstraBridge/PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md) | Only when the user explicitly requests capability-runtime implementation or advancement | `capability-runtime` | Remaining capability-runtime implementation beginning at its recorded Step 2. |

These activation conditions do not conflict: the capability-runtime queue is dormant unless the user explicitly invokes that scope. The prior UI/live-dogfood queue remains preserved as historical evidence and is superseded by the stability plan for remaining reliability work. All other execution plans are `complete` or `superseded` in the registry.

## Active Policy And Memory

| Path | Owner | Scope |
| --- | --- | --- |
| [AGENTS.md](/D:/AstraBridge/AGENTS.md) | `repository-governance` | Safety and execution rules. |
| [README.md](/D:/AstraBridge/README.md) | `repository-governance` | Public entry and quickstart. |
| [PROJECT_SUMMARY.md](/D:/AstraBridge/docs/PROJECT_SUMMARY.md) | `project-memory` | Fast current state. |
| [PROJECT_LOG.md](/D:/AstraBridge/docs/PROJECT_LOG.md) | `project-memory` | Chronological memory. |
| [REPO_GOVERNANCE.md](/D:/AstraBridge/docs/REPO_GOVERNANCE.md) | `repository-governance` | Hygiene and status policy. |
| [OWNERSHIP_BOUNDARIES.md](/D:/AstraBridge/docs/OWNERSHIP_BOUNDARIES.md) | `architecture` | Subsystem and state ownership. |
| [CODE_OWNERSHIP_AND_CONTRACTS.md](/D:/AstraBridge/docs/CODE_OWNERSHIP_AND_CONTRACTS.md) | `architecture` | Canonical code ownership, graph bridges, provider transport, and contract-drift gates. |
| [VERIFICATION_MATRIX.md](/D:/AstraBridge/docs/VERIFICATION_MATRIX.md) | `release` | Validation gates. |
| [RELEASE_CHECKLIST.md](/D:/AstraBridge/docs/RELEASE_CHECKLIST.md) | `release` | Release checklist. |
| [SECURITY_AND_ISOLATION.md](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md) | `security` | Secret and isolation boundaries. |
| [ASSET_SOURCES.md](/D:/AstraBridge/docs/ASSET_SOURCES.md) | `asset-provenance` | Asset provenance. |

## Completed Execution Families

The following are finished records and must not be reopened as active queues:

- Repository normalization: `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`
- App hardening: `PLAN/ASTRABRIDGE_APP_HARDENING_EXECUTION_PLAN.md`
- Brand system round one: `PLAN/ASTRABRIDGE_BRAND_SYSTEM_EXECUTION_PLAN.md`
- First agent benchmark dogfood: `PLAN/AGENT_BENCH_DOGFOOD_EXECUTION_PLAN.md`
- Capability entry/Web validation and capability UI management
- Automation implementation
- Codex kernel/plugin/skill integration
- Agent orchestration productization, foundational task graph, canvas dogfood, GUI/runtime handoff, and dynamic workflow productization
- Multimodal adapter/update implementation
- Provider/model compatibility foundation, residual-risk repair, capability/reasoning validation, and exhaustive smoke
- Agentic update pipeline
- Capability UI, multimodal drift, and plugin/skill gap snapshots whose findings were consumed by later surface maps, runbooks, or completed implementation

Use the exact file list and replacement paths in the JSON registry.

## Superseded Queues

Nineteen older or duplicate queues are preserved but must not be resumed. The major replacement families are:

| Earlier family | Replacement |
| --- | --- |
| ComfyUI, visual-orchestrator, benchmark, product-slice, product-v1, remaining-work, communication-GUI, and click-driven graph queues | `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`, then the current standardization/UI/live-dogfood plan for new work |
| Early five-capability dogfood draft | `PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md` |
| Unstarted multimodal maintenance-automation queue | `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md` plus `PLAN/MULTIMODAL_MAINTENANCE_RUNBOOK.md` |
| Provider remaining-risk, follow-up, coverage, and reasoning handoff queues | Completed residual-risk, validation, and exhaustive-smoke plans; future work starts from `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` |

The registry downgrade is documentary only. It does not delete or alter any historical plan progress.

## Reference Families

Reference documents include:

- architecture, ownership, product semantics, release, security, and demo runbooks;
- runtime rollout, migration, rollback-readback, and maintenance runbooks;
- Agent Graph contracts, maintenance runbooks, canvas UX targets, internal contracts, and surface maps;
- capability runtime, automation, kernel, plugin/skill, and provider compatibility contracts or surface maps;
- interface governance for HTTP, SSE, payload, provider metadata, CLI/launcher, MCP, and compatibility shims;
- multimodal contracts, official-source pack, exposure gates, maintenance runbook, and rollout/rollback policy;
- dogfood task pools and evidence summaries;
- brand tokens, icons, edge primitives, wallpaper, and provenance guidance.

They inform implementation but do not own the execution queue.

## Current Guidance Hygiene

The governance check reads the JSON registry before evaluating documentation:

- every `AGENTS.md`, `README.md`, `docs/**/*.md`, `docs/DOCUMENT_REGISTRY.json`, and `PLAN/*` file must have exactly one registry entry;
- every registered path and replacement target must exist;
- every `superseded` entry must name a replacement;
- active plans must be either the current plan or an explicitly conditional plan;
- local Markdown links in `active` and `reference` files must resolve;
- mojibake or unguarded retired product paths in `active` and `reference` guidance fail the gate;
- removed runtime compatibility symbols may appear only in their audit inventory, tests, or archived history; current code references fail the gate;
- corruption inside preserved completed/superseded records is reported as historical information rather than silently converted into current guidance.

The 2026-07-10 Step 3 audit found no mojibake in registered active/reference guidance. All remaining old project-format, official-login, and plaintext-key-path mentions in that set are explicit prohibitions, negative checks, or historical evidence. Fixed ports `4181` and `8826` remain the documented local preview and sidecar examples; they are launch examples, not persisted product state.

## Archive Rules

- `keep_in_place`: current policy/reference file remains at its path.
- `preserve_execution_record`: completed record remains unchanged except for narrowly justified corruption repair or explicit annotations.
- `preserve_history_do_not_resume`: superseded record remains available, but future agents follow its replacement.
- `preserve_under_docs_archive`: archived material stays under `docs/archive/` and must not become a current entry point.

Prefer status marking plus a visible replacement banner when moving a widely linked completed record would create needless redirects. Physical moves into `docs/archive/` are reserved for obsolete guidance with no maintained contract or evidence role. This policy preserves stable evidence links without allowing an old gap report to act as an execution queue.

## Registry Maintenance

When adding or changing a guiding document or execution plan:

1. Update `DOCUMENT_REGISTRY.json` in the same change.
2. Give every entry `path`, `status`, `owner`, `scope`, `last_verified`, `replacement`, and `archive_policy`.
3. Give every `superseded` entry a real replacement path.
4. Give every `archived` entry a replacement or explicit historical purpose.
5. Keep current execution activation conditions mutually exclusive.
6. Preserve completed and private evidence by default.
7. Run the repository governance and link checks before handoff.

## Current Counts

As verified on 2026-07-17, the registry contains 106 entries:

| Status | Count |
| --- | ---: |
| `active` | 14 |
| `complete` | 25 |
| `reference` | 46 |
| `superseded` | 20 |
| `archived` | 1 |
