# Multimodal Capability Surface Drift Report

Last updated: 2026-07-06

**Document status:** Completed historical snapshot. Do not treat its gap list as current maintenance guidance without revalidation. Start from [MULTIMODAL_MAINTENANCE_RUNBOOK.md](/D:/AstraBridge/PLAN/MULTIMODAL_MAINTENANCE_RUNBOOK.md).

## Purpose

This report reconciles the current AstraBridge multimodal surfaces against:

- `PLAN/MULTIMODAL_CAPABILITY_SCOPE_AND_INVARIANTS.md`
- `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`

It identifies where current catalog, runtime, MCP, and capability-management surfaces still drift from the intended matrix-driven design.

The report is limited to:

- `image.generate`
- `vision.analyze`
- `speech.transcribe`
- `speech.synthesize`

## Surface Inventory Used For Reconciliation

The current reconciliation checked these code and plan surfaces:

- `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_routes.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate_baseline.json`

## Summary

The core runtime already has a usable multimodal skeleton:

- capability ids are stable
- adapter contracts exist for the currently wired lanes
- route snapshots and capability-management snapshots exist
- dry-run and provider-smoke infrastructure exists

But the current system still drifts from the matrix contract in three material ways:

1. route-authoritative and UI-only facts are still mixed together in several surfaces
2. wired runtime behavior is still hardcoded by provider-specific dispatch rather than adapter-family indirection
3. documented catalog presence still exceeds verified or even wired support for some multimodal rows

## Drift Classification

The report uses these severity levels:

- `high`: likely to cause false exposure, misleading routing, or adapter-maintenance churn
- `medium`: causes surface inconsistency, stale operator understanding, or weak rollout behavior
- `low`: documentation or naming drift that does not yet directly misroute calls

## Drift Items

### 1. Surface Map Still Declares A Stale TTS Adapter Id

- Severity: `medium`
- Drift type: `contract drift`
- Ownership surfaces:
  - `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`

Evidence:

- The current capability surface map still lists `speech.synthesize` with adapter `qwen.tts.omni.v1`: [CAPABILITY_RUNTIME_SURFACE_MAP.md](/D:/AstraBridge/PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md:16)
- The current adapter contract is `qwen.tts.api.v1`: [specs.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py:517)

Impact:

- Maintainer-facing surface documentation no longer matches the active adapter contract.
- Future agents could incorrectly assume the runtime still uses an omni-family adapter shape.

Required follow-up:

- Reconcile the surface map with current adapter ids before wider matrix-generated surfaces are introduced.

### 2. Runtime Dispatch Is Still Provider-Class Hardwired Instead Of Adapter-Family Driven

- Severity: `high`
- Drift type: `surface drift`
- Ownership surfaces:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`
  - later adapter-family implementation work

Evidence:

- Runtime constructs concrete provider adapters directly:
  - `QwenSpeechSynthesizeAdapter`: [runtime.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py:40)
  - `QwenVisionAnalyzeAdapter`: [runtime.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py:41)
  - `KimiVisionAnalyzeAdapter`: [runtime.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py:42)
- Runtime dispatch branches on capability id and then on provider choice rather than an adapter-family registry:
  - `image.generate`: [runtime.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py:101)
  - `speech.transcribe`: [runtime.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py:108)
  - `speech.synthesize`: [runtime.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py:110)
  - `vision.analyze`: [runtime.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py:112)

Impact:

- Adding a new adapter family such as `dashscope_image` or a second TTS family still requires hand edits in runtime dispatch.
- The matrix field `adapter_family` cannot yet be the real source of runtime dispatch.

Required follow-up:

- Step 5 and later implementation must replace hardwired adapter member selection with family-based dispatch or an adapter registry.

### 3. Capability Management Snapshot Does Not Yet Expose Matrix-Authoritative States

- Severity: `high`
- Drift type: `surface drift`
- Ownership surfaces:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`

Evidence:

- Capability-management snapshot includes `availability`, `contract`, `adapters`, `smoke`, and `artifacts`: [router_config_service.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py:235)
- It exposes `candidate_count` and `resolution_status`: [router_config_service.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py:263)
- It leaves `smoke.last_result` and `artifacts.recent_refs` as placeholder `None` / empty values: [router_config_service.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py:272), [router_config_service.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py:277)
- The snapshot has no first-class fields for:
  - `documented_state`
  - `wired_state`
  - `verified_state`
  - `exposure_state`
  - `adapter_family`
  - `visibility_policy`

Impact:

- The main desktop capability-management surface cannot yet reflect the matrix contract directly.
- Consumers must infer rollout state from lower-level route and smoke fragments.

Required follow-up:

- Step 6 should introduce explicit exposure-state fields into capability-management responses rather than forcing UI inference.

### 4. Catalog And Runtime Still Mix Route Facts With UI Warnings

- Severity: `high`
- Drift type: `contract drift`
- Ownership surfaces:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`
  - future matrix projection logic

Evidence:

- `ui_warnings` is treated as a catalog-managed modality sync field: [router_config_service.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py:166), [router_config_service.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py:170)
- Router config refresh merges UI warnings into persisted model state: [router_config_service.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py:733)
- Exported model catalog payload also merges `ui_warnings` with runtime authority assessment: [catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py:711), [catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py:797)

Impact:

- UI-facing summary text is stored alongside metadata that later surfaces may treat as semi-authoritative.
- This conflicts with the matrix requirement that `ui_warnings` remain informational only.

Required follow-up:

- Later matrix projection should normalize authoritative route and exposure facts first, then derive UI warnings from them rather than syncing warnings as quasi-source data.

### 5. Generated Catalog Advertises More Multimodal Models Than Current Wired Families Can Explain

- Severity: `high`
- Drift type: `evidence drift`
- Ownership surfaces:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate_baseline.json`

Evidence:

- Generated catalog includes multiple Qwen multimodal rows:
  - `qwen3.7-plus`: [generated_catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py:188)
  - `qwen3.7-max-2026-06-08`: [generated_catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py:198)
  - `qwen3.6-flash`: [generated_catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py:205)
  - `qwen3-vl-plus`: [generated_catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py:215)
  - `qwen3-vl-flash`: [generated_catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py:224)
  - `qwen3-asr-flash`: [generated_catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py:233)
  - `qwen3-tts-flash`: [generated_catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py:244)
  - `qwen3-tts-instruct-flash`: [generated_catalog.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py:255)
- Current adapter contracts only wire a subset of concrete capability families:
  - Qwen vision: [specs.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py:474)
  - Qwen ASR: [specs.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py:496)
  - Qwen TTS: [specs.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py:517)
- Existing verification baseline already records conflicting dry-run cases for some catalog-present multimodal rows:
  - `qwen3-tts-flash` on `speech.transcribe`: [provider_capability_verification_gate_baseline.json](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate_baseline.json:23)
  - `qwen3-tts-instruct-flash` on `speech.transcribe`: [provider_capability_verification_gate_baseline.json](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate_baseline.json:28)
  - `qwen3.7-max-2026-06-08` on `vision.analyze`: [provider_capability_verification_gate_baseline.json](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate_baseline.json:33)

Impact:

- Catalog-level multimodal discovery is ahead of model-capability-lane truth.
- Some models still look multimodal in metadata while route eligibility and dry-run evidence disagree.

Required follow-up:

- Step 3 follow-on and Step 10 should project these rows through the multimodal matrix so each model/capability lane gets its own authoritative state instead of one broad model-level impression.

### 6. Provider Capability Dry-Run Matrix Still Uses The Broader Compatibility Shape Instead Of The Multimodal Matrix Contract

- Severity: `medium`
- Drift type: `surface drift`
- Ownership surfaces:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py`

Evidence:

- Dry-run matrix still builds against the broader provider/model compatibility matrix utilities: [provider_capability_dry_run_matrix.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py:15)
- It aggregates only `overall_status` from the broader matrix shape: [provider_capability_dry_run_matrix.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py:118), [provider_capability_dry_run_matrix.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py:465)
- It currently drags `ui_warnings` into lane notes during matrix construction: [provider_capability_dry_run_matrix.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py:468)

Impact:

- Existing dry-run evidence is useful, but it is not yet emitted in the narrower multimodal matrix shape.
- Verification reporting still mixes UI copy into what should later become route-authoritative or verification-only sections.

Required follow-up:

- Step 11 should either project current dry-run output into the new multimodal matrix contract or replace the current report path with a dedicated multimodal generator.

### 7. MCP Capability Tools Expose Capability-Specific Inputs But Not Matrix-Derived Exposure State

- Severity: `medium`
- Drift type: `surface drift`
- Ownership surfaces:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py`

Evidence:

- The MCP server exposes separate capability tools plus `astrabridge_capability_routes`: [astrabridge_capabilities_mcp_server.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py:69), [astrabridge_capabilities_mcp_server.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py:80), [astrabridge_capabilities_mcp_server.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py:109), [astrabridge_capabilities_mcp_server.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py:128), [astrabridge_capabilities_mcp_server.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py:145)
- Route inspection today reports provider/model candidates, not matrix exposure classes or gate classes: [astrabridge_capabilities_mcp_server.py](/D:/AstraBridge/apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py:170)

Impact:

- Tool consumers can inspect current candidates but cannot yet consume first-class exposure-state data from the MCP layer.
- This weakens automated rollout and repair flows that should be driven by matrix-state outputs.

Required follow-up:

- Later route and MCP projection work should surface matrix-state fields through `astrabridge_capability_routes` or a successor read API.

## Cross-Surface Conclusions

The main repository facts after reconciliation are:

1. Current multimodal routing is usable but not yet matrix-native.
2. Current capability-management surfaces expose route snapshots and contracts, but not explicit rollout states.
3. Current catalog and dry-run evidence are rich enough to seed a matrix, but they still mix route facts, evidence, and UI warnings.
4. The highest-risk implementation gap remains the lack of adapter-family-driven runtime dispatch and the absence of a DashScope image adapter family.

## Next-Step Ownership

These drift findings map directly to the next plan steps:

- Step 4, Stabilize Capability Contracts:
  - normalize capability-facing contract fields and decouple them from UI summaries
- Step 5, Define Adapter Families:
  - replace provider-hardwired runtime dispatch
- Step 6, Add Exposure Gate Rules:
  - add first-class `documented / wired / verified / exposed` projection into runtime and UI surfaces
- Step 10 and Step 11:
  - project dry-run and smoke evidence into the multimodal matrix rather than the broader generic matrix only

## Acceptance Use

This artifact is sufficient for Step 3 of the multimodal handoff plan when:

- a drift report exists on disk
- the report cites concrete file-level mismatches between current surfaces and the multimodal matrix contract
- the report classifies mismatches by severity and ownership surface
- the next implementation entry points are unambiguous
