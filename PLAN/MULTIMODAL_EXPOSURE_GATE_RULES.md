# Multimodal Exposure Gate Rules

Last updated: 2026-07-06

## Purpose

This document defines the gate between multimodal discovery metadata and runnable
runtime exposure.

The problem it solves is current AstraBridge behavior where:

- catalog discovery can contain multimodal-looking models before a lane is truly runnable
- capability routing can still resolve candidates from adapter and provider defaults
- capability-management and MCP surfaces do not yet expose first-class rollout states

The result must be:

- catalog presence does not imply routable support
- route selection only consumes normalized exposure facts
- downgrade behavior is deterministic for `documented_unwired`, `wired_unverified`, and `blocked` lanes

This document is the Step 6 rule set for:

- `image.generate`
- `vision.analyze`
- `speech.transcribe`
- `speech.synthesize`

## Current-State Evidence

The current implementation already exposes useful ingredients, but not a real gate:

- `capabilities/capability_registry.py` resolves candidates from adapter contracts, effective catalog records, and provider defaults, and can still keep a model eligible through adapter override or provider defaults when the effective catalog lacks the model.
- `capabilities/capability_routes.py` currently exposes only `resolved_candidate`, `resolution_status`, and route-mode facts.
- `router_config_service.py` capability-management output exposes `candidate_count`, `resolution_status`, `source_status`, `ui_warnings`, and `last_verified_at`, but not normalized `documented / wired / verified / exposed` states.
- `model_catalog/catalog.py` exports `runtime_provider_contract`, `source_status`, `last_verified_at`, and `ui_warnings`, but still mixes route-relevant and UI-only facts.
- `provider_capability_dry_run_matrix.py` already classifies dry-run outcomes as `supported`, `unsupported`, `conflicting`, or `blocked`, which is enough to seed verified-state projection later.

That means the repository can already compute the raw facts needed for gating, but it does not yet normalize them into one route-authoritative decision.

## Gate Objective

For every concrete `provider/model/capability` lane, AstraBridge must compute:

- `documented_state`
- `wired_state`
- `verified_state`
- `exposure_state`

Only `exposure_state` may decide whether a lane is selectable in normal runtime surfaces.

## Authoritative Gate Inputs

The exposure gate must consume only these classes of inputs.

### Documentation inputs

Used to decide `documented_state`:

- model-level docs-backed matrix row
- official source URLs or reviewed seed provenance
- capability-lane declaration from the multimodal matrix

Current repository landing points:

- `model_catalog/generated_catalog.py`
- `router_config_service.py` model refresh and seed sync
- future multimodal matrix entries

Rule:

- provider-wide claims are not enough when the capability varies by model

### Wiring inputs

Used to decide `wired_state`:

- adapter family exists for the lane
- adapter id exists for the lane
- candidate survives model-level modality eligibility checks
- route can resolve a concrete provider/model/capability adapter path without using optimistic provider-wide inheritance

Current repository landing points:

- `capabilities/specs.py`
- `capabilities/capability_registry.py`
- `capabilities/capability_routes.py`
- future family-aware runtime registry

### Verification inputs

Used to decide `verified_state`:

- static request-shape validation
- dry-run route and contract evidence
- live-smoke evidence where the lane's verification gate class requires it
- durable blocked or conflicting evidence when verification fails

Current repository landing points:

- `provider_capability_dry_run_matrix.py`
- `provider_capability_verification_gate_baseline.json`
- live-smoke artifacts under `PRIVATE/**`

## State Definitions

### `documented_state`

Allowed values:

- `documented`
- `unsupported`
- `unknown`

Normalization rule:

- `documented` requires a model-capability-lane row with primary-source or reviewed seed evidence
- `unsupported` means docs or reviewed policy say the lane should not exist for that model
- `unknown` means AstraBridge lacks trustworthy model-level proof

### `wired_state`

Allowed values:

- `wired`
- `unwired`
- `unknown`

Normalization rule:

- `wired` requires a concrete adapter family and adapter id for the lane plus model-level eligibility success
- `unwired` means the lane is known but lacks a runnable adapter path
- `unknown` means AstraBridge has not yet reconciled the lane against adapter families

### `verified_state`

Allowed values:

- `verified`
- `partial`
- `blocked`
- `unknown`

Normalization rule:

- `verified` means the lane passed the gate class required by the matrix row
- `partial` means some evidence exists, but not enough for rollout
- `blocked` means current evidence proves the lane should not be exposed
- `unknown` means verification has not been performed yet

### `exposure_state`

Allowed values:

- `documented_unwired`
- `wired_unverified`
- `verified_runnable`
- `blocked`
- `deprecated`
- `hidden`
- `unknown`

Normalization rule:

- `exposure_state` is derived, not hand-authored, unless a documented override policy explicitly marks a lane `deprecated` or `hidden`

## Gate Decision Table

| documented_state | wired_state | verified_state | exposure_state | Normal route eligibility |
| --- | --- | --- | --- | --- |
| `documented` | `unwired` | any non-verified state | `documented_unwired` | no |
| `documented` | `wired` | `partial` or `unknown` | `wired_unverified` | no |
| `documented` | `wired` | `verified` | `verified_runnable` | yes |
| any | any | `blocked` | `blocked` | no |
| `unsupported` | any | any | `hidden` or `blocked` | no |
| `unknown` | any | any | `unknown` | no |

Override rules:

1. `deprecated` beats `verified_runnable` for default recommendation and broad UI exposure, but may remain internally routable if later policy allows it.
2. `hidden` beats every non-blocked state for normal UI visibility.
3. `blocked` beats every other route decision.

## Exact Route-Level Gate Conditions

### Condition A: documented gate

A lane may advance past discovery only if:

- `documented_state == documented`

Reject when:

- the lane is only implied by provider defaults
- docs do not support the capability for the concrete model
- the row is still `unknown`

### Condition B: wiring gate

A documented lane may advance to runtime consideration only if:

- `wired_state == wired`
- `adapter_family` is set
- `adapter_id` is set
- model-level modality eligibility passes

Reject when:

- the model looks multimodal in catalog hints but no adapter family exists
- the adapter contract exists only for another capability lane
- the route survives only because provider default fallback filled in a model with no concrete lane proof

### Condition C: verification gate

A wired lane may advance to runnable exposure only if:

- `verified_state == verified`
- the lane meets its `verification_gate_class`

Minimum expected gate classes:

- `image.generate`: at least `static_plus_dry_run_required`, and `live_smoke_required` before broad public exposure
- `speech.transcribe`: at least `static_plus_dry_run_required`
- `speech.synthesize`: at least `static_plus_dry_run_required`
- `vision.analyze`: at least `live_smoke_required` for normal broad exposure

Reject when:

- only docs exist
- dry-run is conflicting or blocked
- live smoke is required but absent

### Condition D: surface gate

Only lanes with `exposure_state == verified_runnable` may appear in:

- normal capability auto-route candidate pools
- normal user-facing pinned model selectors for that capability
- normal MCP route inspection as exposed runnable support

Non-runnable lanes may still appear in:

- diagnostics
- capability-management snapshots
- dry-run reports
- maintainer-only matrix views

## Downgrade Rules

### Downgrade: `documented_unwired`

Trigger:

- docs-backed lane exists but no adapter family or no concrete adapter path exists

Runtime behavior:

- remove from auto-route candidates
- reject pinned-route persistence for normal user-facing route settings
- keep the lane visible only in diagnostics or advanced management views

User-facing explanation:

- "Documented by provider, but AstraBridge does not yet implement a runnable adapter path for this capability."

### Downgrade: `wired_unverified`

Trigger:

- adapter path exists, but required verification evidence is incomplete

Runtime behavior:

- remove from normal auto-route candidates
- reject pinned-route persistence for normal user-facing route settings
- keep diagnostics visible with verification gap details

User-facing explanation:

- "Adapter path exists, but AstraBridge has not yet verified this lane to the required evidence bar."

### Downgrade: `blocked`

Trigger:

- conflicting dry-run evidence
- explicit unsupported-model evidence
- known provider request-shape mismatch
- repeated live-smoke failure that should suppress exposure

Runtime behavior:

- force `eligible_for_auto_route = false`
- force `eligible_for_pinned_route = false`
- surface blocker reasons and latest evidence paths

User-facing explanation:

- "AstraBridge currently blocks this lane because the provider/model/capability combination fails contract or verification checks."

### Downgrade: `hidden`

Trigger:

- intentionally internal-only lane
- protocol-reference lane that should not appear in normal runtime surfaces
- unsupported or unknown lane retained for planning only

Runtime behavior:

- never appear in normal selectors
- remain queryable through internal diagnostics only

## Route-Mode Policy

### Auto route

Allowed only when:

- `exposure_state == verified_runnable`
- `eligible_for_auto_route == true`

### Pinned route

Allowed in normal product UX only when:

- `exposure_state == verified_runnable`
- `eligible_for_pinned_route == true`

Current policy note:

- AstraBridge should not allow normal pinned-route saves for `documented_unwired`, `wired_unverified`, `blocked`, `hidden`, or `unknown` lanes

Future optional policy:

- if a later maintainer-only override mode is added, it must be explicit, audit-visible, and off by default

## File-Level Implementation Ownership

### `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`

Owns:

- model-level capability candidate construction
- modality eligibility rejection
- adapter-family and adapter-id lane truth

Required Step 6 follow-on:

- stop treating adapter override or provider defaults as enough for exposure
- emit normalized lane facts needed for `documented_state` and `wired_state`

### `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_routes.py`

Owns:

- route resolution
- auto versus pinned route decisions
- route-level error messages

Required Step 6 follow-on:

- consume normalized exposure facts instead of raw candidate presence alone
- refuse non-runnable pinned-route targets in normal mode
- return explicit gate failure reasons such as `documented_unwired`, `wired_unverified`, or `blocked`

### `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`

Owns:

- capability-management snapshot
- route persistence surface
- configured model refresh projection

Required Step 6 follow-on:

- add first-class `documented_state`, `wired_state`, `verified_state`, `exposure_state`, `adapter_family`, and `visibility_policy` to capability-management output
- derive `ui_warnings` from gate results rather than treating them as quasi-authoritative inputs

### `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`

Owns:

- export-facing runtime provider contract projection
- current route-relevant metadata merge

Required Step 6 follow-on:

- separate route-authoritative gate facts from UI-only warnings
- export exposure-related metadata in a form that runtime and UI can consume without inference

### `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py`

Owns:

- dry-run evidence normalization
- `supported / unsupported / conflicting / blocked` classification

Required Step 6 follow-on:

- project dry-run classifications into `verified_state` inputs rather than leaving them as side-channel report data only

## Representative Test Requirements

The following tests are required or must be added in the next implementation phase.

### `apps/astrabridge-sidecar/tests/test_capability_routes.py`

Add or extend cases for:

- route excludes `documented_unwired` lanes from auto mode
- route excludes `wired_unverified` lanes from auto mode
- pinned route rejects non-runnable lane targets with explicit gate reason
- verified runnable lane remains selectable

### `apps/astrabridge-sidecar/tests/test_capability_registry.py`

Add or extend cases for:

- model-level modality mismatch produces `unwired` or blocked lane facts instead of a candidate
- adapter override without documentation does not become exposed support
- catalog-only documented row without adapter family becomes `documented_unwired`

### `apps/astrabridge-sidecar/tests/test_router_config_service.py`

Add or extend cases for:

- capability-management snapshot includes normalized gate states
- `ui_warnings` are derived from gate output and do not replace authoritative state
- hidden or blocked lanes stay visible in diagnostics but not as available runtime support

### `apps/astrabridge-sidecar/tests/test_provider_capability_dry_run_matrix.py`

Add or extend cases for:

- `unsupported` dry-run outcomes map to non-runnable verification input
- `conflicting` or `blocked` dry-run outcomes force blocked exposure
- verified evidence does not overrule missing documentation or missing wiring

## Acceptance Use

This artifact is sufficient for Step 6 of the multimodal handoff plan when:

- it defines the exact gate conditions required for a lane to move from `documented` to `exposed`
- it specifies route-level gate behavior for auto and pinned routes
- it defines deterministic downgrade behavior for `documented_unwired`, `wired_unverified`, and `blocked` lanes
- it names file-level implementation ownership for the follow-on code changes
- it specifies representative positive and negative tests
