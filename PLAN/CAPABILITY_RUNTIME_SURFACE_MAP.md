# Capability Runtime Surface Map

Last updated: 2026-06-25

## Goal

This note records how the capability runtime is exposed today, how it relates to legacy tool surfaces, and which MCP entry points are expected to remain stable.

## Capability IDs

| Capability ID | Lane Type | Default Route Behavior | Current Adapters |
| --- | --- | --- | --- |
| `image.generate` | `model_backed` | `auto` or `pinned` via capability routes | `yunwu.image.generate.v1` |
| `vision.analyze` | `model_backed` | `auto` or `pinned` via capability routes | `qwen.vision.chat.v1`, `kimi.vision.chat.v1` |
| `speech.transcribe` | `model_backed` | `auto` or `pinned` via capability routes | `qwen.asr.chat.v1` |
| `speech.synthesize` | `model_backed` | `auto` or `pinned` via capability routes | `qwen.tts.omni.v1` |
| `web.search` | `web_standalone` | never enters model-backed router | standalone web lane |

## MCP Surfaces

### Legacy MCP surfaces kept for compatibility

| Surface | Server Name | Tool Names |
| --- | --- | --- |
| Built-in web lane | `astrabridge_web` | `astrabridge_web_search_batch`, `astrabridge_web_research_brief`, `astrabridge_web_search`, `astrabridge_web_fetch` |
| Yunwu image lane | `yunwu_image` | `yunwu_image_generate`, `yunwu_image_transparent_asset`, `yunwu_image_edit` |

### Capability MCP surface

| Surface | Server Name | Tool Names |
| --- | --- | --- |
| Capability runtime | `astrabridge_capabilities` | `astrabridge_capability_routes`, `astrabridge_capability_image_generate`, `astrabridge_capability_vision_analyze`, `astrabridge_capability_speech_transcribe`, `astrabridge_capability_speech_synthesize` |

## Routing Rules

- `astrabridge_capability_routes` is the inspection surface for current route mode, resolved candidate, and fallback candidates.
- The desktop Capabilities tab is the normal user-facing route management surface.
- The sidecar read model is `/api/runtime/capability-management`; route writes go through `/api/runtime/capability-routes/save`.
- Model-backed capability tools honor explicit `provider_id` / `model` overrides when provided.
- Otherwise the tool uses the saved capability route:
  - `auto`: choose the registry-preferred candidate
  - `pinned`: require the pinned provider/model to still be eligible
- If no candidate is eligible, the runtime returns `no_capability_candidate`.

## Compatibility Rules

- `web.search` remains a standalone web lane. Search result interpretation belongs to the calling LLM, not the search service.
- Legacy Yunwu image tools remain supported; the capability image surface wraps the same underlying image service rather than replacing it.
- Capability routing does not flatten provider protocol differences. Adapter-specific request/response handling stays inside the adapter layer.
- Existing image generation and web search interfaces stay visible; capability routing is an additional management/runtime layer, not a replacement for those entry points.

## Desktop Management Surface

The current desktop Capabilities tab exposes:

- capability list with lane type, transport mode, availability, resolved candidate, adapters, smoke status, and artifact policy
- auto/pinned route controls for model-backed capabilities
- candidate details with provider/model and modality hints
- redacted provider credential states only: configured, missing, env ref, session required, or disabled
- paid-provider quota warnings and local large-artifact retention warnings
- deterministic dry-run smoke controls for model-backed capabilities
- recent artifact previews from workspace-local capability artifacts
- `astrabridge_capabilities` preset health, runtime visibility, configured/missing tool count, and idempotent install/reapply

Automation handoff is controlled from the Automations tab. Automation create/edit forms use preset chips and keep the stored runtime contract as `runtime.mcp_preset_ids`, including `astrabridge_capabilities`.

## Smoke-Test Policy

- Dry-run smoke is the default UI path and must not call providers or require keys.
- Provider-backed smoke must be explicit and user-approved.
- Smoke evidence may include sanitized request metadata, sanitized response metadata, route status, and artifact references.
- Smoke evidence must not persist raw keys, authorization headers, cookies, bearer tokens, or raw provider secrets.
- Step 10 release evidence should preserve deterministic no-key smoke output under a validation or `PRIVATE/demo-runs/**` path.

## Artifact Paths

- `speech.transcribe` artifacts: `.astrabridge/capabilities/speech_transcribe/`
- `speech.synthesize` artifacts: `.astrabridge/capabilities/speech_synthesize/`
- `vision.analyze` artifacts: `.astrabridge/capabilities/vision_analyze/`
- `image.generate` artifacts: existing Yunwu asset persistence plus returned manifest references
- Capability artifact API: `/api/runtime/capability-artifacts`
- Desktop previews should render only safe summaries, image/audio references, timestamps, provider/model labels, and relative paths.

## Operational Notes

- Install or reapply the capability MCP preset through `/api/router/mcp/preset/astrabridge-capabilities`, the desktop MCP settings panel, or the desktop Capabilities tab.
- The capability MCP server reads only environment-based provider credentials:
  - `YUNWU_API_KEY`
  - `DASHSCOPE_API_KEY`
  - `MOONSHOT_API_KEY`
- Workspace-root discovery still uses the standard AstraBridge workspace env vars so persisted artifacts stay inside project-owned state.
- Desktop credential UX must remain redacted. Do not read Desktop key files or plaintext secret sources unless the user explicitly authorizes that exact action.
