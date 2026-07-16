# Multimodal Maintenance Surfaces

Use this reference to keep maintenance work on the intended repository surfaces.

## Primary Flows

### Doc Sync

- Source registry:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`
- Official source pack:
  - `PLAN/MULTIMODAL_PROVIDER_OFFICIAL_SOURCE_PACK.md`
- Existing discovery helper:
  - `apps/astrabridge-sidecar/skills/model-metadata-curator/scripts/collect_metadata.py`

Expected write paths:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/doc-sync/**`

### Matrix Reconcile

- Dry-run matrix:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py`
- Verification gate:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate.py`
- Baseline:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate_baseline.json`

Expected write paths:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/matrix/**`
- linked dry-run run directories created by the sidecar module

### Provider-Backed Smoke

- Sidecar HTTP surfaces:
  - `GET /api/health`
  - `GET /api/llm-manager/session`
  - `GET /api/profiles`
  - `GET /api/admin/session`
  - `POST /api/runtime/provider-compatibility-smoke`
- Core implementation:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_compatibility_smoke.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py`

Expected write paths:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/live-smoke/**`
- sidecar-owned smoke outputs under `PRIVATE/provider-compatibility/**` or the current project workspace

### Rollout Gate

- Verification gate module:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate.py`
- Optional broader update gate:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/validation.py`
- Scope and rollback contracts:
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/contracts.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/artifacts.py`
- Policy artifact:
  - `PLAN/MULTIMODAL_ROLLOUT_AND_ROLLBACK_POLICY.md`

Expected write paths:

- `PRIVATE/agentic-update-pipeline/runs/<run_id>/rollout-gate/**`
- `PRIVATE/agentic-update-pipeline/runs/<run_id>/run-contract.json`
- `PRIVATE/agentic-update-pipeline/runs/<run_id>/rollback/**`

### Repair

- Skill:
  - `apps/astrabridge-sidecar/skills/provider-capability-repair/SKILL.md`
- Diagnostic entrypoint:
  - `apps/astrabridge-sidecar/skills/provider-capability-repair/scripts/diagnose_capability_case.py`

## Multimodal Capability Families

Current family targets in this maintenance slice:

- `dashscope_image`
- `chat_multimodal_vision`
- `dashscope_asr`
- `dashscope_tts`

Primary implementation files:

- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/dashscope_image_generate_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/vision_analyze_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_transcribe_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`

## Secret Rules

Never store:

- API keys
- bearer tokens
- `Authorization` headers
- cookies
- vault contents
- desktop plaintext key paths or contents

Allowed durable evidence:

- sanitized request samples
- sanitized response summaries
- artifact refs
- matrix summaries
- smoke case summaries
- unit test logs
