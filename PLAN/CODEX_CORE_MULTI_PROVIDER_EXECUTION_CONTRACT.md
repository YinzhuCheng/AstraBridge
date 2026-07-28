# Codex-Core Multi-Provider Execution Contract

**Schema version:** `astrabridge-codex-core-multi-provider-execution-v1`
**Status:** normative design contract; implementation is tracked by
`PLAN/ASTRABRIDGE_MULTI_PROVIDER_ADAPTATION_UPGRADE_HANDOFF_PLAN.md`

## 1. Purpose And Product Boundary

AstraBridge is a coding-agent product whose core runtime is Codex. External
LLM providers extend the product through AstraBridge-owned contracts; they do
not replace Codex, impersonate an arbitrary Codex thread, or create a parallel
agent-message ABI.

Hermes-style multi-provider mechanisms are design reference for provider
profiles, wire transforms, reasoning safety, and fallback semantics. Hermes is
not a runtime dependency or a source tree to copy wholesale.

This contract governs three execution categories:

1. **Codex/App Server driver** — the first-class coding runtime and owner of
   Codex-native thread semantics.
2. **AstraBridge native-provider driver** — the internal
   `NativeCodingTurnLoop` using a provider transport only after route
   verification.
3. **Preview/review route** — an intentionally reduced-authority path that may
   analyze, inspect, or propose but may not silently acquire side-effecting
   authority.

The contract applies to the current Qwen, DeepSeek, Kimi, and GLM
provider-family transports, and to OpenAI/Codex and Yunwu-compatible paths
where a provider/model/endpoint route is selected.

## 2. Normative Terms

| Term | Meaning | Is not |
| --- | --- | --- |
| Provider | Long-lived vendor family and stable defaults. | Proof that every model or endpoint behaves the same. |
| Model contract | Model-specific facts: modalities, reasoning mapping, tools, limits, catalog state. | Provider-wide capability flags. |
| Endpoint contract | Region/account/base-URL/protocol/adapter-version binding. | A nominal public documentation page. |
| Execution route | Provider + model + endpoint + adapter + driver + authority + evidence. | A model id or `runtime_backend` string alone. |
| Codex/App Server driver | The Codex-owned `app_server` runtime boundary. | Proof that an external provider has native Codex semantics. |
| Native-provider driver | AstraBridge's feature-gated native coding turn loop. | An unverified generic fallback. |
| Neutral transcript | Safe task continuity: visible intent/results, tool summaries, checkpoints, lineage. | Raw provider history, opaque reasoning, or credentials. |
| Evidence state | Strongest preserved validation level for one execution route. | Documentation or a text-only completion. |

## 3. Non-Negotiable Invariants

### 3.1 Codex Is Core

- Codex/App Server is not modeled as just another external provider adapter.
- The shared AstraBridge task, coding-event, checkpoint, permission, and
  durable-delivery contracts remain the integration boundary around both
  drivers.
- App Server compatibility is not by itself evidence that an external model has
  native Codex thread, tool, or fork semantics.

### 3.2 Provider Semantics Stay Below The Common Runtime Boundary

- Provider transports own request projection, tool-schema projection, reasoning
  controls, response normalization, and provider error classification.
- Upper coding-runtime layers consume normalized responses, coding events,
  task envelopes, checkpoints, and normalized tool results.
- Provider-private payloads must not become durable common-runtime state.

### 3.3 Authority Is Evidence-Qualified

- A provider profile, model name, documentation page, metadata refresh, or
  text-only smoke never enables autonomous write or command tools by itself.
- Effective authority is the lower of model authority assessment and
  route-specific evidence authority.
- Unknown, expired, conflicting, or unsupported routes downgrade authority or
  fail closed.

### 3.4 Cross-Provider Continuity Is Neutral, Not Raw Replay

- Cross-provider handoff starts or reuses an isolated target lane and carries a
  neutral context pack with explicit lineage.
- A provider thread must not be raw-forked into another provider runtime.
- Opaque reasoning, response ids, signatures, encrypted blobs, provider
  cookies, credentials, and private vendor fields never enter neutral context.

### 3.5 Side Effects Are Causal And Recoverable

- Repairable output defects are not authorization to execute a side-effecting
  tool.
- Side-effecting tools require a validated action identity, authority decision,
  workspace/checkpoint linkage, and durable outcome receipt before retry or
  handoff can be safe.
- A retry may not replay an action with an unknown terminal receipt without an
  explicit recovery policy and user-visible explanation.

## 4. Authoritative Ownership Map

| Decision | Current owner/evidence surface | Required rule |
| --- | --- | --- |
| Provider defaults, auth reference, base URL, protocol family | `providers/profile.py` | `ProviderProfile` supplies defaults only; it never proves autonomous-agent safety. |
| Provider-specific wire adaptation | `providers/transports/` | Adapter owns message, tool, request, stream, response, and error projection without leaking raw wire state upward. |
| Normal response | `providers/ir.py` | Upper layers receive `NormalizedResponse` and bounded/redacted diagnostics, not arbitrary raw responses. |
| Model facts and capability exposure | `model_catalog/`, `router_config_service.py` | Claims must be model-specific where needed and cannot outrun route evidence. |
| Driver selection | `runtime_service.py` | Current `execution_backend` is a selector; future route admission makes it evidence-qualified. |
| Native-provider coding loop | `coding_kernel/turn_loop.py` | It runs only when feature-gated, route-admitted, and within authority limits. |
| Authority assessment | `providers/tooling/model_authority.py` | A/B/C/D tier is an upper bound; route evidence may only reduce it. |
| Tool, edit, checkpoint, verification | `coding_kernel/`, `project_tools_service.py` | Common tool policy is independent of provider wire format. |
| History and reasoning projection | `providers/history_projector.py` | Cross-provider projection is neutral/redacted; opaque replay requires compatible provenance. |
| Failure and transition planning | `providers/runtime_transition.py`, `providers/failures.py` | Eventual behavior is a causal state machine, not only advice to the UI. |
| Common event ABI | `coding_kernel/events.py` | No provider-specific event ABI bypasses this shared vocabulary. |
| Update/promotion/rollback evidence | `agentic_updates/`, update runbook | Discovery may change conservative facts; route promotion needs route-specific evidence and rollback. |

## 5. Current Runtime Facts

The following are present implementation facts, not claims of final route
completeness:

1. `ProviderProfile` already contains provider-level protocol, reasoning,
   tool, context, edit, fallback, safety, and `runtime_backend` defaults.
2. Qwen, DeepSeek, Kimi, and GLM have provider-family transport classes;
   fallback transport selection is currently Chat or Responses shaped.
3. `NormalizedResponse` and `ReasoningState` form the common response
   representation.
4. `HistoryProjector` strips known private fields, handles tool-pair repair,
   and blocks unsafe cross-provider reasoning replay.
5. A cross-provider provider-thread switch deliberately starts a fresh target
   thread and carries AstraBridge task/project/asset context instead of trying
   to fork a foreign runtime thread.
6. `NativeCodingTurnLoop` applies model authority to read, preview, edit,
   command, test, and checkpoint tools, but native execution is feature-gated.
7. Failure taxonomy, transition targets, context reports, compatibility smoke,
   dry-run matrix, and proposal-first update/rollback machinery already exist.

Therefore, `runtime_backend` is a provisional driver-selection default, not
complete proof of a model/endpoint route. The adaptation upgrade plan owns the
new evidence-qualified `ExecutionRoute` contract.

## 6. Execution-Route Admission Contract

Every provider turn must resolve an execution route before receiving tool
authority:

```text
ExecutionRoute = (
  provider_id,
  model_id,
  endpoint_identity,
  protocol_adapter_id_and_version,
  driver,
  authority_ceiling,
  context_policy,
  reasoning_policy,
  tool_policy,
  fallback_policy,
  evidence_state,
  evidence_refs,
  verified_at,
  expires_at
)
```

`endpoint_identity` distinguishes at least provider, normalized base URL, and
region/tenant class when semantics differ. It must never contain credentials.

### 6.1 Evidence Lifecycle

```text
documented
  -> adapter_dry_run_passed
  -> provider_smoke_passed
  -> tool_contract_passed
  -> coding_route_verified
  -> default_route_eligible
```

- `documented` may expose conservative facts but is not agent-ready.
- `adapter_dry_run_passed` proves fixture compatibility, not paid-provider
  behavior.
- `provider_smoke_passed` proves only the bounded capability actually
  exercised.
- `tool_contract_passed` requires structured calls, result pairing,
  authority, and recovery evidence.
- `coding_route_verified` is the minimum autonomous coding-route state,
  subject to task permission and authority.
- `default_route_eligible` additionally needs current, non-expired evidence,
  truthful status UI, and safe fallback/rollback.

Endpoint drift, adapter-signature change, model version change, contradictory
provider behavior, or failed regression must de-promote the affected route
until it is revalidated.

### 6.2 Driver Admission

| Candidate driver | Admission rule | Safe result on failure |
| --- | --- | --- |
| Codex/App Server | Runtime/profile is compatible and required route features are verified. | Do not infer native Codex semantics; offer a lower-authority route or block. |
| Native-provider | Native kernel is enabled; transport, context, tool, and authority conditions are route-admitted. | Preview/review-only or blocked; never silently enable native tools. |
| Preview/review | Text/review is supported but autonomous semantics are not proven. | Retain only explicit reduced authority. |
| No admissible route | No route meets requested modality, context, tool, or safety needs. | Fail closed before a turn; give actionable downgrade, compact, retry, or handoff guidance. |

## 7. Authority And Tool Rules

| Effective state | Permitted behavior | Prohibited behavior |
| --- | --- | --- |
| A + `coding_route_verified` | Read, bounded edit/apply, command/test, checkpoint, and verified tools under existing permission policy. | Bypassing checkpoint, receipt, or permission gates. |
| B or partial route | Read, inspect, plan, and preview edits. | Applying edits/commands/new side effects without explicit promotion or approval. |
| C or unverified tool surface | Explain/review only. | Presenting tool calls as executable or auto-applying output. |
| D, blocked, expired, or conflicting route | No agent execution. | Silent fallback to higher authority or reuse of private state. |

Tool-call repair may normalize transport defects for diagnostics or safe history
projection. It must not turn malformed arguments, generated ids, or missing
tool results into authority to perform a side effect. The adaptation plan's
Tool Action Envelope step owns the durable receipt implementation.

## 8. History, Reasoning, And Handoff Rules

1. Use `HistoryProjector` and a neutral task/project/asset pack for every
   cross-provider handoff.
2. Strip provider-private fields before persistence or target projection,
   including opaque/signed/encrypted reasoning and provider response ids.
3. Preserve only visible summaries, structured tool intent/results, checkpoint
   references, task state, and lineage that pass common redaction policy.
4. Same-provider opaque replay requires issuer, endpoint, model, artifact type,
   replayability, and target-compatibility proof. Otherwise reduce it to a
   visible summary.
5. Cross-provider opaque reasoning replay is disabled by default; no current
   route may assume an exception.
6. Handoff records name source/target route identity, projection mode,
   dropped/repaired counts, warnings, and task/thread lineage without leaking
   secrets or opaque state.

## 9. Failure, Fallback, And Recovery Rules

Fallback is a state transition, not a model-string substitution:

```text
classify failure
  -> freeze turn state
  -> inspect action receipts and checkpoints
  -> decide retry/compact/downgrade/handoff/block
  -> project neutral context and record semantic loss
  -> admit target route
  -> start/reuse isolated lane
  -> record terminal outcome and user-visible explanation
```

- Context failure may compact/narrow only with a preserved reason and
  dropped-section record.
- Rate-limit and transport retries are bounded and must consider action
  receipts.
- Unsupported reasoning, modality, tool, or protocol features downgrade that
  feature or block the route; they never pretend success.
- A provider switch may not re-execute an uncertain side-effecting tool call.

## 10. Release-Blocking Violations And Degradable Warnings

| Classification | Condition | Required response |
| --- | --- | --- |
| Release-blocking | Cross-provider private reasoning, credentials, or provider session state enters shared/durable context. | Stop, redact/quarantine evidence, fix boundary, add regression proof. |
| Release-blocking | Autonomous write/command authority lacks route-specific structured-tool and recovery proof. | Block promotion; demote to preview/review or disabled. |
| Release-blocking | Retry/fallback can duplicate an unacknowledged edit or command. | Block retry/handoff until receipt/recovery semantics exist. |
| Release-blocking | Provider wire/event shape bypasses shared task, tool, checkpoint, or coding-event policy. | Terminate at adapter boundary and add conformance coverage. |
| Release-blocking | UI/API says verified/default-ready while evidence is unknown, expired, conflicting, or partial. | Correct admission/status before release. |
| Degradable warning | Text/review works but tools, native driver, image input, or parallel calls are unverified. | Expose explicit reduced authority. |
| Degradable warning | Usable context is below advertised or compaction quality is unverified. | Warn, compact/narrow, or restrict long turns. |
| Degradable warning | Native driver feature flag is disabled. | Use verified alternate route or state unavailable. |
| Degradable warning | Model is documented but not live-smoked. | Expose factual metadata only; keep non-agent-ready. |

## 11. Required Evidence And Test Surface

| Evidence class | Current surface | Minimum future use |
| --- | --- | --- |
| Transport conformance | `tests/test_provider_transport_conformance.py` | Route fixture corpus for request, response, stream, cancel, tool, and error behavior. |
| Handoff/redaction | `tests/test_provider_handoff_compatibility.py` | Prove lineage, fresh-thread use, private-state removal, neutral context. |
| Tool/authority | `tests/test_tool_call_compatibility.py` | Prove authority ceilings, malformed output handling, receipts, no duplicate side effects. |
| Failure/transition | `tests/test_runtime_failure_taxonomy.py` and runtime retry tests | Prove bounded recovery and explicit semantic downgrade. |
| Context/capability truth | Context gate, catalog, dry-run matrix, compatibility tests | Prove endpoint/model admission, not provider-wide optimism. |
| Update evidence | `PRIVATE/agentic-update-pipeline/runs/` | Prove discovery, promotion, de-promotion, rollback without secrets. |
| Provider smoke | `PRIVATE/provider-compatibility/runs/` | Run only with explicit authorization; prove bounded route claims. |

## 12. Compatibility, Migration, And Change Control

- Existing profiles and task settings resolve through conservative defaults
  until evidence-qualified routes are implemented.
- Missing new route metadata resolves to non-promotion, never an authority
  upgrade.
- Existing `runtime_backend` values remain backward compatible while later
  admission layers qualify them with evidence.
- A model/endpoint that cannot migrate losslessly retains factual catalog
  metadata but moves to preview/review or blocked with a visible reason.
- No migration rewrites provider private state, user secrets, or legacy task
  history into common state without the redaction rules above.

Changing this contract requires a compatible amendment or version increment,
owner/test impact analysis, secret-free validation evidence, and a progress-log
entry in the adaptation upgrade handoff plan. Hermes source inspection is only
needed for a later bounded implementation question that current AstraBridge
evidence and this contract cannot resolve.
