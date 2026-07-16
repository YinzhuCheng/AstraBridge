# Multimodal Adapter Family Contract

Last updated: 2026-07-06

## Purpose

This document defines the adapter-family layer for AstraBridge's multimodal runtime.

The goal is to stop treating every provider model as a one-off integration point. A
model should reuse an existing adapter family whenever its transport, request shape,
artifact semantics, and failure modes match that family closely enough.

This contract sits between:

- capability-facing contracts in `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`
- model and provider matrix rows in `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`
- runtime dispatch in `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`

## Design Rules

1. Capability-level schemas stay stable even when provider-native request fields drift.
2. Adapter families own provider-protocol details, not the capability layer.
3. A new model should require metadata only when it fits an existing family contract without semantic drift.
4. A new family is required when the request envelope, response assembly, artifact semantics, or verification bar materially differ.
5. Family contracts must be secret-free, testable in dry-run form, and compatible with matrix exposure gating.
6. Family contracts must preserve raw evidence artifacts with secrets redacted or omitted.

## Current Concrete Adapter Evidence

Current concrete adapter ids and runtime wiring show five implementation islands:

- `yunwu.image.generate.v1`
- `qwen.vision.chat.v1`
- `kimi.vision.chat.v1`
- `qwen.asr.chat.v1`
- `qwen.tts.api.v1`

Current runtime dispatch is still hardwired by capability and concrete class:

- `YunwuImageGenerateAdapter`
- `QwenSpeechTranscribeAdapter`
- `QwenSpeechSynthesizeAdapter`
- `QwenVisionAnalyzeAdapter`
- `KimiVisionAnalyzeAdapter`

That is sufficient for single-provider paths, but it is still below the family-level abstraction needed for update-friendly multimodal support.

## Required Family Interface

Every multimodal adapter family must provide these interfaces, whether through one
class or a small set of cooperating components.

### 1. Route Projection

Responsibilities:

- declare supported capabilities
- declare supported input and output modalities
- declare abstract request-shape requirements
- declare model-level eligibility constraints
- emit route-authoritative facts consumable by the multimodal matrix

Minimum outputs:

- `adapter_family`
- `supported_capability_ids`
- `effective_input_modalities`
- `effective_output_modalities`
- `required_request_shapes`
- `request_constraints`
- `supported_models` or model-selection rules
- `verification_gate_class`

### 2. Request Builder

Responsibilities:

- accept the capability-stable payload
- validate required abstract fields
- translate to provider-native request body or streaming envelope
- normalize provider base URLs and path conventions
- reject unsupported parameter combinations early

Required behavior:

- must fail before network I/O when abstract request-shape requirements are not met
- must not leak secrets into persisted artifacts
- must preserve enough normalized request data for dry-run evidence

### 3. Response Parser

Responsibilities:

- normalize provider-native responses into capability-stable result fields
- preserve model id, provider id, finish reason, usage, and normalized annotations
- handle family-specific streaming assembly rules where needed

Required behavior:

- must define whether the family consumes plain JSON, SSE, multipart, or deferred artifact polling
- must distinguish visible answer content from reasoning or metadata content
- must provide deterministic normalization notes for known family quirks

### 4. Artifact Persistence

Responsibilities:

- write secret-free request, response, summary, and media artifacts
- persist artifact manifests in the existing `.astrabridge/capabilities/**` layout or a successor explicitly recorded in the matrix
- preserve enough evidence to replay verification without preserving secrets

Required outputs:

- `artifact_refs`
- `artifact_dir`
- family-appropriate summary fields such as transcript path, audio path, image manifest path, or text path

### 5. Validator

Responsibilities:

- enforce family-specific request-shape constraints before live calls
- validate model eligibility inside the family boundary
- validate media modality constraints such as image count, audio-only content, inline-vs-remote URL policy, and stream mode expectations

Required behavior:

- must produce stable, secret-free failure messages
- must be callable in dry-run and unit-test contexts
- must expose negative cases clearly enough for matrix downgrade decisions

### 6. Error Normalizer

Responsibilities:

- classify provider failures into stable AstraBridge-facing categories
- preserve raw diagnostics in artifacts where allowed
- separate unsupported-model, malformed-request, auth, rate-limit, timeout, and provider-internal failures

Required outputs:

- stable error category
- provider error summary
- route or matrix downgrade hint when the failure should affect exposure

## Family Boundary Test

A provider or model belongs to an existing family only if all of these stay true:

1. The capability-facing payload shape remains the same.
2. The provider-native request envelope is the same class of protocol.
3. The response can be normalized into the same capability result schema without adding family-specific capability fields.
4. Artifact persistence semantics remain the same class of outputs.
5. Validation rules differ only by data values or allowlists, not by validation model.
6. Exposure and verification gates stay in the same class.

If any of those fail, the lane needs either:

- a new family, or
- a documented subfamily with its own tests and matrix semantics

## Initial Adapter Families

These are the family boundaries AstraBridge should use for the current priority scope.

### `openai_compatible_image`

Capabilities:

- `image.generate`

Protocol shape:

- image generation or image edit APIs returning image artifacts plus manifest-style metadata

Required family behavior:

- support prompt-only generation
- optionally support edit-style generation when the provider protocol remains compatible
- normalize image artifact manifests and revised prompts
- persist generated assets and manifest summaries

Current mapping:

- provider `yunwu`
- current adapter id `yunwu.image.generate.v1`

Near-term extension target:

- any future OpenAI-compatible image provider whose request and artifact semantics match the same family

Metadata-only admission rule:

- a new model may reuse this family when it still behaves like the current image generation path and does not require a different async job lifecycle, artifact polling model, or editing contract

### `chat_multimodal_vision`

Capabilities:

- `vision.analyze`

Protocol shape:

- chat-completions request with image content parts plus trailing text prompt

Required family behavior:

- normalize image inputs into inline data URLs or approved remote URLs
- enforce model allowlists and image-side constraints at family level
- normalize visible answer text, optional reasoning annotations, usage, and finish reason
- persist request, response, and extracted text artifacts

Current mapping:

- provider `qwen`, adapter id `qwen.vision.chat.v1`
- provider `kimi`, adapter id `kimi.vision.chat.v1`

Priority protocol-reference mapping:

- provider `glm` for rows that remain compatible with chat-style multimodal vision
- provider `deepseek` only if later official docs expose a matching multimodal chat lane
- provider `openai` as protocol-reference rows where the chat-style image-input lane matches this family

Metadata-only admission rule:

- a new model may reuse this family when the only differences are supported model ids, image URL policy, detail-field support, or documented size constraints

New-family trigger:

- provider requires file-upload handles, async image preprocessing jobs, or non-chat response assembly

### `dashscope_chat_asr`

Capabilities:

- `speech.transcribe`

Protocol shape:

- chat-completions request whose user content contains audio parts only

Required family behavior:

- normalize local files or inline audio into audio content parts
- enforce audio-only content semantics
- preserve language hints and transcription annotations
- persist request, response, transcript, and summary artifacts

Current mapping:

- provider `qwen`
- current adapter id `qwen.asr.chat.v1`

Priority protocol-reference mapping:

- future Alibaba ASR variants that still use the same chat-style audio request semantics

Metadata-only admission rule:

- a new model may reuse this family when the protocol remains chat-completions with audio-only content and the result still normalizes into the same transcript schema

New-family trigger:

- provider introduces batch transcription jobs, streaming token events, diarization-first payloads, or non-chat speech APIs with different artifact semantics

### `dashscope_sse_tts`

Capabilities:

- `speech.synthesize`

Protocol shape:

- DashScope multimodal-generation SSE stream yielding text and audio snapshots or deltas

Required family behavior:

- normalize text, audio bytes, audio URLs, finish reason, and usage from SSE events
- support family-level model fallback between ordinary TTS and instruct TTS variants
- persist request, SSE transcript, text transcript, audio artifact, and summary records

Current mapping:

- provider `qwen`
- current adapter id `qwen.tts.api.v1`

Priority protocol-reference mapping:

- priority CosyVoice or Qwen TTS models only if official docs confirm the same SSE contract and output assembly rules

Metadata-only admission rule:

- a new model may reuse this family when model id, voice catalog, and supported formats vary but SSE event structure and audio assembly remain compatible

New-family trigger:

- provider requires websocket streams, polling jobs, binary chunk framing, or a different audio assembly contract

## Priority Provider-To-Family Mapping

The current priority providers can be mapped without ambiguity as follows.

| Provider | Capability lane | Family | Current state |
| --- | --- | --- | --- |
| `yunwu` | `image.generate` | `openai_compatible_image` | wired via `yunwu.image.generate.v1` |
| `qwen` | `vision.analyze` | `chat_multimodal_vision` | wired via `qwen.vision.chat.v1` |
| `qwen` | `speech.transcribe` | `dashscope_chat_asr` | wired via `qwen.asr.chat.v1` |
| `qwen` | `speech.synthesize` | `dashscope_sse_tts` | wired via `qwen.tts.api.v1` |
| `qwen` | `image.generate` | `dashscope_image` | documented target, not wired yet |
| `kimi` | `vision.analyze` | `chat_multimodal_vision` | wired via `kimi.vision.chat.v1` |
| `glm` | `vision.analyze` | `chat_multimodal_vision` | protocol-reference candidate, currently unwired |
| `deepseek` | multimodal lanes | family unresolved pending official multimodal docs and runtime scope | currently unknown or blocked |
| `openai` | protocol-reference multimodal rows | family chosen per lane, but official live verification remains out of current scope | docs-backed only |

Notes:

- `dashscope_image` is intentionally named here even though Step 8 has not implemented it yet. This keeps the family map stable for the upcoming adapter work.
- `openai` remains a protocol-reference provider in the current repository scope, not an authorized official live-smoke target.

## Metadata-Only Versus New-Family Decision Rule

A new provider model should be admitted through metadata only when all of the following are true:

1. It uses an existing family protocol.
2. It requires no new capability-level fields.
3. It reuses the same persistence model.
4. It only changes allowlists, documented limits, voice catalogs, or default parameters.
5. Existing family tests can cover it with added fixtures rather than architectural changes.

A new family is required when any of the following are true:

- the provider uses a different network protocol class
- response assembly changes from snapshot to delta, or from sync response to async job lifecycle
- media input rules change in a way that requires a new validator model
- artifact persistence changes from a simple local asset set to a job-result retrieval flow
- exposure gating must use a different verification class

## Runtime Refactor Target

Later implementation steps should move `capabilities/runtime.py` from concrete adapter attributes to family-aware registration.

Target shape:

1. capability selects candidate family
2. family validates model eligibility and request shape
3. family resolves concrete provider adapter instance
4. runtime executes and persists family-normalized artifacts

This means new model onboarding should usually touch:

- matrix metadata
- provider catalog metadata
- family allowlists or constraints
- dry-run and smoke evidence

It should not usually require a new runtime dispatch branch.

## Acceptance Use

This artifact is sufficient for Step 5 of the multimodal handoff plan when:

- it defines adapter-family boundaries for the current multimodal scope
- it names the required family interfaces
- it maps the current priority providers and concrete adapters to families without ambiguity
- it states when a new model is metadata-only versus when a new family is required
