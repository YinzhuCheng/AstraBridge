# Multimodal Maintenance Automation Handoff Plan

## Total Objective

Create a durable execution plan that future agents can use to keep AstraBridge's multimodal capability layer current, conservative, verifiable, and easy to extend as providers, models, and modality-specific APIs change. The target end state is not a one-time compatibility cleanup, but a repeatable maintenance workflow that combines official-doc sync, capability-matrix reconciliation, adapter-family repair, exhaustive dry-run coverage, bounded live smoke, rollout gates, and rollback-safe automation.

## Deliverables

- A multimodal maintenance workflow that connects provider documentation, capability contracts, model catalog metadata, adapter families, exposure gates, and verification evidence.
- Durable artifacts for provider/model/capability matrix reconciliation, dry-run audit output, blocked-lane classification, and live-smoke evidence.
- A maintenance-oriented skill and helper-script surface that future agents can run with explicit scope and authorization.
- A rollout policy that keeps multimodal exposure conservative by default and reversible when regressions appear.

## Related Context Files

- `PLAN/MULTIMODAL_CAPABILITY_ADAPTER_AND_UPDATE_HANDOFF_PLAN.md`
- `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`
- `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- `PLAN/MULTIMODAL_PROVIDER_OFFICIAL_SOURCE_PACK.md`
- `PLAN/MULTIMODAL_CAPABILITY_MATRIX_CONTRACT.md`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`
- `apps/astrabridge-sidecar/skills/agentic-update-pipeline/SKILL.md`

## Constraints And Attention Notes

1. Official provider documentation is the primary source for modality support, model status, request shape, and response shape claims.
2. Do not treat a documented model as exposed or recommended until adapter support and verification evidence exist.
3. Preserve `PRIVATE/**`, dry-run reports, smoke artifacts, normalized request/response traces, screenshots, and matrix outputs unless the user explicitly names cleanup targets.
4. Never persist API keys, bearer tokens, cookies, authorization headers, vault secrets, desktop key contents, or raw provider secrets in code, plans, logs, or artifacts.
5. Multimodal maintenance must stay capability-first. Provider quirks belong in adapter families and metadata, not in the capability contract itself.
6. Update automation must remain proposal-first. Live provider calls, code changes, install steps, and exposure changes require explicit authorization or an already-approved automation contract.
7. Unknown, blocked, or downgraded support is preferable to optimistic inheritance from provider-level defaults.
8. Rollout rules must tolerate provider drift, model retirement, parameter renames, and partial modality support without requiring large rewrites to stable capability-facing APIs.

## Adjustment Policy

Agents may reasonably adjust specific substeps, file paths, script boundaries, provider order, model prioritization, or validation commands when repository evidence requires it. Such adjustments must not change the total objective, weaken the conservative exposure policy, lower the evidence bar for multimodal support, or replace substantive compatibility work with documentation-only cleanup. If a core maintenance path becomes infeasible, record the blocker, evidence, attempted approaches, and a substitute that preserves the original maintenance intent.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must begin by reading this plan and the context files needed for the current step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all of its acceptance criteria are satisfied.
5. If blocked, record the concrete blocker, evidence, attempted paths, and exact next-step entry point.
6. Each turn must end with a concise handoff that states completed work, files changed, validation run, blockers, and next step.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Align Existing Plans And Ownership Boundaries
- Next step: Step 1, Align Existing Plans And Ownership Boundaries
- Last updated: 2026-07-07

## Execution Steps

### 0. Create Durable Plan

Goal: Create this plan and make the next entry point clear.

Main actions:

- Define the total objective, constraints, execution rules, steps, and acceptance criteria.
- Record the adjacent plans and code surfaces this maintenance loop depends on.
- Set current progress and initial log entry.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, constraints, adjustment policy, current progress, numbered steps, acceptance criteria, and progress log.
- The next step is unambiguous.

Status: completed

### 1. Align Existing Plans And Ownership Boundaries

Goal: Prevent future agents from splitting the same maintenance concern across conflicting plans.

Main actions:

- Map which concerns are owned by the multimodal runtime plan, the exhaustive smoke plan, and the agentic update pipeline plan.
- Record explicit ownership boundaries for contract work, adapter work, smoke work, and automation work.
- Identify where future agents should update one shared artifact instead of creating parallel records.

Acceptance criteria:

- A written ownership note exists under `PLAN/` or `PRIVATE/`.
- The note identifies which plan owns runtime implementation, which owns smoke execution, and which owns update automation.
- A future agent can choose the right plan entry point without reconstructing chat history.

Status: not started

### 2. Build The Multimodal Maintenance Matrix View

Goal: Turn the existing capability matrix contract into a maintenance-oriented working view.

Main actions:

- Define the exact row set for `provider/model/capability` maintenance coverage across `image.generate`, `vision.analyze`, `speech.transcribe`, and `speech.synthesize`.
- Record documented support, wired support, exposure state, verification state, and downgrade reason for every row in scope.
- Separate family-level assumptions from model-level facts.

Acceptance criteria:

- A matrix-view artifact exists on disk.
- Every in-scope row has an explicit status instead of implicit inheritance.
- Family-shared behavior and model-specific limits are distinguishable from the artifact alone.

Status: not started

### 3. Define Official-Doc Sync Rules For Multimodal Lanes

Goal: Make provider-doc maintenance reproducible instead of ad hoc.

Main actions:

- For each priority provider, record the official doc sources that are authoritative for model lists, modality support, request parameters, and streaming semantics.
- Classify which pages are rollout-critical and which are informational only.
- Define how doc drift should be classified into metadata-only, adapter-review, smoke-required, or blocked states.

Acceptance criteria:

- A doc-sync rule artifact exists or the source-pack artifact is extended accordingly.
- Every priority multimodal lane has named official source owners.
- Drift categories are explicit enough for a future agent or script to act conservatively.

Status: not started

### 4. Normalize Adapter-Family Maintenance Contracts

Goal: Ensure future model additions land through family contracts rather than one-off patches.

Main actions:

- Reconcile the current adapter families for image, vision, ASR, and TTS against the documented provider protocols.
- Define which changes are metadata-only onboarding and which require a new family or parser update.
- Record stable invariants for request building, response normalization, artifact persistence, and error mapping.

Acceptance criteria:

- A maintenance-facing adapter contract artifact exists or the existing family contract is extended.
- Family-shared invariants and new-family triggers are explicit.
- A future agent can decide whether a new model needs code or only metadata.

Status: not started

### 5. Tighten Model-Level Capability Eligibility

Goal: Stop provider-wide defaults from overstating multimodal support as providers expand their model lines.

Main actions:

- Define model-level eligibility rules for vision, ASR, TTS, and image generation.
- Make unsupported or unknown modality combinations fail before live provider calls.
- Record downgrade behavior for documented-but-unwired and wired-but-unverified lanes.

Acceptance criteria:

- Eligibility rules are recorded in code or a directly owning plan artifact.
- Representative blocked cases are enumerated for each modality family.
- A future agent can determine whether a model may be exposed without reading provider-specific code.

Status: not started

### 6. Exhaustive Dry-Run Coverage For All Multimodal Rows

Goal: Make maintenance coverage broad before consuming provider credits.

Main actions:

- Produce or extend a dry-run tool that traverses every in-scope matrix row.
- Emit route eligibility, adapter-family selection, validation result, downgrade reason, and expected artifact path for every row.
- Preserve secret-free reports in a durable location.

Acceptance criteria:

- A repeatable dry-run report exists for all in-scope rows.
- The report distinguishes runnable, blocked, unknown, downgraded, and conflicting lanes.
- The report can be regenerated without network or live credentials.

Status: not started

### 7. Blocked-Lane Triage Against Official Docs

Goal: Make blocked results actionable instead of ambiguous.

Main actions:

- Review blocked and downgraded rows against the official source pack.
- Classify each blocked lane as unsupported by docs, unsupported by runtime, unsupported by verification, or ambiguous due to provider drift.
- Record the exact next fix target for each lane.

Acceptance criteria:

- A blocked-lane triage artifact exists on disk.
- Every blocked lane has a reason class and next action.
- Unsupported-by-docs rows are separated from implementation defects.

Status: not started

### 8. Define The Minimal Live-Smoke Basis Per Family

Goal: Keep live verification bounded but sufficient to support conservative exposure.

Main actions:

- Choose one or more representative live-smoke cases for each priority adapter family.
- Define what evidence must be preserved for success, soft-failure, and hard-failure results.
- Define when a dry-run pass is sufficient and when provider-backed smoke is mandatory.

Acceptance criteria:

- A live-smoke basis artifact exists and maps to adapter families.
- Each chosen smoke case is justified by family coverage rather than random model selection.
- Promotion requirements per family are explicit.

Status: not started

### 9. Reconcile Multimodal Maintenance With The Agentic Update Pipeline

Goal: Reuse the existing updater architecture instead of building a parallel multimodal updater.

Main actions:

- Map multimodal maintenance steps onto the existing update pipeline scopes, proposal formats, diff engine, and validation gates.
- Identify missing multimodal-specific update hooks, artifact fields, or risk classes.
- Define the contract between multimodal matrix work and proposal-first update runs.

Acceptance criteria:

- A reconciliation note exists with file-level ownership.
- Reusable updater surfaces and multimodal-specific gaps are explicit.
- A future agent can route multimodal update work through the updater without inventing a new workflow.

Status: not started

### 10. Create Or Extend The Multimodal Maintenance Skill

Goal: Let future agents run the maintenance workflow without reconstructing this plan.

Main actions:

- Create or extend a skill that covers multimodal doc sync, matrix reconcile, blocked-lane triage, dry-run coverage, smoke execution, and rollout recommendations.
- Define accepted user scope inputs, authorization rules, artifact paths, and rollback boundaries.
- Point the skill to concrete scripts, sidecar APIs, and evidence outputs.

Acceptance criteria:

- A skill exists on disk with task-independent instructions.
- The skill defaults to proposal-first behavior and conservative exposure.
- The skill references concrete repository entry points and artifact rules.

Status: not started

### 11. Add Fixture And Test Support For Maintenance Workflows

Goal: Keep maintenance workflows testable when provider calls are unavailable.

Main actions:

- Add fixture coverage for provider docs, dry-run rows, blocked-lane classifications, and proposal generation.
- Add tests for family eligibility, downgrade rules, and maintenance artifact generation.
- Ensure failure reports are deterministic and secret-free.

Acceptance criteria:

- Focused tests exist for the maintenance workflow surfaces.
- Fixture-only runs can exercise the workflow without network or provider keys.
- Failing cases produce actionable outputs instead of generic errors.

Status: not started

### 12. Define Rollout Gates For Multimodal Exposure Changes

Goal: Prevent maintenance automation from silently widening multimodal exposure.

Main actions:

- Define which combinations of doc-sync evidence, dry-run success, smoke success, and review status are required before exposure changes.
- Define downgrade and rollback behavior when verification regresses.
- Ensure new models start conservative by default.

Acceptance criteria:

- A rollout-gate artifact exists or the existing rollout policy is extended.
- Exposure promotion and rollback conditions are explicit.
- Future agents have a clear rule for refusing unsafe exposure changes.

Status: not started

### 13. Pilot The Workflow On One Provider Family Cluster

Goal: Validate the maintenance loop against real repository complexity before generalizing.

Main actions:

- Choose one multimodal provider family cluster, such as Alibaba image plus TTS or Qwen vision plus ASR.
- Run the maintenance flow through doc sync, matrix update, dry-run, blocked-lane triage, and any authorized smoke.
- Record issues in workflow design, evidence schema, and skill instructions.

Acceptance criteria:

- A durable pilot evidence pack exists.
- Workflow gaps are recorded with concrete follow-up ownership.
- The pilot proves the maintenance loop is operational, not only theoretical.

Status: not started

### 14. Generalize Across All Priority Providers

Goal: Expand the maintenance loop from the pilot family to the full priority multimodal surface.

Main actions:

- Apply the workflow to all priority providers in scope.
- Consolidate repeated adapter, matrix, and smoke findings into shared fixes where possible.
- Record deferred providers or capabilities with explicit reasons.

Acceptance criteria:

- Priority providers have maintenance records under one consistent workflow.
- Shared fixes and provider-specific exceptions are both explicit.
- Deferred lanes are deliberate rather than accidental gaps.

Status: not started

### 15. Finalize Runbook And Long-Term Handoff

Goal: Leave a durable operating manual for future maintenance agents and human reviewers.

Main actions:

- Summarize plan ownership, matrix semantics, adapter-family rules, automation entry points, validation expectations, rollout gates, and rollback paths.
- Link the final runbook to the active multimodal runtime plan and the agentic update pipeline plan.
- Record remaining risks, known weak spots, and exact next entry points for future work.

Acceptance criteria:

- A final runbook or handoff note exists on disk.
- Remaining risks and deferred work are explicit.
- A future agent can continue multimodal maintenance from the runbook and this plan without reconstructing chat history.

Status: not started

## Progress Log

### 2026-07-07 - Step 0

- Completed: Created the durable multimodal maintenance automation handoff plan. The plan defines the maintenance objective, ownership boundaries with the existing multimodal runtime plan and the completed agentic update pipeline plan, conservative constraints, numbered execution steps, and acceptance criteria for future agents who need to keep multimodal support current and extensible.
- Files changed: `PLAN/MULTIMODAL_MAINTENANCE_AUTOMATION_HANDOFF_PLAN.md`
- Validation: Read the durable handoff plan skill and template, re-read the active multimodal adapter/update handoff plan, and inspected the existing `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md` so the new plan reuses established updater architecture instead of duplicating it.
- Blockers: None.
- Next step: Step 1, Align Existing Plans And Ownership Boundaries.
