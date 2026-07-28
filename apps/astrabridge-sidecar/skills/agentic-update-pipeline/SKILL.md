---
name: agentic-update-pipeline
description: Run controlled AstraBridge provider/model metadata, provider adapter, docs-only, plugin/skill surface, and Codex kernel update workflows. Use when a user asks an agent to check upstream provider or Codex changes, discover new models or versions, generate an update proposal, classify compatibility risk, validate a scoped update, apply an approved metadata/code/kernel candidate change, or roll back an AstraBridge update run.
---

# Agentic Update Pipeline

Use this skill to help AstraBridge update itself safely. The default behavior is controlled update assistance: discover official upstream changes, generate a reviewable proposal, classify risk, validate, and apply only after the current run contract explicitly permits it.

Never silently apply changes, install a Codex candidate, call paid provider APIs, modify user settings, push commits, or write external platforms.

## Start Every Run

1. Read `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md` if the user is executing the durable plan.
2. Normalize the user request into a run contract with:
   - `scope`: one or more of `provider_metadata`, `provider_adapter`, `capability_routes`, `codex_kernel`, `plugin_skill_surface`, `docs_only`
   - `providers`: optional provider ids such as `qwen`, `deepseek`, `kimi`, `glm`, `yunwu`, `openai`
   - `models`: optional exact model ids
   - `version_policy`: `pinned`, `stable`, `latest`, `deprecated_check`, or `security_fix_only`
   - `target_version`: required for `version_policy=pinned`
   - `apply_mode`: `discover_only`, `proposal_only`, `isolated_apply`, `verify_candidate`, or `promote_after_smoke`
   - `allow_network`, `allow_provider_calls`, `allow_install`, `allow_code_changes`
   - `approval_policy`: default `manual_review_required`
3. Use `astrabridge_sidecar.agentic_updates.normalize_update_scope_contract` to validate the contract before doing discovery.
4. Create or reuse the run artifact layout under `PRIVATE/agentic-update-pipeline/runs/<run_id>/`.
5. Preserve artifacts by default. Do not clean old runs unless the user names exact cleanup paths.

## Current Code Entry Points

Use these sidecar modules before inventing new scripts:

- Contract and proposal schema: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/contracts.py`
- Artifact and rollback layout: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/artifacts.py`
- Provider source registry: `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`
- Discovery runner: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/discovery.py`
- Provider parser interface: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/parsers.py`
- Codex kernel candidate discovery: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/kernel_candidates.py`
- Diff and risk classification: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/diffing.py`

Expected run artifacts:

- `run-contract.json`
- `sources/source-index.json`
- `sources/source-pack.jsonl`
- `parsed/parser-output.json`
- `parsed/codex-kernel-candidates.json`
- `proposals/proposal.json`
- `diffs/proposal-diff.json`
- `diffs/proposal.md`
- `validation/validation-report.json`
- `apply/apply-manifest.json`
- `rollback/rollback-manifest.json`
- `secret-scan/secret-scan-report.json`

Prefer the implemented sidecar proposal surface for app-owned runs: `POST /api/agentic-updates/start`, `GET /api/agentic-updates/{run_id}/status`, `GET /api/agentic-updates/{run_id}/result`, and `GET /api/agentic-updates/runs`. Direct Python helpers remain appropriate for focused tests and preserved diagnostic runs.

The adjacent `orchestration-manifest.json` resolves this skill to the built-in `provider_update_smoke_gate` graph. Resolve, lint, compile, and dry-run that manifest before live execution. Its defaults remain proposal-only; provider calls and promotion stay behind explicit manual gates.

## Official Documentation Indexes

- Prefer a provider's official `llms.txt` or equivalent machine-readable documentation index when registered.
- Follow only bounded, same-origin Markdown links selected by update relevance. Keep discovery depth at one and respect the run-wide source cap.
- Do not weaken redirect, private-address, content-type, decompression, or response-size guards to accommodate stale HTML URLs. Update the stable source seed or use the provider's machine-readable index instead.
- Kimi has two independent official platform scopes. Discover both `https://platform.kimi.com/docs/llms.txt` and `https://platform.kimi.ai/docs/llms.txt`, retain each source record's `platform_id`, and propagate it through discovery and proposal provenance. Its parser merges model-list, model-guide, reasoning-effort, modality, pricing, and deprecation evidence into one candidate per native model.
- Kimi native reasoning values and Codex-visible efforts are separate. For a model declaring native `low/high/max`, preserve native values and propose the Codex mapping `low->low`, `high->high`, `xhigh->max`.
- Kimi China credentials from `platform.kimi.com` use `https://api.moonshot.cn/v1`; international credentials from `platform.kimi.ai` use `https://api.moonshot.ai/v1`. Never rewrite, fall back, or retry a credential against the other scope. Persist the non-secret platform binding on managed key records and align the provider endpoint before an authorized smoke.
- Kimi K3 uses top-level `reasoning_effort` and no K2 `thinking` object on both official API scopes. Treat K2 request shaping as a separate compatibility branch.
- A new reasoning request field or mapping is an adapter requirement, not metadata-only work. Keep it at `requires_adapter_review` until transport tests and authorized provider smoke pass.
- DeepSeek uses canonical official HTML URLs with trailing slashes and a bounded provider-specific HTML parser. GLM uses `https://docs.z.ai/llms.txt` plus same-origin Markdown and a provider-specific Markdown parser.
- Qwen's official Alibaba Cloud surface does not currently expose a registered machine-readable documentation index in this pipeline. Keep its existing bounded official HTML parser path; do not invent or follow a non-official index.

## Workflow Routing

### Provider Metadata

Use for new model ids, context windows, modalities, pricing, deprecation, default/recommended hints, and source provenance.

1. Run discovery with official provider sources or fixtures.
2. Parse source packs with `parse_agentic_update_source_pack`.
3. Merge evidence by provider/native model; reject weak family-name and unknown-model noise before diffing.
4. Diff with `build_agentic_update_diff`.
5. Keep new capabilities conservative until validation passes.
6. Treat metadata-only changes as proposal-only unless `apply_mode` and approval allow isolated apply.

### Provider Adapter Or Capability Routes

Use when upstream changes affect request schema, tool calls, reasoning parameters, image/audio formats, token usage, web search, MCP, or apply-patch behavior.

1. Generate a proposal and diff first.
2. Classify schema or transport changes as `requires_adapter_review`.
3. Do not mutate transport/profile/router code unless `allow_code_changes=true`, `approval_policy=manual_review_required`, and a branch/worktree boundary exists.
4. Require relevant unit tests and provider smoke before promotion.

### Codex Kernel

Use for Codex CLI/kernel candidate versions.

1. Discover candidates with `discover_codex_kernel_candidates`.
2. Do not install or switch binaries during discovery.
3. Treat every candidate as `requires_kernel_smoke` until probe and smoke evidence exist.
4. Never write official Codex `~/.codex/config.toml`, project `.codex*`, or normal AstraBridge runtime config as part of discovery.
5. Use existing kernel probe/smoke surfaces for later verification: `codex_kernel_probe.py`, `codex_kernel_smoke.py`, and `codex_kernel_matrix_gate.py`.

### Docs-Only

Use when updating runbooks, source notes, or compatibility documentation without changing runtime behavior.

1. Still create a run contract and proposal.
2. Cite sanitized evidence paths, not long raw upstream excerpts.
3. Keep raw external payloads out of git-tracked docs.

### Plugin Or Skill Surface

Use when updating Codex plugin/skill assumptions.

1. Treat installer or plugin changes as install-sensitive.
2. Require `allow_install=true` before any install attempt.
3. Keep plugin/skill discovery separate from provider metadata promotion.

## Risk Rules

Use the most conservative applicable risk class:

- `docs_only`: documentation or pricing text changes that do not alter runtime behavior.
- `metadata_only`: model catalog fields that do not assert unverified capabilities.
- `requires_provider_smoke`: tool calls, web search, `apply_patch`, image/audio/video, reasoning behavior, or long-context claims.
- `requires_kernel_smoke`: Codex kernel candidates or app-server/CLI compatibility changes.
- `requires_adapter_review`: transport/schema changes, unknown parsed fields, or profile/router code impact.
- `blocked_manual_review`: removals, unsafe paths, unsupported contracts, missing evidence, or contradictory sources.

Do not mark a model, provider capability, or kernel candidate verified unless the validation artifacts prove it.

## Validation Commands

Run focused validation for the touched surface from `apps/astrabridge-sidecar`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_contract tests.test_agentic_update_artifacts
.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_discovery tests.test_agentic_update_parsers tests.test_agentic_update_diffing
.\.venv\Scripts\python.exe -m unittest tests.test_agentic_update_kernel_candidates tests.test_provider_source_registry
```

For deterministic four-provider parser coverage without network access or provider keys, run `scripts/run_four_provider_fixture_coverage.py` with an explicit workspace root and run id. Preserve its source pack, parser output, and `validation/four-provider-coverage.json` report.

Run `py_compile` for any edited Python modules. For desktop UI update surfaces added later, also run the relevant `npm test` or `tsc --noEmit` command from `apps/astrabridge-desktop`.

Always run a focused secret scan over touched files and durable artifacts. Record matches and explain synthetic or non-secret matches.

## Apply And Rollback Rules

- Default to `proposal_only`; `changed_paths` must stay empty unless the contract authorizes mutation.
- Metadata apply must snapshot current catalog/router state and write `apply/apply-manifest.json`.
- Rollback instructions must be recorded in `rollback/rollback-manifest.json` before or with apply.
- Do not use destructive git commands for rollback without explicit user approval.
- Preserve failed apply artifacts; they are evidence.
- Keep provider calls, Codex installs, and code changes separately authorized and separately logged.

## Handoff

When this skill is used under a numbered durable plan:

1. Complete exactly one full numbered plan step per turn.
2. Update the plan status and progress log before stopping.
3. Record changed files, validation commands, blockers, and the exact next step.
4. Leave the goal active unless every numbered step and final acceptance criterion is complete.
