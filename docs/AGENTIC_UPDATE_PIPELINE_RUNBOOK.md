# Agentic Update Pipeline Runbook

Last updated: 2026-07-26

This runbook defines the controlled AstraBridge workflow for provider/model metadata updates, provider adapter review, capability route drift checks, plugin/skill surface checks, Codex kernel candidate validation, and supervised auto-upgrade control for the tracks that are currently justified for unattended apply.

The pipeline is not a blanket auto-updater. It remains an agent-assisted proposal, validation, and supervised-apply system. A user or a stored user-approved automation must define the update scope before discovery starts. The updater discovers, proposes, validates, and records rollback evidence; only explicitly enabled tracks may advance through the supervised controller, and unsupported or higher-risk tracks remain off by default until their trust and recovery evidence exists.

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

If any of those actions are needed, the current run contract must explicitly permit the relevant authorization flag, and the run must preserve the relevant apply journal, validation report or apply manifest, and rollback manifest.

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
| `POST /api/agentic-updates/apply` | Apply journaled provider-metadata or capability-route proposals after approval. |
| `POST /api/agentic-updates/rollback` | Roll back an applied metadata proposal. |
| `POST /api/agentic-updates/supervised-run` | Run the supervised auto-upgrade controller across the requested tracks, enforcing per-track policy, cohorts, pause/kill switches, containment, and recovery-point recording. |
| `POST /api/agentic-updates/code-change-plan` | Create a code-change worktree plan without mutating source by default. |
| `POST /api/agentic-updates/kernel-verify` | Verify a Codex kernel candidate with fixture or binary evidence and preserve a journaled activation-gate record. |
| `POST /api/agentic-updates/automation-template` | Create a disabled-by-default recurring update check template. |

### Skill And Scripts

Agent handoff skill:

- `apps/astrabridge-sidecar/skills/agentic-update-pipeline/SKILL.md`
- `apps/astrabridge-sidecar/skills/agentic-update-pipeline/orchestration-manifest.json`

The manifest resolves to the built-in `provider_update_smoke_gate` graph. Before any live run, resolve, lint, compile, and dry-run it; the default is provider-free proposal generation, and the manual gate remains mandatory for provider calls or promotion.

Deterministic four-provider parser coverage:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
.\.venv\Scripts\python.exe skills\agentic-update-pipeline\scripts\run_four_provider_fixture_coverage.py --workspace-root D:\AstraBridge --run-id <run-id>
```

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
- `apply/apply-journal.json` when apply is attempted
- `apply/apply-manifest.json` when apply is attempted
- `apply/supervised-run-summary.json` when supervised apply is attempted
- `apply/supervised-run-report.md` when supervised apply is attempted
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

When an official provider publishes `llms.txt`, discovery may expand it by one level into a bounded set of same-origin Markdown documents. It must not follow external/private links or bypass redirect, content-type, decompression, response-size, and redaction guards. Kimi and GLM use this path. Kimi registers both official documentation origins and preserves `platform_id` from source record through parsed proposal provenance. DeepSeek uses canonical official HTML URLs with a provider-specific parser. Qwen keeps its bounded official Alibaba Cloud HTML path because no machine-readable index is registered for that upstream surface.

The accepted live Kimi proposal-only run `mechanism-repaired-kimi-20260726-r5` discovered Kimi K3 before runtime promotion. Step 22 then added the K3 built-in profile/catalog/transport contract: 1,048,576-token context, text/image/video input, native `low/high/max`, Codex `low/high/xhigh`, top-level `reasoning_effort`, and no K2 `thinking` object. Step 23 corrected the earlier single-platform assumption: `platform.kimi.com` credentials bind only to `https://api.moonshot.cn/v1`, while `platform.kimi.ai` credentials bind only to `https://api.moonshot.ai/v1`. Catalog refresh must preserve an existing binding and must never migrate a credential across these scopes. The accepted DeepSeek run is `step22-live-deepseek-proposal-20260726-r4`: it preserves the provider's column-oriented HTML pricing table, retains metadata signals that are separated from model ids, and emits V4 Flash/Pro context, pricing, tool, and reasoning-effort contracts. Earlier DeepSeek runs are preserved as diagnostics for fragmented table and reasoning evidence. The accepted GLM run is `step22-live-glm-proposal-20260726-r2`, while the first GLM run is preserved as diagnostic evidence for rejected link/architecture false positives.

Managed provider smoke should resume the encrypted user vault through the platform credential manager. If the user explicitly authorizes a named plaintext source for the current task, it may be used only in memory and must never be copied to an artifact. `LlmApiManagerService.test_key()` aligns a bound Kimi credential to its matching regional endpoint and persists a sanitized health record containing the credential platform id, provider base URL, request preview, structural response diagnostics or failure notice, response excerpt, and usage signal; reasoning text is redacted while token counts and non-replayable state are retained. It must not retry a failed Kimi credential on the other platform. The first authorized K3 smoke in Step 22 returned `fail` because a `platform.kimi.com` credential was sent to the international endpoint; no retry occurred. The Step 23 matching-endpoint run `step23-kimi-com-managed-20260726` then made exactly one non-stream K3 text call to `api.moonshot.cn`, returned HTTP 200 with `ok`, and made no retry or cross-region fallback. This verifies managed China-credential connectivity and the bounded K3 text transport only; image/video, tools, and long-context behavior retain their separate validation status.

Capability-route apply inside this lane must stay track-separated from provider metadata: it may write only isolated router-config state plus explicit apply-journal and rollback evidence, and it must fail closed on ambiguous route records.

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

## Supervised Auto-Upgrade Policy

The supervised controller is the only lane that may advance an update without a per-run interactive approval click, and even then it stays bounded by explicit per-track policy.

Current policy shape:

| Field | Meaning |
| --- | --- |
| `automation_mode` | `off` or `supervised_apply`. |
| `cohort` | Named rollout cohort such as `canary` or `manual_only`. |
| `cohort_size` | Intended cohort width for the current stage. |
| `paused` | Stops the track before apply. |
| `kill_switch` | Emergency stop that blocks the track immediately. |
| `depends_on` | Earlier tracks that must commit first in the same supervised run. |
| `max_failures_before_pause` | Failure threshold after which the track should remain paused for the next run. |

Current default posture on Sunday, July 19, 2026:

- `provider_metadata`: enabled for `supervised_apply`
- `capability_routes`: enabled for `supervised_apply`, dependent on metadata when both are present
- `codex_kernel`: off by default
- `plugin_skill_surface`: off by default
- `node_executors`: off by default
- `desktop_application`: off by default

The controller must preserve:

- one controller summary JSON and operator-facing Markdown report
- per-track apply journal and apply manifest for every committed unattended track
- rollback manifest paths for all committed unattended tracks
- clear containment state when a blocked or failed track stops the rollout

Mixed-track runs fail closed: once a track is blocked or fails, later tracks are skipped and the summary records the exact recovery point.

### Operator Recovery Playbook: Supervised Containment Or Updater Interruption

Use this bounded operator path when a supervised run stops on containment or an
update interruption rehearsal shows a rollback-required state.

1. Read `apply/supervised-run-summary.json` first and identify:
   - `stopped_after_track`
   - `containment.reason`
   - the last committed recovery point under `containment.recovery_points`
2. If a committed track exists, inspect its child-run artifacts before retrying:
   - child `apply/apply-journal.json`
   - child `apply/apply-manifest.json`
   - child `rollback/rollback-manifest.json`
3. If the blocked track is paused or kill-switched, do not retry until policy is
   changed deliberately and the reason is recorded.
4. If containment followed a failed apply, run rollback from the recorded child
   recovery point before enabling any later track.
5. Preserve the failed controller summary, the child rollback manifest, and the
   release-gate or runtime-stability bundle that caught the issue; do not clean
   them.

Expected bounded outcomes:

- `track_paused` or `kill_switch_active`: quarantine the track and stop.
- `automation_mode_off` or `automation_not_supported_for_track`: return to
  manual verification or manual promotion for that lane.
- `apply_failed:<track>`: roll back the last committed child run, preserve the
  failing child artifacts, and reopen only the single affected track after the
  root cause is fixed.

### Operator Recovery Playbook: Runtime Stability Long-Horizon And Chaos Signals

Use this consolidated operator surface when the shared runtime-stability gate or
rollout gate records failure, partial qualification, or a blocked release lane
for long-horizon stability or injected chaos drills. This playbook is a read
path over the existing gate owners; it must not become a second scheduler,
soak ledger, or ad hoc issue tracker.

Start with these shared evidence roots:

- `PRIVATE/runtime-stability/<run_id>/reports/summary.json`
- `PRIVATE/runtime-stability/<run_id>/reports/report.md`
- `PRIVATE/runtime-stability/<run_id>/validations/fault-matrix.json`
- `PRIVATE/runtime-stability/<run_id>/validations/long-horizon-bundle.json`
- `PRIVATE/runtime-stability/<run_id>/validations/injected-chaos-drills.json`
- `PRIVATE/runtime-rollout/<run_id>/reports/summary.json`
- `PRIVATE/runtime-rollout/<run_id>/validations/release-gate-summary.json`
- `PRIVATE/runtime-rollout/<run_id>/validations/rollback-readback.json`

Current bounded examples preserved by Step 29 work:

- `PRIVATE/runtime-stability/step29-2-gate/reports/summary.json`
- `PRIVATE/runtime-stability/step29-2-gate/validations/injected-chaos-drills.json`
- `PRIVATE/runtime-stability/step29-1/summary.json`
- `PRIVATE/runtime-stability/step29-2/summary.json`

Recovery table:

| Failure signature | Read first | Quarantine / containment action | Rollback or recovery action | Preserve for support bundle or escalation | Rerun entry point |
| --- | --- | --- | --- | --- | --- |
| `release_long_horizon_bundle.status != pass` | runtime rollout `reports/summary.json`, then nested release gate `validations/long-horizon-bundle.json` | Stop promotion for the affected release candidate. Do not advance later tracks or declare rollout-ready state. | Follow the failing suite entry under `long_horizon_bundle.suites[]` and recover only that lane. If the failing lane is updater-related, apply the supervised containment path above before reopening later tracks. | Preserve the rollout summary, nested release-gate summary, long-horizon bundle JSON, and matching suite stdout/stderr logs. | Re-run `python scripts/run_runtime_stability_gate.py --mode release` only after the single failing lane is repaired and rollback/quarantine notes are recorded. |
| `supervised_update_policy_and_containment` failure or containment stop | `apply/supervised-run-summary.json`, child apply/rollback manifests, then runtime-stability long-horizon bundle | Keep the blocked track paused or kill-switched. Do not reopen unrelated tracks to “see if they pass.” | Roll back from the last committed child recovery point when apply already touched state. If automation is unsupported, fall back to manual verification for that one track. | Preserve controller summary, child apply journal, child rollback manifest, and the long-horizon bundle/report that caught the failure. | Re-run the supervised controller only for the repaired track set after policy and recovery point are explicitly confirmed. |
| `windows_update_interruption_rehearsal` failure or rollback-readback mismatch | runtime rollout `validations/rollback-readback.json`, nested release gate `long-horizon-bundle.json`, and update rehearsal evidence | Freeze the candidate build or track. Do not promote new binaries or sidecar bundle changes from the same candidate. | Execute the recorded rollback/readback path first; only restore promotion once durable store readback and projection rebuilds are clean. | Preserve rollback-readback JSON, rehearsal logs, nested release-gate summary, and any affected apply or activation manifest. | Re-run the rollout gate after rollback-readback evidence returns to `pass`. |
| `provider_retry_storm_and_circuit_breaker_chaos` failure or `release_injected_chaos_drills.release_qualified=false` | runtime-stability `validations/injected-chaos-drills.json`, rollout `release-gate-summary.json`, and the provider chaos stdout/stderr logs | Quarantine the affected provider lane or release cohort. Do not widen provider concurrency, retry budgets, or default recommendations while the breaker path is unqualified. | Keep retry-budget and breaker thresholds fail-closed. Repair provider backpressure, rate-limit handling, or dispatch visibility before reopening the lane; do not bypass the breaker to force continuation. | Preserve the drill JSON, the provider chaos command logs, rollout summary, and any provider compatibility or failure-taxonomy evidence tied to the lane. | Re-run the runtime stability gate first; if release qualification is required, re-run the nested rollout gate only after the drill pack returns `pass` in release mode. |
| `mcp_timeout_cancel_and_policy_fail_closed` failure | runtime-stability summary plus the matching suite stdout/stderr logs | Quarantine the affected MCP capability or policy lane. Do not treat timeouts or policy bypass as a UI-only issue. | Restore timeout, cancellation, or policy fail-closed behavior before resuming long-running MCP tasks. If a task was partially applied, preserve it as needs-review rather than auto-retrying side effects. | Preserve suite logs, broker/server validation evidence, and the gate summary that marked the lane failed. | Re-run the stability gate after the exact MCP boundary fix lands; do not reopen broad provider or update promotion first. |
| `terminal_projection_and_stream_recovery` or `scheduler_recovery_and_idempotency` failure | runtime-stability summary, matching suite logs, and the fault matrix entry for truncated stream or duplicate suppression | Quarantine the affected release candidate or graph-runtime change set. Do not rely on manual observation that “the UI seemed fine.” | Repair terminal reconciliation, duplicate suppression, or resume semantics before allowing recovery-sensitive runs to proceed. If ambiguous external effects were recorded, stop on `needs_review` instead of replaying blindly. | Preserve suite logs, fault matrix JSON, durable run projection evidence, and any support-bundle snapshot captured during the failing run. | Re-run the stability gate only after the single recovery or idempotency fault is corrected and the preserved ambiguous run evidence is reviewed. |

Operator rules that apply to every row:

1. Read the shared gate summary first, then narrow to the specific child JSON or
   command logs named above.
2. Quarantine only the affected lane, cohort, or candidate unless the evidence
   explicitly shows cross-lane corruption.
3. Roll back or repair before rerun when any recorded state mutation already
   occurred; do not “test forward” through a known bad recovery point.
4. Preserve gate summaries, child JSON artifacts, and matching stdout/stderr
   logs as the support-bundle seed. Do not replace them with a handwritten
   narrative.
5. Re-run only the bounded gate named in the row after the fix; avoid creating
   a parallel checklist or out-of-band approval tracker.

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
