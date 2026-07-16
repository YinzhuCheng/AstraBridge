---
name: provider-capability-repair
description: Diagnose and repair AstraBridge provider/model/capability adaptation regressions, especially route mismatches, modality request-shape bugs, and provider-specific normalization drift.
---

# Provider Capability Repair

Use this skill when AstraBridge starts failing on a specific provider/model/capability lane, or when live smoke evidence disagrees with the actual request/response artifacts.

This skill is for repair work, not broad metadata refresh. Prefer it when the issue looks like one of these:

- a smoke case says the route hit the wrong provider/model, but the preserved `request.json` shows the expected target
- a provider/model has the right declared capability, but the adapter request shape or normalization is wrong
- a new provider/model variant reuses an existing adapter family, but AstraBridge is collapsing it onto a default/base model
- the app’s capability/runtime evidence and the preserved `PRIVATE/provider-compatibility/**` artifacts disagree

## Preserve First

1. Preserve `PRIVATE/provider-compatibility/**` by default.
2. Do not delete failing runs, request/response artifacts, validation summaries, or scratch reports.
3. Never persist secrets, raw auth headers, cookies, or desktop key contents.
4. Do not read desktop plaintext key files unless the user explicitly authorizes that exact path for the current run.

## Start Every Repair

1. Identify the failing case artifact, usually under:
   - `PRIVATE/provider-compatibility/runs/<run_id>/batches/<batch_id>/cases/*.json`
2. Run the diagnostic helper first:

```powershell
.\.venv\Scripts\python.exe apps/astrabridge-sidecar/skills/provider-capability-repair/scripts/diagnose_capability_case.py --case <case.json>
```

3. Use the diagnosis to choose the smallest repair surface before editing code.

## Diagnosis Classes

### `smoke_route_reporting_mismatch`

Meaning:
- the preserved request artifact targeted the expected provider/model
- but smoke reported a different route/provider/model

Primary entrypoints:
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/provider_compatibility_smoke.py`
- `PRIVATE/provider-compatibility/step7_exhaustive_batch_b_runner.py`
- `PRIVATE/provider-compatibility/step8_exhaustive_batch_c_runner.py`
- `PRIVATE/provider-compatibility/step9_exhaustive_batch_d_runner.py`
- `PRIVATE/provider-compatibility/step10_exhaustive_batch_e_runner.py`

Typical fix:
- make smoke/reporting honor explicit `provider_id` and `model`
- prefer the runtime-resolved route or the explicit request target over unrelated auto-route state

### `request_payload_mismatch`

Meaning:
- the request artifact itself targeted the wrong model or wrong shape

Primary entrypoints:
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/vision_analyze_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_transcribe_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/image_generate_adapter.py`

Typical fix:
- patch the adapter `build_request()` path or runtime normalization
- add a focused regression test for the exact provider/model variant

### `provider_response_model_alias_or_remap`

Meaning:
- the request targeted the expected model
- but the upstream response echoed a base model or alias

Primary entrypoints:
- adapter `normalize_result()` implementations
- smoke/report classifiers that compare requested vs observed model identity
- official provider docs for alias/highspeed/instruct model behavior

Typical fix:
- distinguish true route mistakes from upstream alias echo
- keep the requested target visible in AstraBridge evidence even if the provider returns an alias

### `provider_or_adapter_behavior`

Meaning:
- route and request look correct, but the lane still fails semantically or by artifact validation

Primary entrypoints:
- capability adapter modules
- capability registry/specs
- provider-specific transport/profile code when the issue is not adapter-local

## Relevant Code Surfaces

- Capability routing/runtime:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_routes.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`
- Capability smoke/reporting:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_compatibility_smoke.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/exhaustive_smoke_runner.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/exhaustive_smoke_contract.py`
- Adapter implementations:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/vision_analyze_adapter.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_transcribe_adapter.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/image_generate_adapter.py`

## Validation Commands

Run focused validation from `apps/astrabridge-sidecar`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_capability_smoke tests.test_provider_compatibility_smoke
.\.venv\Scripts\python.exe -m unittest tests.test_vision_analyze_adapter tests.test_speech_transcribe_adapter tests.test_speech_synthesize_adapter
.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\capabilities\smoke.py astrabridge_sidecar\provider_compatibility_smoke.py
```

If the repair changes a capability-specific adapter, add that adapter’s test file to the validation set.

Only run provider-backed live rechecks when the user explicitly authorizes provider calls or a managed-key session is already in scope for the task.

## Live Recheck Entry Points

Prefer the preserved focused runners over ad hoc scripts:

- `PRIVATE/provider-compatibility/step7_exhaustive_batch_b_runner.py`
- `PRIVATE/provider-compatibility/step8_exhaustive_batch_c_runner.py`
- `PRIVATE/provider-compatibility/step9_exhaustive_batch_d_runner.py`
- `PRIVATE/provider-compatibility/step10_exhaustive_batch_e_runner.py`

Use the runner that matches the failing capability lane. Keep outputs in `PRIVATE/provider-compatibility/runs/<run_id>/`.

## Handoff

Record:

- the failing case path
- the diagnosis class from `diagnose_capability_case.py`
- files changed
- focused validation commands run
- whether live recheck was skipped or executed
- the next unresolved provider/model/capability lane
