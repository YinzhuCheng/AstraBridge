# Agentic Update Pipeline Runbook

Last updated: 2026-07-06

This runbook defines the controlled AstraBridge workflow for provider/model metadata updates, provider adapter review, capability route drift checks, plugin/skill surface checks, and Codex kernel candidate validation.

The pipeline is not an auto-updater. It is an agent-assisted proposal and validation system. A user or a stored user-approved automation must define the update scope before discovery starts. The updater discovers, proposes, validates, and records rollback evidence; it applies or promotes only when the current run contract and explicit approval allow it.

## User Scope Contract

Every run starts from a secret-free run contract. The user specifies the contract through the desktop Updates review panel, a sidecar API call, an automation template, or an agent using the update skill.

Required or common fields:

| Field | Meaning |
| --- | --- |
| `scope` | One or more of `provider_metadata`, `provider_adapter`, `capability_routes`, `codex_kernel`, `plugin_skill_surface`, or `docs_only`. |
| `providers` | Optional provider ids, for example `qwen`, `deepseek`, `kimi`, `glm`, `yunwu`, or `openai`. Empty means all selected source records in the current context. |
| `models` | Optional exact model ids when the update is model-specific. |
| `version_policy` | `stable`, `latest`, `pinned`, `deprecated_check`, or `security_fix_only`. |
| `target_version` | Required when `version_policy=pinned`; may be a model id, release tag, or Codex version. |
| `apply_mode` | `discover_only`, `proposal_only`, `isolated_apply`, `verify_candidate`, or `promote_after_smoke`. |
| `allow_network` | Allows official-doc discovery. Use `false` for fixture-only validation. |
| `allow_provider_calls` | Allows provider-backed smoke only when true and credentials are available. Default is false. |
| `allow_install` | Allows install-sensitive Codex/plugin work only when true. Default is false. |
| `allow_code_changes` | Allows code-change planning only when true. Default is false. |
| `approval_policy` | Normally `manual_review_required`; `preapproved_discovery_only` is only for discovery/proposal checks. |

Example proposal-only Qwen metadata check:

```json
{
  "scope": ["provider_metadata"],
  "providers": ["qwen"],
  "version_policy": "stable",
  "apply_mode": "proposal_only",
  "allow_network": true,
  "allow_provider_calls": false,
  "allow_install": false,
  "allow_code_changes": false,
  "approval_policy": "manual_review_required"
}
```

Example pinned Codex kernel candidate discovery:

```json
{
  "scope": ["codex_kernel"],
  "version_policy": "pinned",
  "target_version": "0.138.0",
  "apply_mode": "verify_candidate",
  "allow_network": true,
  "allow_provider_calls": false,
  "allow_install": false,
  "allow_code_changes": false,
  "approval_policy": "manual_review_required"
}
```

## What Is Never Automatic

These actions never happen silently:

- applying provider metadata to live runtime config
- modifying source code, provider transports, provider profiles, or generated catalog locks
- calling paid or key-backed provider APIs
- installing or switching a Codex kernel candidate
- installing or updating plugins or skills
- writing official Codex `~/.codex/config.toml`
- creating product `.codex*` project state
- reading desktop key files or other plaintext secret files
- pushing commits, merging branches, publishing releases, or writing external platforms
- marking a model, capability, provider, or kernel candidate verified without preserved validation evidence

If any of those actions are needed, the current run contract must explicitly permit the relevant authorization flag, and the run must preserve an apply manifest, validation report, and rollback manifest.

## Entry Points

### Desktop UI

Use the Updates review panel in the AstraBridge manager surface.

The panel lets the user select scope, provider, version policy, target version, apply mode, and network allowance. Current UI proposal generation is intentionally conservative: apply, provider smoke, install, and promotion actions remain disabled unless a later authorized workflow enables them.

### Sidecar API

Use these endpoints for controlled runs:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/agentic-updates/start` | Start discovery/proposal generation. |
| `GET /api/agentic-updates/status` | Read the latest or selected job status. |
| `GET /api/agentic-updates/result` | Read the proposal result. |
| `GET /api/agentic-updates/runs` | List preserved update runs. |
| `POST /api/agentic-updates/validate` | Run validation gates for a proposal. |
| `POST /api/agentic-updates/apply` | Apply metadata-only proposals after approval. |
| `POST /api/agentic-updates/rollback` | Roll back an applied metadata proposal. |
| `POST /api/agentic-updates/code-change-plan` | Create a code-change worktree plan without mutating source by default. |
| `POST /api/agentic-updates/kernel-verify` | Verify a Codex kernel candidate with fixture or binary evidence. |
| `POST /api/agentic-updates/automation-template` | Create a disabled-by-default recurring update check template. |

### Skill And Scripts

Agent handoff skill:

- `apps/astrabridge-sidecar/skills/agentic-update-pipeline/SKILL.md`

Reusable offline dogfood:

```powershell
cd D:\AstraBridge
.\apps\astrabridge-sidecar\.venv\Scripts\python.exe .\scripts\agentic_update_fixture_dogfood.py --run-id step18-fixture-dogfood-manual
```

Step 19 provider pilot evidence runner:

```powershell
cd D:\AstraBridge
.\apps\astrabridge-sidecar\.venv\Scripts\python.exe .\PRIVATE\agentic-update-pipeline\step19_provider_pilot_runner.py
```

The Step 19 runner is preserved as evidence for the Qwen official-docs pilot. It is not a general public updater script; use the sidecar API or skill for new scopes.

## Artifact Layout

Every run writes under:

```text
PRIVATE/agentic-update-pipeline/runs/<run_id>/
```

Expected core artifacts:

- `run-contract.json`
- `sources/source-index.json`
- `sources/source-pack.jsonl`
- `parsed/parser-output.json`
- `parsed/codex-kernel-candidates.json` when scoped to Codex kernel
- `proposals/proposal.json`
- `diffs/proposal-diff.json`
- `diffs/proposal.md`
- `validation/validation-report.json`
- `validation/validation-report.md`
- `apply/apply-manifest.json` when apply is attempted
- `rollback/rollback-manifest.json`
- `secret-scan/secret-scan-report.json`
- `summary.json`

Do not clean old runs unless the user names exact cleanup targets. Failed and blocked runs are evidence.

## Workflow By Scope

### Provider Metadata

Use for model lists, context windows, output limits, pricing, deprecation, source provenance, defaults, and recommendation hints.

1. Start with `apply_mode=proposal_only`.
2. Discover official provider sources or fixture sources.
3. Parse into candidate model metadata.
4. Diff against current catalog/profile state.
5. Validate with schema, metadata, model catalog, diff, and secret-scan gates.
6. Apply only if the proposal is `metadata_only` or lower risk, the run has manual approval, and rollback evidence exists.

### Provider Adapter Or Capability Routes

Use when upstream changes affect request schema, reasoning/thinking fields, tool calls, image/audio formats, token usage, hosted web/search, MCP, or apply-patch behavior.

1. Generate a proposal and diff first.
2. Treat unknown parsed fields or transport/schema drift as `requires_adapter_review`.
3. Use `code-change-plan` to create a branch/worktree plan.
4. Do not mutate the main worktree unless explicitly authorized.
5. Require provider-backed smoke before any verified promotion.

### Codex Kernel

Use for Codex CLI/kernel candidates.

1. Discover official release/package/install-hint sources.
2. Do not install or switch binaries during discovery.
3. Treat every candidate as `requires_kernel_smoke`.
4. Verify with kernel probe and kernel smoke before marking verified.
5. Preserve rollback state for binary locator changes.

### Plugin Or Skill Surface

Use for plugin/skill discovery, skill contract drift, and install-sensitive changes.

1. Treat plugin or skill installation as install-sensitive.
2. Require `allow_install=true` before install attempts.
3. Preserve install plan, side effects, rollback metadata, and trust review evidence.

### Docs Only

Use for runbooks, source notes, and compatibility documentation. A docs-only run still needs a run contract, proposal, validation evidence, rollback/noop evidence, and secret scan.

## Validation Gates

Validation is selected from the proposal risk class and change requirements.

Core gates:

- schema validation
- metadata tests
- model catalog tests
- transport tests
- provider compatibility smoke
- capability smoke
- Codex kernel probe
- Codex kernel smoke
- desktop tests
- desktop build
- diff check
- secret scan
- rollback plan review
- manual review

Provider-backed gates require both:

- `allow_provider_calls=true`
- redacted credential status showing the provider is available

If either is missing, the gate records a skipped or blocked reason and promotion remains blocked.

## Rollback

Rollback evidence is mandatory before or with any apply path.

Metadata apply must preserve:

- sanitized router config before/after
- generated model/source catalog locks before/after
- changed paths
- backup paths
- rollback manifest path

Code-change planning must preserve:

- branch/worktree name
- planned files and test gates
- rollback instructions that do not run destructive git commands without explicit user approval

Kernel verification must preserve:

- candidate metadata
- binary locator state
- probe evidence
- smoke evidence
- rollback requirement when verification is blocked or failed

Noop or proposal-only runs should still write a rollback manifest explaining that no runtime/source state changed.

## Automation Template

The automation scheduler supports `agentic_update_check`.

Automation update checks are disabled by default and are intended for recurring discovery/proposal work only. They must not apply changes, install binaries, call providers, mutate source, or promote models. They can create inbox findings and preserve proposal/diff/summary artifact references for human review.

## Status Language

Use these terms consistently:

| Status | Meaning |
| --- | --- |
| `discovered` | Official or fixture sources were fetched or replayed and preserved. No proposal claim is implied. |
| `proposed` | A proposal and diff were generated. It is reviewable, not applied. |
| `applied` | A permitted metadata-only proposal was applied inside the allowed state boundary and has rollback evidence. |
| `verified` | Required validation, provider smoke, or kernel smoke passed with preserved evidence. |
| `partial` | Some gates passed, but at least one relevant behavior remains unproven or warning-gated. |
| `blocked` | Promotion or apply is blocked by missing approval, missing provider-call authorization, missing credentials, failed validation, unsafe risk class, parser uncertainty, or manual-review requirement. |
| `deprecated` | Source or proposal marks a model as deprecated and validation confirms the catalog should warn or remove it according to policy. |
| `recommended` | A model/provider/kernel candidate can be suggested only after verified evidence and manual review support that recommendation. |

## Promotion Policy

Promotion means moving a proposal from discovery/review evidence into product defaults, recommendation hints, verified compatibility status, or applied metadata.

Minimum promotion rules:

- `docs_only`: proposal review, diff check, rollback/noop evidence, and secret scan must pass.
- `metadata_only`: schema, metadata, model catalog, diff, rollback, and secret scan gates must pass; manual approval is required for apply.
- `requires_provider_smoke`: provider compatibility and capability smoke must pass with explicit provider-call authorization and redacted credential evidence.
- `requires_kernel_smoke`: kernel probe and smoke must pass; install/switch remains separately authorized.
- `requires_adapter_review`: code-change planning, transport tests, relevant UI/API tests, provider smoke, and manual review are required.
- `blocked_manual_review`: no promotion. Resolve the blocker and run a new proposal or validation pass.

Step 19 current evidence is intentionally blocked: Qwen official-doc discovery succeeded, but generic HTML parsing produced a conservative `qwen/unknown-model` adapter-review proposal and provider-backed smoke was not authorized. The next recommended pilot is a Qwen provider-specific parser improvement followed by a rerun of the same official-docs scope; if the user explicitly authorizes provider calls, add bounded provider-backed smoke for the exact proposed model or capability.
