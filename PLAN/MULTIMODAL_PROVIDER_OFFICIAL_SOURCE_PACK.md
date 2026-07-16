# Multimodal Provider Official Source Pack

Last updated: 2026-07-07

## Purpose

This source pack records the official documentation baseline for AstraBridge's
priority multimodal providers.

It exists so future agents can:

- refresh provider and model capability claims from primary sources
- distinguish official provider proof from repository seed assumptions
- know which source URLs matter for rollout decisions
- run later doc-sync work without reconstructing discovery logic from chat history

This source pack supports the multimodal work tracked by:

- `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`

## Scope

Priority providers in this source pack:

- `yunwu`
- `qwen`
- `kimi`
- `glm`
- `deepseek`
- `openai`

Covered capability categories:

- model lists and model overview
- vision and multimodal chat input
- image generation and image editing
- speech recognition
- speech synthesis
- streaming or protocol notes relevant to the four multimodal capability lanes
- reasoning and protocol-reference notes where they affect adapter design

## Source Selection Rules

1. Primary sources are provider-owned documentation, API reference, or official model overview pages.
2. Secondary sources may be retained only as implementation hints and must not be treated as proof of support.
3. If a provider's official docs do not expose a lane clearly, that lane should remain `unknown`, `unwired`, or `blocked` rather than assumed from ecosystem reputation.
4. Retrieval dates below reflect the current audit performed on 2026-07-07 Asia/Tokyo.

## Source Entry Schema

Each source entry records:

- `provider_id`
- `source_kind`
- `url`
- `retrieved_at`
- `capability_categories`
- `rollout_required`
- `stability_notes`
- `current_use`

Interpretation:

- `rollout_required: true` means later exposure decisions should not bypass this source category
- `current_use` explains why the page matters to AstraBridge today

## Primary Sources

### Yunwu

Yunwu is a gateway provider in this plan, not the protocol-reference provider. Its
source pack focuses on the Yunwu-owned API surface that AstraBridge already uses for
OpenAI-compatible image generation and edit flows.

| provider_id | source_kind | url | retrieved_at | capability_categories | rollout_required | stability_notes | current_use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `yunwu` | `official_provider_portal` | `https://yunwu.ai/` | `2026-07-07` | `provider_overview`, `gateway_scope` | `false` | Public provider portal; current crawl is JS-gated, so the page is useful as provider ownership proof but weak for field-level capability extraction. | Confirms Yunwu is a provider-owned gateway surface rather than a random third-party seed. |
| `yunwu` | `official_api_reference` | `https://yunwu.apifox.cn/api-328094105` | `2026-07-07` | `image.generate`, `image.edit`, `openai_compatible_image` | `true` | Apifox page indexed publicly. Current snippet shows `POST https://yunwu.ai/v1/images/generations`. | Primary current source for the existing AstraBridge `yunwu.image.generate.v1` lane. |
| `yunwu` | `official_api_reference` | `https://yunwu.apifox.cn/api-393805052` | `2026-07-07` | `image.edit`, `openai_compatible_image` | `true` | Apifox page indexed publicly. Current snippet shows `POST https://yunwu.ai/v1/images/edits`. | Primary current source for edit-style image generation compatibility and future family-level edit support. |
| `yunwu` | `official_api_reference` | `https://yunwu.apifox.cn/api-453199915` | `2026-07-07` | `image.generate`, `image.edit`, `provider_specific_reference` | `false` | Direct linked page from prior repository work; current crawl returns a JS shell with no text lines. Keep as provenance for existing repo references, but not as the sole proof source. | Preserves the exact page already referenced during repository work for later manual review. |

### Qwen / DashScope / Model Studio

Alibaba has sufficiently rich official docs for all four multimodal lanes and for
future `dashscope_image` family work.

| provider_id | source_kind | url | retrieved_at | capability_categories | rollout_required | stability_notes | current_use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `qwen` | `official_model_overview` | `https://help.aliyun.com/zh/model-studio/models` | `2026-07-07` | `model_list`, `modality_overview` | `true` | Central model-selection page covering text, image, audio, and video lines. | Baseline for model discovery and current model naming. |
| `qwen` | `official_release_log` | `https://help.aliyun.com/zh/model-studio/newly-released-models` | `2026-07-07` | `model_updates`, `snapshot_changes`, `deprecation_watch` | `true` | Frequently updated release page. Useful for tracking renamed or newly promoted multimodal snapshots. | Critical update feed for model churn and rollout drift. |
| `qwen` | `official_capability_guide` | `https://help.aliyun.com/zh/model-studio/vision` | `2026-07-07` | `vision.analyze`, `image_input`, `video_input`, `documented_limits`, `openai_compatible_protocol` | `true` | Official guide for image and video understanding. Current page explicitly includes OpenAI-compatible integration guidance. | Primary vision source for Qwen multimodal chat and model-level visual capability claims. |
| `qwen` | `official_capability_guide` | `https://help.aliyun.com/zh/model-studio/text-to-image` | `2026-07-07` | `image.generate`, `text_to_image`, `model_family_overview` | `true` | Official text-to-image entry page covering Wan, Qwen-Image, and z-image lines. | Primary family-level discovery source for Step 8 `dashscope_image` implementation. |
| `qwen` | `official_capability_guide` | `https://help.aliyun.com/zh/model-studio/image-model/` | `2026-07-07` | `image.generate`, `image.edit`, `model_selection`, `documented_limits` | `true` | Current recommendation and model-difference page for image generation and editing. | Useful for model-family selection and deciding which image models are worth wiring first. |
| `qwen` | `official_capability_guide` | `https://help.aliyun.com/zh/model-studio/qwen-image-edit-guide` | `2026-07-07` | `image.edit`, `multi_image_edit`, `documented_limits` | `true` | Specific edit guide for Qwen image editing behavior. | Important when deciding whether Qwen image edit can share the same family as Qwen image generate. |
| `qwen` | `official_api_reference` | `https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference` | `2026-07-07` | `speech.transcribe`, `openai_compatible_protocol`, `dashscope_protocol`, `model_level_access_modes` | `true` | Current page explicitly distinguishes which Qwen ASR models support OpenAI-compatible versus DashScope-only access. | Primary ASR source for request-shape and per-model protocol eligibility. |
| `qwen` | `official_capability_guide` | `https://help.aliyun.com/zh/model-studio/non-realtime-speech-recognition-user-guide` | `2026-07-07` | `speech.transcribe`, `documented_limits`, `async_transcription` | `true` | Official non-realtime ASR guide; current page documents file duration and size limits. | Required for limits and for distinguishing async ASR from current chat-style adapter behavior. |
| `qwen` | `official_capability_guide` | `https://help.aliyun.com/zh/model-studio/real-time-speech-recognition-user-guide` | `2026-07-07` | `speech.transcribe`, `streaming_asr`, `websocket_protocol` | `false` | Official realtime ASR guide using WebSocket. | Useful to decide when a new ASR family is required instead of metadata-only extension. |
| `qwen` | `official_api_reference` | `https://help.aliyun.com/zh/model-studio/qwen-tts-api` | `2026-07-07` | `speech.synthesize`, `tts_http`, `streaming_audio`, `voice_and_format_limits` | `true` | Official Qwen-TTS API reference. Current page documents language, voice, and format fields. | Primary TTS source for the current `qwen.tts.api.v1` lane. |
| `qwen` | `official_capability_guide` | `https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide` | `2026-07-07` | `speech.synthesize`, `streaming_audio`, `artifact_semantics` | `true` | Official user guide that distinguishes non-stream and stream outputs and URL-vs-PCM return semantics. | Important for family-level artifact persistence and streaming assembly semantics. |
| `qwen` | `official_api_reference` | `https://help.aliyun.com/zh/model-studio/qwen-tts-realtime-api-reference/` | `2026-07-07` | `speech.synthesize`, `realtime_tts`, `streaming_protocol` | `false` | Official realtime TTS reference for a different protocol class. | Marks a likely future new-family trigger rather than metadata-only extension of the current SSE family. |
| `qwen` | `official_limits_reference` | `https://help.aliyun.com/zh/model-studio/rate-limit` | `2026-07-07` | `rate_limits`, `rollout_operability` | `false` | Official per-account and per-model rate-limit guidance. | Useful for rollout automation and smoke pacing. |
| `qwen` | `official_error_reference` | `https://help.aliyun.com/zh/model-studio/error-code` | `2026-07-07` | `error_shapes`, `request_validation_failures` | `false` | Useful for stable error normalization. | Useful for turning provider-native failures into AstraBridge error categories. |

### Kimi / Moonshot

Kimi currently matters to this plan mainly through multimodal chat and visual input,
plus provider-specific thinking behavior.

| provider_id | source_kind | url | retrieved_at | capability_categories | rollout_required | stability_notes | current_use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `kimi` | `official_overview` | `https://platform.kimi.com/docs/overview` | `2026-07-07` | `provider_overview`, `multimodal_scope`, `tool_calling` | `true` | Official top-level docs page. | Baseline entry point for provider ownership and platform scope. |
| `kimi` | `official_api_overview` | `https://platform.kimi.com/docs/api/overview` | `2026-07-07` | `openai_compatible_protocol`, `chat_completions`, `files`, `models` | `true` | Official API overview and protocol baseline. | Primary protocol source for current Kimi adapter behavior. |
| `kimi` | `official_model_list` | `https://platform.kimi.com/docs/models` | `2026-07-07` | `model_list`, `multimodal_models`, `context_window` | `true` | Current model list explicitly includes multimodal models such as `kimi-k2.6` and `kimi-k2.7-code`. | Baseline for model discovery and model-family naming. |
| `kimi` | `official_capability_guide` | `https://platform.kimi.com/docs/guide/use-kimi-vision-model` | `2026-07-07` | `vision.analyze`, `image_input`, `video_input`, `parameter_constraints` | `true` | Official visual-model guide. Current page documents `thinking`, `temperature`, `top_p`, and `n` constraints for Kimi multimodal models. | Primary source for Kimi visual lane support and request-shape constraints. |
| `kimi` | `official_capability_guide` | `https://platform.kimi.com/docs/guide/use-kimi-k2-thinking-model` | `2026-07-07` | `reasoning`, `thinking_parameter`, `preserved_thinking` | `false` | Provider-specific reasoning behavior page. | Important for protocol normalization and future reasoning policy logic. |
| `kimi` | `official_model_quickstart` | `https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart` | `2026-07-07` | `model_quickstart`, `multimodal_model_entry` | `false` | Good model-specific anchor page when exact K2.6 behavior matters. | Supplemental source for current default visual model assumptions. |

### GLM / BigModel

GLM is broader than current wiring, but its official docs are rich enough to support
future expansion and to keep current protocol-reference assumptions honest.

| provider_id | source_kind | url | retrieved_at | capability_categories | rollout_required | stability_notes | current_use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `glm` | `official_platform_intro` | `https://docs.bigmodel.cn/cn/guide/start/introduction` | `2026-07-07` | `provider_overview`, `openai_compatible_sdk`, `platform_scope` | `true` | Official platform introduction. | Baseline provider overview and compatibility claim source. |
| `glm` | `official_model_overview` | `https://docs.bigmodel.cn/cn/guide/start/model-overview` | `2026-07-07` | `model_list`, `vision`, `image.generate`, `speech.synthesize`, `speech.transcribe` | `true` | Official model overview page covering major model families. | Baseline for discovery and category coverage. |
| `glm` | `official_capability_guide` | `https://docs.bigmodel.cn/cn/guide/models/vlm/glm-4.6v` | `2026-07-07` | `vision.analyze`, `tool_calling`, `documented_limits` | `true` | Official visual understanding page with model-family detail. | Primary GLM vision source for future route-eligibility correctness. |
| `glm` | `official_api_reference` | `https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E5%9B%BE%E5%83%8F%E7%94%9F%E6%88%90` | `2026-07-07` | `image.generate`, `http_endpoint`, `artifact_semantics` | `true` | Official image-generation API reference. | Primary image generation endpoint source if GLM image support enters scope later. |
| `glm` | `official_capability_guide` | `https://docs.bigmodel.cn/cn/guide/models/image-generation/glm-image` | `2026-07-07` | `image.generate`, `input_output_modalities`, `documented_limits` | `true` | Official GLM-Image guide with size and output notes. | Useful for family design and documented limits. |
| `glm` | `official_api_reference` | `https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E8%AF%AD%E9%9F%B3%E8%BD%AC%E6%96%87%E6%9C%AC` | `2026-07-07` | `speech.transcribe`, `http_endpoint`, `multipart_upload`, `stream_flag` | `true` | Official speech-to-text API reference. | Primary GLM ASR endpoint source. |
| `glm` | `official_capability_guide` | `https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-asr` | `2026-07-07` | `speech.transcribe`, `input_output_modalities`, `recommended_scenarios` | `true` | Official ASR guide. | Useful for documented modality and scenario support. |
| `glm` | `official_api_reference` | `https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E6%96%87%E6%9C%AC%E8%BD%AC%E8%AF%AD%E9%9F%B3` | `2026-07-07` | `speech.synthesize`, `http_endpoint`, `voice_selection`, `format_selection` | `true` | Official text-to-speech API reference. | Primary GLM TTS endpoint source. |
| `glm` | `official_capability_guide` | `https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-tts` | `2026-07-07` | `speech.synthesize`, `streaming_support`, `input_output_modalities` | `true` | Official TTS guide explicitly mentions non-stream and stream support. | Useful for deciding whether GLM TTS can share a family with other providers. |

### DeepSeek

DeepSeek is in the current priority set because its provider normalization and
reasoning behavior affect shared compatibility logic. In this audit, official public
docs clearly cover chat, reasoning, model listing, and reasoning-effort behavior,
but they do not provide a public image-generation, vision, ASR, or TTS lane for the
current multimodal scope.

| provider_id | source_kind | url | retrieved_at | capability_categories | rollout_required | stability_notes | current_use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `deepseek` | `official_api_overview` | `https://api-docs.deepseek.com/` | `2026-07-07` | `provider_overview`, `openai_compatible_protocol`, `chat_completions`, `streaming` | `true` | Official docs landing page. | Baseline protocol-reference source for DeepSeek. |
| `deepseek` | `official_model_list_api` | `https://api-docs.deepseek.com/api/list-models` | `2026-07-07` | `model_list`, `availability` | `true` | Official `/models` reference. | Primary model listing source. |
| `deepseek` | `official_api_reference` | `https://api-docs.deepseek.com/api/create-chat-completion` | `2026-07-07` | `chat_completions`, `reasoning_effort`, `thinking_mode`, `streaming` | `true` | Current page documents `reasoning_effort` values and thinking controls. | Primary source for current reasoning normalization and compatibility mapping. |
| `deepseek` | `official_reasoning_guide` | `https://api-docs.deepseek.com/guides/reasoning_model` | `2026-07-07` | `reasoning`, `cot_visibility` | `false` | Official reasoning model guide. | Useful for shared reasoning-content preservation logic. |
| `deepseek` | `official_thinking_guide` | `https://api-docs.deepseek.com/guides/thinking_mode` | `2026-07-07` | `reasoning`, `tool_calls`, `reasoning_content_replay` | `false` | Official guide for tool calls during thinking mode. | Important for preserving reasoning content across tool turns. |
| `deepseek` | `official_pricing_page` | `https://api-docs.deepseek.com/quick_start/pricing` | `2026-07-07` | `model_aliases`, `deprecation_watch` | `false` | Useful for alias and deprecation tracking. | Useful when model aliases or deprecations affect catalog updates. |

DeepSeek current multimodal audit note:

- No official public image-generation, image-understanding, speech-to-text, or text-to-speech API pages were identified in this audit under `api-docs.deepseek.com` for the current four-lane multimodal scope.
- Therefore, DeepSeek should remain a shared protocol and reasoning-compatibility provider inside this slice, not a positive multimodal exposure source, unless later official docs add those lanes.

### OpenAI

OpenAI remains a protocol-reference provider in this plan unless later live testing is
explicitly authorized. Its official docs still matter because many other providers in
this repository emulate or partially emulate OpenAI protocol surfaces.

| provider_id | source_kind | url | retrieved_at | capability_categories | rollout_required | stability_notes | current_use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `openai` | `official_docs_overview` | `https://developers.openai.com/api/docs` | `2026-07-07` | `provider_overview`, `responses_api`, `images`, `audio`, `reasoning` | `true` | Official docs landing page. | Baseline provider-owned reference for current protocol expectations. |
| `openai` | `official_model_overview` | `https://developers.openai.com/api/docs/models` | `2026-07-07` | `model_list`, `context_window`, `reasoning_levels`, `tooling_surface` | `true` | Central model overview page. | Baseline for protocol-reference model capability assumptions. |
| `openai` | `official_capability_guide` | `https://developers.openai.com/api/docs/guides/images-vision` | `2026-07-07` | `vision.analyze`, `image.generate`, `image.edit`, `multimodal_scope` | `true` | Official combined images and vision guide. | High-level protocol reference for image input and image output behavior. |
| `openai` | `official_capability_guide` | `https://developers.openai.com/api/docs/guides/image-generation` | `2026-07-07` | `image.generate`, `image.edit`, `image_api_options` | `true` | Dedicated image generation guide. | Primary image-generation reference for OpenAI-compatible family design. |
| `openai` | `official_capability_guide` | `https://developers.openai.com/api/docs/guides/audio` | `2026-07-07` | `audio_overview`, `streaming`, `speech_to_text`, `text_to_speech` | `true` | Top-level audio guide. | High-level audio capability taxonomy reference. |
| `openai` | `official_capability_guide` | `https://developers.openai.com/api/docs/guides/speech-to-text` | `2026-07-07` | `speech.transcribe`, `transcriptions`, `translations`, `model_list` | `true` | Dedicated speech-to-text guide. | Primary ASR reference for OpenAI protocol assumptions. |
| `openai` | `official_capability_guide` | `https://developers.openai.com/api/docs/guides/text-to-speech` | `2026-07-07` | `speech.synthesize`, `voices`, `streaming_audio` | `true` | Dedicated text-to-speech guide. | Primary TTS reference for OpenAI protocol assumptions. |
| `openai` | `official_reasoning_guide` | `https://developers.openai.com/api/docs/guides/reasoning` | `2026-07-07` | `reasoning`, `reasoning_effort`, `reasoning_tokens` | `false` | Official reasoning guide. | Important for reasoning-effort normalization and protocol-reference behavior. |
| `openai` | `official_api_reference` | `https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create/` | `2026-07-07` | `speech.synthesize`, `stream_events`, `endpoint_shape` | `false` | Endpoint-level reference for speech creation. | Useful when family design needs endpoint-level details instead of high-level guide summaries. |

## Secondary Or Supplemental Sources

These sources are useful but must not replace the primary rows above when deciding
whether AstraBridge may expose a lane.

| provider_id | url | retrieved_at | why_secondary |
| --- | --- | --- | --- |
| `qwen` | `https://help.aliyun.com/zh/model-studio/model-pricing` | `2026-07-07` | Pricing page is useful for rate and deprecation monitoring, but not a primary capability proof source. |
| `qwen` | `https://help.aliyun.com/zh/model-studio/model-depreciation` | `2026-07-07` | Useful for lifecycle tracking, not for lane capability proof. |
| `kimi` | `https://platform.kimi.com/docs/guide/use-kimi-k2-thinking-model` | `2026-07-07` | Important for reasoning normalization, but not enough by itself to prove multimodal lane support. |
| `glm` | `https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-realtime` | `2026-07-07` | Realtime audio-video page is valuable for future family design but outside the current four-lane primary wiring target. |
| `glm` | `https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-4-voice` | `2026-07-07` | End-to-end voice model may matter later, but it is not the current primary TTS or ASR adapter target. |
| `deepseek` | `https://api-docs.deepseek.com/news/news260424` | `2026-07-07` | Release notes are useful for churn tracking, not as primary multimodal support proof. |
| `yunwu` | `https://yunwu.ai/` | `2026-07-07` | Provider portal confirms ownership but is JS-only in current crawl and weak for parameter extraction. |

## Provider-Specific Rollout Notes

### Yunwu

- Treat Yunwu as a gateway provider with provider-owned API reference pages.
- Current official evidence is strongest for image generation and image edit only.
- Do not generalize Yunwu multimodal breadth from gateway branding alone.

### Qwen

- Qwen has enough official coverage to support model-family sync, adapter-family design, and request-shape validation for image, vision, ASR, and TTS.
- Realtime ASR and realtime TTS docs indicate protocol divergence; those should not be assumed to fit the current chat-ASR or SSE-TTS families without separate review.

### Kimi

- Kimi current official evidence in this slice is strongest for multimodal chat and visual input.
- Reasoning and temperature constraints are provider-specific and should stay below the capability layer.
- No separate official Kimi image-generation or TTS/ASR source was identified in this audit for the current four-lane scope.

### GLM

- GLM exposes official docs for vision, image generation, ASR, and TTS, so it is a meaningful future expansion candidate.
- The presence of these docs must still be separated from AstraBridge wiring state; current repo scope does not automatically make these lanes exposed.

### DeepSeek

- DeepSeek official docs currently justify protocol and reasoning compatibility work, not positive multimodal lane exposure.
- If a future audit finds official image or audio lanes, they must be added explicitly rather than inferred from OpenAI compatibility claims.

### OpenAI

- OpenAI remains protocol-reference only in the current repository scope unless later live testing is explicitly authorized.
- Its docs are still required because several adapter families in AstraBridge intentionally track OpenAI-compatible request and response shapes.

## Minimal Source Set Required For Later Doc-Sync Automation

A later doc-sync skill can perform useful multimodal reconciliation if it consumes at
least these URLs:

- `yunwu`: `api-328094105`, `api-393805052`
- `qwen`: `models`, `newly-released-models`, `vision`, `text-to-image`, `qwen-asr-api-reference`, `qwen-tts-api`
- `kimi`: `overview`, `api/overview`, `models`, `guide/use-kimi-vision-model`
- `glm`: `model-overview`, `glm-4.6v`, image-generation API reference, speech-to-text API reference, text-to-speech API reference
- `deepseek`: docs landing page, `list-models`, `create-chat-completion`, `guides/reasoning_model`
- `openai`: docs landing page, `models`, `guides/images-vision`, `guides/image-generation`, `guides/audio`, `guides/speech-to-text`, `guides/text-to-speech`

## Acceptance Use

This artifact is sufficient for Step 7 of the multimodal handoff plan when:

- it exists on disk and is secret-free
- each source entry has `provider_id`, `url`, `retrieved_at`, and `capability_categories`
- primary sources are clearly separated from secondary or supplemental sources
- the pack is concrete enough that a future doc-sync skill can reuse it without rediscovering provider-owned documentation
