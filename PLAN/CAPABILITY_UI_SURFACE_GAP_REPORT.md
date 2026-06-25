# Capability UI Surface Gap Report

Last updated: 2026-06-25

## Purpose

This report completes step 1 of `PLAN/CAPABILITY_UI_MANAGEMENT_IMPLEMENTATION_PLAN.md`.

It inventories the current desktop and sidecar surfaces for MCP-style capabilities, identifies the user workflow gaps, records backend/API gaps, and proposes the UI navigation shape for the remaining implementation steps.

## Current Entry Points

### Desktop UI

- `apps/astrabridge-desktop/src/App.tsx`
  - Setup tabs include `capabilities`, `mcp`, and `automations`.
  - The `capabilities` tab renders a route list with capability id, lane type, resolved candidate/status, route mode, pinned candidate selection, save action, and inline route error.
  - The `mcp` tab exposes an `Install capability runtime` action through the AstraBridge capabilities preset.
  - The main runtime panel has a `Capability health` section, but it is not a capability management console.

- `apps/astrabridge-desktop/src/api.ts`
  - Exposes `capabilityRoutes()` for `/api/runtime/capability-routes`.
  - Exposes `saveCapabilityRoute()` for `/api/runtime/capability-routes/save`.
  - Exposes `applyAstraBridgeCapabilitiesPreset()` for `/api/router/mcp/preset/astrabridge-capabilities`.
  - Exposes generic MCP config/status actions and legacy Yunwu image test/generate actions.

- `apps/astrabridge-desktop/src/types.ts`
  - Defines `CapabilityRouteRecord`, `CapabilityRouteCandidate`, and `CapabilityRouteEntry`.
  - Current route types cover route mode, candidate metadata, resolution status, selected candidate, and route errors.
  - Current route types do not cover capability health, credential state, smoke summaries, artifact references, cost hints, or MCP preset visibility.

- `apps/astrabridge-desktop/src/features/i18n/catalog.ts`
  - Contains labels for capability routes, route mode, pinned candidate, web capability, and install capability runtime.
  - Does not yet contain labels for capability smoke tests, artifact history, credential/cost status, or automation preset selector states.

- `apps/astrabridge-desktop/src/features/automations/AutomationsPanel.tsx`
  - Automation runtime supports `mcp_preset_ids`.
  - The current UI uses a comma-separated text input with placeholder `astrabridge_web`.
  - Tests already cover parsing `astrabridge_web, astrabridge_capabilities`, but there is no controlled preset selector.

### Sidecar APIs And Runtime

- `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`
  - `GET /api/runtime/capability-routes` returns the capability route snapshot.
  - `POST /api/runtime/capability-routes/save` saves one capability route.
  - `POST /api/router/mcp/preset/astrabridge-capabilities` installs or reapplies the MCP preset.
  - `GET /api/router/mcp/config` and `GET /api/runtime/mcp/status` expose generic MCP config/runtime status.
  - There is a legacy Yunwu image test endpoint, but no generic capability smoke-test endpoint.

- `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`
  - `capability_route_snapshot()` resolves route entries from registry specs, configured models, and saved route records.
  - `save_capability_route()` persists normalized route records.

- `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_config_service.py`
  - `astrabridge_capabilities_preset()` installs server name `astrabridge_capabilities`.
  - The preset exposes `astrabridge_capability_routes`, `astrabridge_capability_image_generate`, `astrabridge_capability_vision_analyze`, `astrabridge_capability_speech_transcribe`, and `astrabridge_capability_speech_synthesize`.
  - The preset reads provider credentials from environment variables only.

- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/`
  - Runtime and adapters exist for `image.generate`, `vision.analyze`, `speech.transcribe`, and `speech.synthesize`.
  - `web.search` is registered as a standalone web lane and must not be folded into model-backed capability routing.
  - Adapter outputs persist artifacts under workspace-local `.astrabridge/capabilities/...` where applicable.

- `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md`
  - Documents stable capability ids, MCP server/tool names, routing rules, compatibility rules, and artifact paths.

## User Workflow Gaps

1. Capability discovery is too implementation-shaped.
   - The current page lists route records, but it does not explain availability, candidate eligibility, credential readiness, or what the user can do next.

2. Route management lacks operational context.
   - Users can choose auto or pinned, but cannot compare candidate health, adapter source, input/output modalities, last smoke result, or credential state in one place.

3. MCP preset installation is separated from capability management.
   - The capability tab does not show whether `astrabridge_capabilities` is configured or visible to the runtime.
   - The MCP tab has generic server counts, but not a capability-specific status summary.

4. Capability smoke testing is not unified.
   - Image has a legacy Yunwu smoke path.
   - Vision, speech transcription, and speech synthesis do not have a shared no-key/dry-run smoke surface.
   - Provider-backed smoke needs explicit user approval and sanitized evidence capture.

5. Artifact inspection is missing.
   - The adapters write artifacts, but the desktop UI does not expose recent capability artifacts, previews, audio playback, structured summaries, or safe diagnostics.

6. Automation handoff is too raw.
   - Automation authors must type comma-separated preset ids.
   - `astrabridge_capabilities` is not discoverable as a selectable capability preset from the automation form.

7. Safety and cost signals are incomplete.
   - There is no consolidated UI for missing credentials, disabled provider actions, paid-provider warnings, large artifact warnings, or unavailable candidate reasons.
   - The UI must show only redacted status, never raw secrets.

8. Documentation is split across plans and maps.
   - Runtime surface documentation exists, but it does not yet describe the final capability UI, smoke-test policy, or automation preset handoff.

## Backend And API Gaps

- Add typed API/client support for capability health/status. The current `CapabilityRouteEntry` is not enough to drive a full management console.
- Add or expose a capability-specific MCP preset status, derived from existing MCP config/status APIs if possible.
- Add a generic capability smoke-test API or explicit no-key fixture endpoints for image, vision, speech transcription, and speech synthesis.
- Add an artifact listing API for workspace-local capability artifacts, with redacted metadata and stable artifact references.
- Add credential readiness and cost/safety metadata as redacted status only. Do not expose raw key values or read plaintext key files without explicit user authorization.
- Add a preset discovery API or desktop-side preset catalog for automation UI selectors, covering at least `astrabridge_web` and `astrabridge_capabilities`.

## Proposed UI Navigation Shape

Keep capability management inside the existing setup/manager surface, but make it a complete operational panel:

- Overview
  - capability cards or dense rows for each capability id
  - lane type, resolved candidate, route mode, availability, credential readiness, and last smoke status
  - explicit standalone treatment for `web.search`

- Routes
  - current auto/pinned controls
  - candidate comparison details
  - save/reset state
  - inline route and eligibility errors

- Smoke Tests
  - one controlled panel per model-backed capability
  - no-key/dry-run or fixture mode by default
  - provider-backed run requires explicit user action
  - sanitized evidence links after each run

- Artifacts
  - recent outputs grouped by capability
  - image preview, audio playback/download, text/JSON summary, timestamp, provider/model, and sanitized diagnostic state

- MCP Runtime
  - install/reapply `astrabridge_capabilities`
  - configured/visible/healthy status
  - link to full MCP settings for advanced editing

- Automation Handoff
  - controlled selector/chips for MCP presets in automation forms
  - `astrabridge_capabilities` discoverable without raw string entry
  - preserve existing stored `mcp_preset_ids` compatibility

## Recommended Next Entry

Proceed to step 2 of `PLAN/CAPABILITY_UI_MANAGEMENT_IMPLEMENTATION_PLAN.md`:

`Normalize the desktop capability data contract and API client surface.`

The next agent should start by designing the typed data contract needed by the UI shape above, then add only the smallest backend fields required to support that contract.
