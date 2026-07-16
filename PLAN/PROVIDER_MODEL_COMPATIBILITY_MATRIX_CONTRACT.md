# Provider Model Compatibility Matrix Contract

Last updated: 2026-07-06

## Purpose

This document defines the contract for AstraBridge's provider/model compatibility matrix.

The matrix is intended to be the shared shape for:

- provider/profile metadata review
- generated runtime contract summaries
- managed-vault provider readiness UI
- provider-backed health and smoke evidence
- upgrade and onboarding gates for new models or new providers

The contract must stay secret-free and must distinguish what AstraBridge declares, what the runtime normalizes, and what real validation has actually proved.

## Design Rules

The compatibility matrix must follow these rules:

- It must not contain API keys, bearer tokens, cookies, authorization headers, session tokens, vault passwords, desktop `key.txt` paths, or provider raw secrets.
- It may contain provider ids, model ids, display names, environment variable names, secret-free file paths, token usage counts, status strings, warnings, and evidence references.
- It must separate three evidence layers for every provider or model entry:
  - `declared_capability`: what AstraBridge source defines or advertises
  - `runtime_normalized_contract`: what AstraBridge turns that declaration into for Codex runtime and app-server use
  - `validated_evidence`: what current tests, health checks, smoke runs, or preserved reports have actually exercised
- It must not treat declared capability as proof of real compatibility.
- Web search remains a standalone web lane unless the user explicitly changes that product boundary.
- The contract must stay extensible so new provider families can add fields without breaking existing consumers.
- It must define stable capability dimensions that can be compared across providers and models without collapsing everything into one provider-wide status.
- It must define explicit source precedence so provider-level defaults cannot silently override model-level evidence.

## Capability Taxonomy

The matrix must use a stable capability taxonomy for provider/model comparison. Each dimension is tracked separately even when the current product does not yet expose a dedicated adapter for that dimension.

| Dimension | Meaning | Typical declaration sources | Typical validation sources |
| --- | --- | --- | --- |
| `text_input` | Model accepts text input. | Provider profile, generated/effective model catalog, adapter contract. | Dry-run route resolution, text smoke, workflow runs. |
| `text_output` | Model produces usable text output. | Provider profile, generated/effective model catalog. | Health checks, text smoke, workflow runs. |
| `image_input` | Model accepts image input for analysis or multimodal chat. | Model catalog `input_modalities`, adapter `model_match`, modality limits. | Static image-shape validation, vision smoke, workflow runs. |
| `image_output` | Model produces image artifacts. | Image-generation adapter contract, catalog model metadata. | Image generation smoke, artifact persistence checks, UI preview. |
| `audio_input` | Model accepts audio input. | Model catalog `input_modalities`, ASR adapter contract, modality notes. | Static audio-shape validation, ASR smoke. |
| `audio_output` | Model produces audio output. | TTS adapter contract, model metadata. | TTS smoke, artifact validation, playback/container checks. |
| `video_input` | Model accepts video input when applicable. | Model catalog `input_modalities`, modality limits, official docs. | Static validation, provider smoke, workflow evidence when available. |
| `video_output` | Model produces video output when applicable. | Official docs, model metadata. | Provider smoke and artifact validation when available. |
| `tool_calling` | Model can call structured tools in AstraBridge/Codex flows. | Provider profile, runtime contract, transport/tool schema policy. | Tool smoke, code-agent runs, command-event evidence. |
| `parallel_tools` | Model can safely emit parallel tool calls. | Provider profile, runtime contract, adapter or transport metadata. | Parallel tool smoke, workflow evidence. |
| `streaming` | Model or capability lane supports streaming response flow. | Provider profile, capability spec transport mode, adapter contract. | Stream smoke, SSE/runtime evidence. |
| `structured_edit` | Model can be routed into structured edit or `apply_patch`-style workflows. | Provider profile edit policy, runtime contract `apply_patch_tool_type`. | Edit smoke, code-agent workflow evidence. |
| `web_search` | Model/provider can participate in the standalone web lane or native/tool web search support. | Tool policy, runtime web capability normalization. | Web smoke, citation-quality evidence, workflow runs. |
| `context_window` | Declared and effective context-window behavior. | Provider profile, model catalog, runtime normalization. | Context-gate dry-run, compact/continuation evidence. |
| `output_limit` | Declared and effective output/token/tool-output budget behavior. | Provider profile, runtime normalization. | Dry-run contract checks, long-turn evidence. |
| `prompt_cache` | Provider/model advertises prompt-cache behavior. | Provider profile, model metadata. | Live usage evidence when exposed, otherwise remains declaration-only. |
| `reasoning` | Provider/model exposes reasoning/thinking mode or effort controls. | Provider profile reasoning policy, model metadata, runtime normalization. | Static mapping audit, live reasoning smoke, workflow evidence. |

Rule:

- The taxonomy is per dimension, not one provider-wide boolean.
- A provider row may summarize defaults, but model rows own promotion for concrete lanes.
- `video_input` and `video_output` may remain `unknown` or `unsupported` until AstraBridge has a declared path for them.

## Fact Boundary

The matrix has one top-level list of entries. Each entry may describe either a provider rollup or a concrete provider/model lane.

Every entry must include three mandatory sub-sections:

1. `declared_capability`
2. `runtime_normalized_contract`
3. `validated_evidence`

Rule:

- `declared_capability` must describe source-of-truth metadata only.
- `runtime_normalized_contract` must describe AstraBridge's transformed runtime-facing contract only.
- `validated_evidence` is the only section allowed to summarize what has actually passed, failed, or remained partial in current evidence.

## Status Vocabulary

The contract uses three related status vocabularies:

1. Declaration state for capability dimensions:
   - `declared`: the source layer claims the dimension exists.
   - `unsupported`: the source layer explicitly says the dimension is not supported for this entry.
   - `unknown`: AstraBridge has no trustworthy declaration for this dimension yet.
2. Validation status for evidence records:
   - `pass`, `warn`, `fail`, `partial`, `skipped`, `blocked`, `unknown`
3. Promotion status for the whole row:
   - `verified`, `partial`, `blocked`, `unknown`

Rules:

- `failed` is represented at the evidence layer as `validation_status=fail`.
- A row with one or more failed high-priority evidence records usually promotes to `blocked`, not to a separate top-level `failed` enum.
- `unsupported` is a declaration-state value for a dimension, not proof that runtime blocking and UI messaging are already correct.

## JSON Shape

```json
{
  "schema_version": "astrabridge-provider-model-compatibility-matrix-v1",
  "generated_at": "2026-07-04T20:00:00+09:00",
  "matrix_id": "provider-compatibility-baseline",
  "capability_taxonomy": {
    "dimensions": [
      "text_input",
      "text_output",
      "image_input",
      "image_output",
      "audio_input",
      "audio_output",
      "video_input",
      "video_output",
      "tool_calling",
      "parallel_tools",
      "streaming",
      "structured_edit",
      "web_search",
      "context_window",
      "output_limit",
      "prompt_cache",
      "reasoning"
    ]
  },
  "source_precedence": {
    "declaration": [
      "official_or_fetched_model_level_source",
      "configured_model_override",
      "capability_specific_adapter_contract",
      "provider_default_model_metadata",
      "provider_level_broad_capability_flags"
    ],
    "validation": [
      "current_live_smoke_or_real_workflow_evidence",
      "current_static_request_shape_validation",
      "current_dry_run_contract_evidence",
      "official_docs_and_source_registry",
      "provider_defaults_without_model_level_support"
    ]
  },
  "matrix_scope": {
    "source_kind": "registry_runtime_and_evidence",
    "managed_session_mode": "managed_user",
    "managed_username": "astra",
    "registry_provider_ids": ["openai", "yunwu", "deepseek", "qwen", "kimi", "glm"],
    "effective_provider_ids": ["yunwu", "deepseek", "qwen", "kimi", "glm"],
    "web_lane_policy": "standalone"
  },
  "status_definitions": {
    "declared_states": ["declared", "unsupported", "unknown"],
    "overall_statuses": ["verified", "partial", "blocked", "unknown"],
    "validation_statuses": ["pass", "warn", "fail", "partial", "skipped", "blocked", "unknown"]
  },
  "entry_section_names": [
    "declared_capability",
    "runtime_normalized_contract",
    "validated_evidence"
  ],
  "entries": [
    {
      "entry_id": "qwen/qwen3.7-plus",
      "entry_kind": "model",
      "provider_id": "qwen",
      "model_id": "qwen/qwen3.7-plus",
      "display_name": "Qwen 3.7 Plus",
      "declared_capability": {
        "capability_dimensions": {
          "image_input": {"declared_state": "declared"},
          "audio_output": {"declared_state": "unsupported"}
        }
      },
      "runtime_normalized_contract": {},
      "validated_evidence": {
        "evidence_records": []
      },
      "overall_status": "partial",
      "warnings": []
    }
  ],
  "evidence_index": {
    "source_files": [],
    "runtime_sources": [],
    "artifact_paths": []
  },
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
    ],
    "notes": [
      "Store paths, summaries, usage signals, and evidence references only.",
      "Do not embed raw provider requests, raw provider responses, auth headers, cookies, or reusable secrets."
    ]
  }
}
```

## Top-Level Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | Matrix schema version. Start at `astrabridge-provider-model-compatibility-matrix-v1`. |
| `generated_at` | yes | ISO 8601 generation timestamp. |
| `matrix_id` | yes | Stable identifier for one generated matrix snapshot. |
| `capability_taxonomy` | yes | Stable taxonomy dimensions used across provider and model rows. |
| `source_precedence` | yes | Ordered source precedence for declaration and validation decisions. |
| `matrix_scope` | yes | Secret-free scope metadata for the session and source set used to produce the matrix. |
| `status_definitions` | yes | Allowed enums for `overall_status` and `validation_status`. |
| `entry_section_names` | yes | Required three-section contract list. |
| `entries` | yes | Provider or model compatibility entries. |
| `evidence_index` | yes | Source file, runtime source, and artifact references used by the matrix. |
| `redaction_rules` | yes | Explicit statement of forbidden field classes and allowed evidence style. |

## Entry Schema

Each entry must include these fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `entry_id` | yes | Stable identifier for the row. Prefer `provider_id` for provider rows and `provider_id/model_id` for model rows. |
| `entry_kind` | yes | `provider` or `model`. |
| `provider_id` | yes | Canonical provider id. |
| `model_id` | model rows | Canonical provider/model id for model rows; `null` for provider-only rollups. |
| `display_name` | yes | Secret-free user-visible label. |
| `declared_capability` | yes | Source-defined or profile-defined metadata. |
| `runtime_normalized_contract` | yes | Effective Codex/app-server runtime contract after AstraBridge normalization. |
| `validated_evidence` | yes | Current evidence-backed validation results only. |
| `overall_status` | yes | One of `verified`, `partial`, `blocked`, `unknown`. |
| `warnings` | yes | Secret-free warnings that do not belong in one sub-section. |

## `declared_capability`

This section describes source-defined behavior only. It should be built from provider profiles, registry defaults, profile service state, or static capability declarations.

Required fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `source_of_truth` | yes | File paths or source identifiers used to produce this declaration block. |
| `capability_dimensions` | yes | Stable dimension map keyed by the taxonomy names. Each dimension must expose at least `declared_state` and may include notes, modality limits, or declaration-specific source refs. |
| `protocol` | yes | Declared protocol such as `responses`, `qwen_responses`, or `chat`. |
| `reasoning_mode` | yes | Declared reasoning/thinking mode such as `openai_responses`, `enable_thinking`, `reasoning_content`, or `reasoning_effort`. |
| `default_model` | provider rows | Declared default model before effective-runtime filtering. |
| `input_modalities` | yes | Declared supported input modalities. |
| `edit_policy` | yes | Declared edit strategy by task size. |
| `tool_policy` | yes | Declared tool surface such as `apply_patch`, web tool types, MCP tool policy, and search support. |
| `context_policy` | yes | Declared context-window, compact-limit, and tool-output-limit metadata. |
| `fallback_policy` | yes | Declared fallback model and modality downgrade policy. |

This section must not include live key availability, live health, or smoke conclusions.

Dimension rules:

- Provider rows may summarize provider-wide defaults, but they must not silently promote a model-specific dimension to `declared` when model-level or adapter-level metadata is absent.
- If a provider-level flag is broad, but a capability-specific adapter gates only some models, model rows win for routing purposes.
- If the current declaration layer cannot prove a model-specific capability, use `unknown` rather than inheriting `declared` from a broad provider flag.

## `runtime_normalized_contract`

This section describes AstraBridge's transformed runtime-facing contract after catalog and runtime normalization.

Required fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `source_of_truth` | yes | Runtime or catalog source identifiers used to produce this section. |
| `managed_key_available` | yes | Whether the current managed session exposes an encrypted key for this provider. |
| `effective_default_model` | provider rows | Effective default model after runtime filtering and effective catalog generation. |
| `codex_runtime_metadata` | yes | Codex-facing normalized metadata such as reasoning effort values, context limits, `apply_patch` type, web search type, modalities, and tool-output limit. |
| `capability_metadata` | yes | Runtime contract summaries such as tool schema, vision flags, MCP state, token usage availability, and web capability status. |
| `authority` | yes | Runtime authority tier and parallel-tool status derived from the normalized contract. |
| `contract_warnings` | yes | Warnings generated during normalization, such as unsupported apply-patch mapping or unverified context windows. |

This section is allowed to record normalized metadata even when it is not yet validated in production.

## `validated_evidence`

This section describes what has actually been tested or observed through health checks, smoke runs, dogfood records, or preserved screenshots/artifacts.

Required fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `validation_status` | yes | `pass`, `warn`, `fail`, `partial`, `skipped`, `blocked`, or `unknown`. |
| `health_status` | yes | Current health or smoke status summary for the entry. |
| `validation_scope` | yes | Human-readable description of which path was exercised: text, code-agent, handoff, vision, image generation, ASR, TTS, web lane, and so on. |
| `evidence_paths` | yes | Secret-free file references for current evidence. |
| `evidence_records` | yes | Structured evidence attachments describing what kind of evidence was gathered and which dimensions or lanes it covers. |
| `last_verified_at` | yes | Most recent evidence timestamp when known. |
| `usage_signals` | yes | Token/cost counts or explicit unavailability markers. |
| `known_failures` | yes | Failure modes actually observed in evidence. |
| `known_pitfalls` | yes | Provider quirks that were observed or repaired. |
| `notes` | yes | Free-form secret-free validation notes. |

This is the only section allowed to say that a path is truly passed, partial, or broken in current evidence.

Each `evidence_records` item should follow this target shape:

```json
{
  "evidence_kind": "official_docs | static_request_validation | dry_run | live_smoke | workflow_dogfood | ui_observability | manual_review",
  "status": "pass | warn | fail | partial | skipped | blocked | unknown",
  "covers": ["image_input", "vision.analyze"],
  "source_refs": ["PRIVATE/provider-compatibility/runs/example/summary.json"],
  "observed_at": "2026-07-06T12:00:00+09:00",
  "notes": ["Secret-free explanatory note."]
}
```

Attachment rules:

- Official documentation attaches primarily to `declared_capability.source_of_truth`, and may appear in `evidence_records` only as declaration support or manual review context. Official docs alone do not validate a lane.
- Static request-shape validation attaches to `validated_evidence.evidence_records[]` with `evidence_kind=static_request_validation`.
- Dry-run route or normalized-contract generation attaches to `validated_evidence.evidence_records[]` with `evidence_kind=dry_run`.
- Live provider smoke attaches to `validated_evidence.evidence_records[]` with `evidence_kind=live_smoke`.
- Real workflow or dogfood evidence attaches to `validated_evidence.evidence_records[]` with `evidence_kind=workflow_dogfood`.

## Status Rules

- `verified`: declared capability, runtime contract, and validation evidence are all present for the assessed lane and current evidence is sufficient for the intended product claim.
- `partial`: some important evidence exists, but a meaningful gap remains.
- `blocked`: evidence shows a concrete incompatibility or unsafe condition that prevents promotion.
- `unknown`: AstraBridge does not yet have enough trustworthy evidence to classify the lane.

Rule:

- Do not promote a lane to `verified` using only `declared_capability` or `runtime_normalized_contract`.
- A lane with only health or preview evidence but no realistic workflow evidence should usually remain `partial`.

## Source Precedence

The matrix must follow explicit source precedence instead of treating every metadata surface as equally strong.

### Declaration precedence

Use this order, strongest first:

1. Explicit model-level official or fetched source with source provenance.
2. Explicit configured model override for the current runtime.
3. Capability-specific adapter contract such as `model_match` and request-builder constraints.
4. Provider default-model metadata derived from normalized provider defaults.
5. Broad provider-level capability flags or provider default input modalities.

Rules:

- Stronger declaration sources may narrow or override weaker ones.
- Weaker declaration sources must not silently broaden a model capability that is absent from a stronger source.
- A provider-level `supports_vision` flag is never sufficient to promote all provider models to image-input capable.

### Validation precedence

Use this order, strongest first:

1. Current live smoke or real workflow evidence on the current code/runtime.
2. Current static request-shape validation on the current code/runtime.
3. Current dry-run contract and route-generation evidence.
4. Official documentation and source-registry metadata.
5. Provider-family broad defaults without model-level support.

Rules:

- More direct current-version runtime evidence beats older or more indirect evidence.
- A fresh fail on the current version outranks an older pass from a different request shape or older code path.
- Official docs may justify `declared`, but they do not justify `verified` without runtime evidence.

## Provider-Level Versus Model-Level Rule

The matrix must explicitly reject this anti-pattern:

- inferring that every model under a provider supports a capability because one provider-level boolean or default modality suggests it

Required behavior:

- Provider rows summarize defaults and family-level expectations.
- Model rows control promotion for concrete capability lanes.
- Capability routing and compatibility promotion must use the strongest model-specific source available.
- When model-level evidence is missing, the matrix should prefer `unknown` or `unsupported` over optimistic inheritance from provider-wide defaults.

## Secret-Free Rules

The matrix must reject or exclude these classes of content:

- fields named like `api_key`, `authorization`, `cookie`, `password`, `secret`, `access_token`, `refresh_token`, `session_token`, `vault_password`, or `admin_session_token`
- raw authorization or bearer strings
- desktop `key.txt` paths
- raw provider request or response bodies
- inline image data URLs or base64 payloads

Allowed examples:

- environment variable names such as `YUNWU_API_KEY`
- token counts such as `input_tokens`, `output_tokens`, `reasoning_tokens`, `total_tokens`
- redacted evidence paths under `PRIVATE/**`
- provider ids, model ids, adapter ids, and status strings

## Current Machine-Readable Helper

The current code-side template and validator live in:

- `apps/astrabridge-sidecar/astrabridge_sidecar/provider_model_compatibility_matrix.py`

That helper currently provides:

- an empty matrix template
- an entry template for `provider` and `model` rows
- secret-free validation for the matrix payload

The helper is currently a conservative subset of this contract. Step 3 and later implementation slices must align generated matrix payloads with the added taxonomy, source-precedence, and evidence-record requirements in this document.

## Next-Step Use

This contract is the required target shape for the next execution slices:

- Step 3 should align provider/profile/catalog data with this contract.
- Step 4 through Step 8 should populate or enforce more of `runtime_normalized_contract`.
- Step 9 through Step 12 should populate `validated_evidence`.
- Step 13 should surface stable portions of this contract in the app UI.
