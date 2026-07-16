# Multimodal Capability Scope And Invariants

Last updated: 2026-07-06

## Purpose

This note freezes the execution scope and non-negotiable architectural invariants for the multimodal capability adaptation and update work tracked by:

- `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`

It exists to stop later agents from drifting into ad hoc provider patching, catalog-only model additions, or implicit provider-wide capability inheritance.

## In-Scope Capability Lanes

The work in this plan is limited to these capability-facing lanes:

- `image.generate`
- `vision.analyze`
- `speech.transcribe`
- `speech.synthesize`

Supporting surfaces that are in scope only as dependencies of those lanes:

- capability registry and route eligibility
- generated and effective model catalog metadata
- runtime capability exposure and desktop capability-management surfaces
- capability MCP exposure for the four multimodal lanes
- dry-run and live-smoke verification paths
- agent skills and scripts used to discover, reconcile, validate, and safely roll out multimodal updates

The following remains explicitly in scope as a product boundary:

- `web.search` stays a standalone web lane and is not merged into model-backed multimodal routing.

## Priority Provider Set

The current priority providers for this slice are:

- `yunwu`
- `qwen`
- `kimi`
- `glm`
- `deepseek`
- `openai` documentation and protocol assumptions only, unless the user later authorizes official-provider live testing

Provider focus inside this slice:

- `yunwu`: OpenAI-compatible image-generation and image-edit compatibility surfaces already exposed by AstraBridge
- `qwen`: vision, ASR, TTS, and future DashScope image-generation adapter family
- `kimi`: vision and multimodal-chat compatibility
- `glm`: model-level capability declaration and route-eligibility correctness
- `deepseek`: provider/profile normalization interactions that affect shared capability and reasoning metadata
- `openai`: protocol and contract reference only, not current live-verification scope

## Deferred Or Out-Of-Scope Work

The following are deferred unless the user later redirects scope:

- official OpenAI direct live verification
- video-specific runtime lanes, including dedicated `video_input` or `video_output` adapters
- merging standalone web search into the model-backed capability router
- provider expansion beyond the priority set above
- broad UI redesign unrelated to truthful capability exposure
- catalog-only onboarding of new multimodal models without corresponding adapter-family and exposure-gate work

## Architectural Invariants

These rules are mandatory for all later steps in the multimodal plan.

### 1. Capability-First Runtime Boundary

Calling surfaces must target stable capability ids rather than provider-specific model contracts.

The supported multimodal capability ids remain:

- `image.generate`
- `vision.analyze`
- `speech.transcribe`
- `speech.synthesize`

Provider-specific request and response shape differences must stay below the capability layer.

### 2. Adapter-Layer Isolation

Provider and protocol quirks must live in adapter families or transport-specific code, not in the capability contract itself.

Examples of adapter-only concerns:

- image request shape differences across OpenAI-compatible and DashScope image APIs
- TTS stream assembly and event parsing differences
- multimodal chat content-shape differences
- provider-native reasoning or thinking control names
- provider-native artifact and usage payload shapes

### 3. No Catalog-Only Promotion To Runnable Support

A model must not be exposed as runnable only because:

- it appears in official docs
- it exists in generated catalog metadata
- it exists in provider default metadata
- it is in the same provider family as a verified model

Catalog presence is evidence of discovery, not proof of runtime support.

### 4. Model-Level Evidence Overrides Provider-Wide Optimism

Provider-wide defaults may seed metadata, but they must not silently promote unsupported model lanes into runnable routes.

When model-level evidence conflicts with provider-level defaults:

- model-level documented support wins for declarations
- model-level adapter wiring wins for runtime eligibility
- model-level validation evidence wins for exposure

Unknown is preferred over optimistic inheritance.

### 5. Stable Exposure-State Vocabulary

Multimodal work in this slice must distinguish four support states:

- `documented`: official docs or trusted source registry indicate the model or lane exists
- `wired`: AstraBridge has a concrete adapter path and route-level representation for the lane
- `verified`: current dry-run or live evidence proves the lane behaves as expected at the required layer
- `exposed`: the lane is allowed to appear as user-selectable or auto-routable runtime support

Interpretation rule:

- `documented` without `wired` means discovery only
- `wired` without `verified` means implementation exists but is not yet safe for exposure
- `verified` without `exposed` is allowed when rollout is intentionally gated
- `exposed` requires the lane to be at least both `wired` and sufficiently `verified` for its rollout class

## Runnable-Support Fact Boundary

Later agents must keep these fact layers separate:

### `documented`

Source-backed declaration that a provider or model claims a lane exists.

Typical evidence:

- official provider docs
- maintained source registry
- trusted model-list fetch output

### `wired`

AstraBridge has code paths that can actually build, send, parse, and persist the lane for a specific provider family or model family.

Typical evidence:

- capability adapter contracts
- request builders and response parsers
- validator logic
- artifact persistence logic
- route resolution entries

### `verified`

Current evidence proves the wired path works or is correctly blocked at the required layer.

Typical evidence:

- dry-run route and contract reports
- static request-shape validation
- live smoke records
- preserved workflow evidence

### `exposed`

The lane is permitted to appear in runtime selection, auto-routing, or user-facing capability-management surfaces.

Typical evidence:

- explicit exposure-gate logic
- route-management output
- desktop or MCP surfaces that reflect the gated support state

## Step-1 Summary Of Current Starting Point

Current repository facts that later agents should treat as the baseline for this slice:

- `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` already fixes the capability-runtime direction around the four multimodal lanes plus a standalone web lane.
- `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md` records that the current adapters are:
  - `yunwu.image.generate.v1`
  - `qwen.vision.chat.v1`
  - `kimi.vision.chat.v1`
  - `qwen.asr.chat.v1`
  - a stale `qwen.tts.omni.v1` label in the surface map that no longer matches the current adapter contract and should be reconciled later
- `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md` already defines a broader provider/model evidence vocabulary that later multimodal work should reuse rather than replace.
- The current repo does not yet have a real DashScope image-generation adapter family, so official Alibaba image models must not be treated as runnable support until such wiring exists and is verified.

## Acceptance Use

This artifact is sufficient for Step 1 of the multimodal handoff plan when:

- a later agent can see the in-scope capabilities
- a later agent can see the priority providers
- deferred work is explicit
- architectural invariants are concrete enough to block catalog-only or provider-wide optimistic patches
- the distinction between `documented`, `wired`, `verified`, and `exposed` is unambiguous
