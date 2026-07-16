# Multimodal Capability Matrix Contract

Last updated: 2026-07-06

## Purpose

This document defines the contract for AstraBridge's multimodal capability matrix.

The matrix is the single source of truth for multimodal provider and model state across:

- capability routing
- runtime adapter eligibility
- catalog-to-runtime promotion
- desktop and MCP capability-management surfaces
- dry-run and live-smoke evidence
- automated provider update and rollout gates

This contract is narrower than the broader provider/model compatibility matrix. It focuses only on the multimodal capability lanes frozen in:

- `PLAN/MULTIMODAL_CAPABILITY_SCOPE_AND_INVARIANTS.md`

It must make it impossible for a later agent to confuse:

- provider-wide defaults with model-level support
- documented support with runnable support
- wired support with exposed support
- UI hints with route-authoritative facts

## Governing Scope

The matrix only governs these capability ids:

- `image.generate`
- `vision.analyze`
- `speech.transcribe`
- `speech.synthesize`

The matrix must support these provider classes in the current priority set:

- `yunwu`
- `qwen`
- `kimi`
- `glm`
- `deepseek`
- `openai` protocol-reference rows only unless the user later authorizes official live testing

`web.search` is out of matrix routing scope because it remains a standalone web lane.

## Design Rules

The multimodal matrix must follow these rules:

1. It must be secret-free.
2. It must separate `documented`, `wired`, `verified`, and `exposed` states.
3. It must be model-level first for any lane that can vary by model.
4. It must define field classes so later agents know which fields can influence routing and which may only influence UI.
5. It must remain compatible with the broader provider/model compatibility contract rather than replacing it.
6. It must represent both positive support and intentionally blocked or hidden support.
7. It must not treat generated catalog presence as proof of runtime support.
8. It must be extensible so new provider families or new model families can be added without schema breakage.

## Source Precedence

The matrix must resolve declaration and exposure disputes using this precedence.

### Declaration precedence

1. official model-level documentation or maintained fetched model metadata
2. model-level configured metadata or reviewed seed overrides
3. capability-specific adapter-family declarations
4. provider default-model metadata
5. provider-wide broad capability flags

Rule:

- lower-precedence sources may fill gaps but must not silently override stronger model-level evidence

### Runtime and exposure precedence

1. capability route eligibility derived from current adapter-family wiring
2. runtime-normalized effective model metadata
3. persisted exposure-gate state
4. generated catalog metadata
5. provider defaults

Rule:

- if route eligibility and catalog metadata disagree, route eligibility wins

### Validation precedence

1. current live-smoke or real workflow evidence
2. current static request-shape validation
3. current dry-run route and contract evidence
4. official docs and maintained source registry
5. provider defaults without model-level proof

Rule:

- docs may explain a lane but cannot mark it verified by themselves

## Support-State Vocabulary

Every matrix row must distinguish these rollout-oriented states:

| State | Meaning |
| --- | --- |
| `documented_unwired` | Docs or trusted source registry show the lane exists, but AstraBridge lacks a concrete adapter path. |
| `wired_unverified` | AstraBridge has a concrete adapter path and route representation, but required verification is incomplete. |
| `verified_runnable` | The lane is wired and current evidence proves it behaves correctly at the required layer. |
| `blocked` | The lane is intentionally blocked because evidence, request-shape constraints, or missing prerequisites make it unsafe. |
| `deprecated` | The lane exists but should not be chosen for new exposure or default routing. |
| `hidden` | The lane may remain tracked internally but must not appear in normal user-facing selectable surfaces. |
| `unknown` | AstraBridge lacks enough trustworthy evidence to classify the lane. |

Interpretation rule:

- only `verified_runnable` may be promoted to default user-visible runnable support without an explicit override policy

## Field Classes

Every field in the matrix belongs to exactly one of these classes.

### Route-authoritative fields

These fields may influence route selection, exposure gating, auto-routing, or blocking:

- `provider_id`
- `model_id`
- `capability_id`
- `entry_kind`
- `documented_state`
- `wired_state`
- `verified_state`
- `exposure_state`
- `route_mode_support`
- `eligible_for_auto_route`
- `eligible_for_pinned_route`
- `adapter_family`
- `adapter_id`
- `effective_input_modalities`
- `effective_output_modalities`
- `required_request_shapes`
- `request_constraints`
- `runtime_blockers`
- `deprecation_state`
- `visibility_policy`
- `verification_gate_class`

Rule:

- a later agent must be able to decide whether a lane may be routed or exposed using only route-authoritative fields plus current evidence references

### UI-informational fields

These fields may be displayed to users or maintainers but must not by themselves affect routing:

- `display_name`
- `provider_display_name`
- `model_display_name`
- `capability_display_name`
- `ui_badges`
- `ui_warnings`
- `ui_hints`
- `example_use_cases`
- `recommended_for_provider`
- `recommended_for_capability`
- `authority_tier_label`
- `artifact_preview_kind`
- `notes`

Rule:

- UI fields may summarize route facts but must never be the canonical source for route decisions

### Verification-only fields

These fields exist to explain or prove current evidence status and must not change routing by themselves:

- `docs_sources`
- `evidence_records`
- `evidence_paths`
- `last_verified_at`
- `last_docs_checked_at`
- `validation_scope`
- `known_failures`
- `known_pitfalls`
- `usage_signals`
- `verification_notes`
- `observed_route_mismatches`
- `observed_artifact_issues`

Rule:

- verification-only fields inform exposure-state transitions, but a route should consume the already-normalized authoritative state rather than raw evidence details

## Top-Level Shape

```json
{
  "schema_version": "astrabridge-multimodal-capability-matrix-v1",
  "generated_at": "2026-07-06T18:00:00+09:00",
  "matrix_id": "multimodal-capability-baseline",
  "scope_ref": "PLAN/MULTIMODAL_CAPABILITY_SCOPE_AND_INVARIANTS.md",
  "capabilities": [
    "image.generate",
    "vision.analyze",
    "speech.transcribe",
    "speech.synthesize"
  ],
  "field_classes": {
    "route_authoritative": [],
    "ui_informational": [],
    "verification_only": []
  },
  "status_definitions": {
    "documented_states": ["documented", "unsupported", "unknown"],
    "wired_states": ["wired", "unwired", "unknown"],
    "verified_states": ["verified", "partial", "blocked", "unknown"],
    "exposure_states": [
      "documented_unwired",
      "wired_unverified",
      "verified_runnable",
      "blocked",
      "deprecated",
      "hidden",
      "unknown"
    ]
  },
  "entries": [],
  "redaction_rules": {
    "secret_free": true,
    "forbidden_field_markers": [
      "api_key",
      "authorization",
      "cookie",
      "password",
      "secret",
      "access_token",
      "refresh_token",
      "session_token",
      "vault_password",
      "admin_session_token"
    ]
  }
}
```

## Required Top-Level Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | Must start at `astrabridge-multimodal-capability-matrix-v1`. |
| `generated_at` | yes | ISO 8601 generation time. |
| `matrix_id` | yes | Stable identifier for one matrix snapshot. |
| `scope_ref` | yes | Path to the governing scope and invariants document. |
| `capabilities` | yes | The multimodal capability ids governed by this matrix. |
| `field_classes` | yes | Explicit lists of route-authoritative, UI-informational, and verification-only fields. |
| `status_definitions` | yes | Allowed enums for documented, wired, verified, and exposure states. |
| `entries` | yes | Provider-level or provider/model/capability rows. |
| `redaction_rules` | yes | Secret-handling rules for the matrix. |

## Entry Kinds

The matrix supports two row kinds:

1. `provider_default`
2. `model_capability_lane`

Rule:

- provider defaults may summarize defaults and fallback behavior
- route and exposure decisions for concrete capability lanes must be made from `model_capability_lane` rows whenever they exist

## Entry Identity

Each `model_capability_lane` row must use this identity tuple:

- `provider_id`
- `model_id`
- `capability_id`

Recommended stable `entry_id`:

- `provider_id/model_id:capability_id`

Example:

- `qwen/qwen3-vl-plus:vision.analyze`

## Provider-Default Entry Schema

Provider-default rows capture broad defaults without promoting per-model support.

Required fields:

| Field | Class | Meaning |
| --- | --- | --- |
| `entry_id` | route-authoritative | Stable row identifier such as `qwen:provider_default`. |
| `entry_kind` | route-authoritative | Must be `provider_default`. |
| `provider_id` | route-authoritative | Canonical provider id. |
| `provider_display_name` | UI | Secret-free display label. |
| `default_model_id` | route-authoritative | Current effective provider default model, if any. |
| `default_adapter_families` | route-authoritative | Adapter families the provider currently uses for the in-scope lanes. |
| `declared_defaults` | route-authoritative | Default modality and capability declarations that may seed model rows. |
| `runtime_defaults` | route-authoritative | Effective runtime defaults after normalization. |
| `verification_summary` | verification-only | Aggregated evidence status for the provider. |
| `warnings` | UI | Secret-free high-level warnings. |

Rule:

- provider-default rows are advisory for missing model rows and must not overrule a concrete `model_capability_lane` row

## Model-Capability-Lane Entry Schema

Each concrete lane row must include these fields.

| Field | Class | Meaning |
| --- | --- | --- |
| `entry_id` | route-authoritative | Stable lane identifier. |
| `entry_kind` | route-authoritative | Must be `model_capability_lane`. |
| `provider_id` | route-authoritative | Canonical provider id. |
| `model_id` | route-authoritative | Canonical provider/model id. |
| `capability_id` | route-authoritative | One of the four governed multimodal capability ids. |
| `display_name` | UI | User-visible lane label. |
| `provider_display_name` | UI | Provider label for UI. |
| `model_display_name` | UI | Model label for UI. |
| `capability_display_name` | UI | Capability label for UI. |
| `documented_state` | route-authoritative | `documented`, `unsupported`, or `unknown`. |
| `wired_state` | route-authoritative | `wired`, `unwired`, or `unknown`. |
| `verified_state` | route-authoritative | `verified`, `partial`, `blocked`, or `unknown`. |
| `exposure_state` | route-authoritative | Rollout-facing exposure state. |
| `adapter_family` | route-authoritative | Family id such as `openai_compatible_image` or `dashscope_tts`. |
| `adapter_id` | route-authoritative | Concrete current adapter contract id when one exists. |
| `route_mode_support` | route-authoritative | Whether the lane supports `auto`, `pinned`, and explicit routing. |
| `eligible_for_auto_route` | route-authoritative | Whether current facts allow auto-route selection. |
| `eligible_for_pinned_route` | route-authoritative | Whether pinned selection is allowed if explicitly chosen. |
| `effective_input_modalities` | route-authoritative | Effective input modalities after runtime normalization. |
| `effective_output_modalities` | route-authoritative | Effective output modalities after runtime normalization. |
| `required_request_shapes` | route-authoritative | Abstract request-shape requirements for the lane. |
| `request_constraints` | route-authoritative | File count, media, size, transport, or parameter constraints that can block a route. |
| `runtime_blockers` | route-authoritative | Secret-free reasons the lane is not currently eligible. |
| `deprecation_state` | route-authoritative | `active`, `deprecated`, or `retired`. |
| `visibility_policy` | route-authoritative | `normal`, `advanced_only`, `hidden`, or `internal_only`. |
| `verification_gate_class` | route-authoritative | The required verification bar before exposure. |
| `docs_sources` | verification-only | Official or trusted docs references for this lane. |
| `evidence_records` | verification-only | Structured proof records for dry-run, static checks, or live smoke. |
| `evidence_paths` | verification-only | Secret-free artifact references. |
| `last_docs_checked_at` | verification-only | Most recent docs-check timestamp. |
| `last_verified_at` | verification-only | Most recent verification timestamp. |
| `validation_scope` | verification-only | Human-readable evidence scope. |
| `known_failures` | verification-only | Current observed failures. |
| `known_pitfalls` | verification-only | Current observed quirks or caveats. |
| `usage_signals` | verification-only | Secret-free token, latency, or artifact-count observations. |
| `ui_badges` | UI | Badges for desktop display only. |
| `ui_warnings` | UI | User-facing warnings that summarize authoritative facts. |
| `ui_hints` | UI | Non-authoritative usage hints. |
| `recommended_for_provider` | UI | Whether the lane is a preferred option inside the provider. |
| `recommended_for_capability` | UI | Whether the lane is a preferred option across providers for the capability. |
| `notes` | UI | Secret-free free-form notes. |

## Required Request-Shape Vocabulary

`required_request_shapes` must use stable abstract names rather than provider-native parameter names.

Recommended values include:

- `text_prompt_required`
- `image_inputs_required`
- `audio_inputs_required`
- `multipart_edit_inputs`
- `remote_image_urls_allowed`
- `base64_image_content_allowed`
- `streaming_audio_events`
- `single_turn_analysis`
- `artifact_manifest_expected`

Rule:

- provider-native parameter names may be referenced inside notes, but routing and validation should consume the abstract shape vocabulary

## Verification Gate Classes

Every concrete lane row must declare one of these gate classes:

| Gate class | Meaning |
| --- | --- |
| `docs_only` | Discovery retained, but no runtime promotion is allowed yet. |
| `dry_run_required` | The lane must pass route and contract dry-run before any exposure. |
| `static_plus_dry_run_required` | The lane needs request-shape validation plus dry-run route success. |
| `live_smoke_required` | The lane must also have current live-smoke evidence before exposure. |
| `manual_override_only` | Exposure requires explicit human-approved override even if wired. |

Rule:

- `image.generate`, `speech.transcribe`, and `speech.synthesize` should generally target at least `static_plus_dry_run_required`
- provider-backed public exposure should generally target `live_smoke_required`

## Example Concrete Entry

```json
{
  "entry_id": "qwen/qwen3-vl-plus:vision.analyze",
  "entry_kind": "model_capability_lane",
  "provider_id": "qwen",
  "model_id": "qwen/qwen3-vl-plus",
  "capability_id": "vision.analyze",
  "display_name": "Qwen3 VL Plus Vision Analyze",
  "provider_display_name": "Qwen / DashScope",
  "model_display_name": "Qwen3 VL Plus",
  "capability_display_name": "Vision Analyze",
  "documented_state": "documented",
  "wired_state": "wired",
  "verified_state": "partial",
  "exposure_state": "wired_unverified",
  "adapter_family": "chat_multimodal_vision",
  "adapter_id": "qwen.vision.chat.v1",
  "route_mode_support": {
    "auto": true,
    "pinned": true,
    "explicit": true
  },
  "eligible_for_auto_route": true,
  "eligible_for_pinned_route": true,
  "effective_input_modalities": ["text", "image"],
  "effective_output_modalities": ["text"],
  "required_request_shapes": ["image_inputs_required", "single_turn_analysis"],
  "request_constraints": {
    "remote_image_urls_allowed": true
  },
  "runtime_blockers": [],
  "deprecation_state": "active",
  "visibility_policy": "normal",
  "verification_gate_class": "live_smoke_required",
  "docs_sources": [
    {
      "source_kind": "official_docs",
      "url": "https://help.aliyun.com/zh/model-studio/vision"
    }
  ],
  "evidence_records": [],
  "evidence_paths": [],
  "last_docs_checked_at": "2026-07-06T18:00:00+09:00",
  "last_verified_at": "",
  "validation_scope": "route and capability contract only",
  "known_failures": [],
  "known_pitfalls": [],
  "usage_signals": {},
  "ui_badges": ["image-input", "wired"],
  "ui_warnings": ["Live-smoke evidence is still required before broad exposure."],
  "ui_hints": ["Use image inputs rather than text-only model routes for image analysis."],
  "recommended_for_provider": true,
  "recommended_for_capability": false,
  "notes": []
}
```

## Mapping To Current Repository Surfaces

Later steps should map current code and artifacts into this contract as follows.

| Current surface | Expected matrix contribution |
| --- | --- |
| `capabilities/specs.py` | `adapter_family`, `adapter_id`, capability-to-model declarations, transport and capability-facing contract hints |
| `capabilities/capability_registry.py` | route eligibility, candidate selection semantics, effective modalities, route blockers |
| `capabilities/capability_routes.py` | `route_mode_support`, `eligible_for_auto_route`, `eligible_for_pinned_route`, route-resolution outputs |
| `capabilities/runtime.py` | concrete runtime dispatch ownership per capability and provider family |
| `model_catalog/generated_catalog.py` | documented discovery, model identifiers, default metadata, seed confidence |
| `router_config_service.py` | provider-model overrides, effective default models, UI warning inputs, route persistence |
| smoke and validation artifacts under `PRIVATE/**` or test outputs | `verified_state`, `evidence_records`, `known_failures`, `known_pitfalls` |

## Redaction Rules

The matrix must not store:

- raw API keys
- auth headers
- cookies
- bearer tokens
- raw provider request bodies containing secrets
- raw provider response bodies containing reusable secrets
- vault paths or passwords that expose secret retrieval details

Allowed content:

- provider ids
- model ids
- capability ids
- secret-free file paths
- normalized warnings
- token and latency summaries
- evidence classifications
- documentation URLs

## Acceptance Use

This artifact is sufficient for Step 2 of the multimodal handoff plan when:

- it exists on disk
- it names route-authoritative, UI-informational, and verification-only fields
- it defines a stable row shape for concrete `provider/model/capability` lanes
- it defines status vocabulary that matches the frozen `documented`, `wired`, `verified`, and `exposed` fact boundary
- a later agent can decide whether a lane may be exposed without reconstructing chat history
