---
name: astrabridge-multimodal-capability-adapter
description: Probe, adapt, and validate a bounded image, vision, speech, or document capability route through AstraBridge's MCP capability runtime. Use when provider/model modality support differs or truthful fallback is required; never bypass capability exposure gates or silently drop a modality.
---

# AstraBridge Multimodal Capability Adapter

Use the `astrabridge.multimodal-capability-adapter` manifest and the existing
`multimodal_capability_adapter` graph template. Provider-specific content
shapes stay inside capability adapters; the skill handles only declared
capability contracts and fallback evidence.

## Resolve and validate

1. Read `orchestration-manifest.json`, the taxonomy contract, the multimodal
   capability matrix/exposure gates, and the canonical graph contract.
2. Declare the input content parts, target capability ID, size/count limits,
   desired output, and allowed fallback route. v1 lanes are `image.generate`,
   `vision.analyze`, `speech.transcribe`, and `speech.synthesize`.
3. Resolve, lint, compile, and dry-run before any live capability call. Check
   model-level exposure state instead of trusting provider-wide metadata.
4. Preserve workspace-scoped `ArtifactRef` values with media type, size,
   digest, and lineage. Provider-returned paths are untrusted input.
5. Send all capability/tool/resource calls through the `astrabridge_capabilities`
   MCP preset and broker/loopback policy. Keep fallback and downgrade status
   explicit in the typed result.

## Topology and contracts

- `capability probe` → `contract adapter` → `fallback validator`.
- Probe output: `schema.multimodal_probe` with detected modalities and plan.
- Adapter output: `schema.multimodal_adapted` plus
  `document_extract:adapted_contract`.
- Final output: `schema.multimodal_validation` plus
  `validation_report:multimodal_validation`.
- Default limits: 3 agents, 1 parallel lane, 80,000 total tokens, 6 provider
  calls, and 2 retries; graph depth is 2.

## Safety boundary

- Treat `documented_unwired`, `wired_unverified`, `blocked`, and `unknown`
  exposure states as non-runnable. Only `verified_runnable` may route by
  default.
- Keep nested subagents and direct teammate messages false. Never pass raw
  credentials, provider-private reasoning, unbounded media, or local paths as
  an unvalidated artifact.
- Video-specific lanes remain out of scope until separately qualified.
- Silent modality loss, catalog-only exposure, an unverified fallback, failed
  artifact validation, or an over-budget request is a blocker.
