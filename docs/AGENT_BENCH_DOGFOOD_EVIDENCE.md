# AstraBridge Agent Bench Dogfood Evidence

Generated from the first-round dogfood plan on 2026-06-27.

## Scope

This document summarizes the first small-sample AstraBridge agent benchmark dogfood round from `PLAN/AGENT_BENCH_DOGFOOD_EXECUTION_PLAN.md`. The round used classic agent benchmark task shapes as product validation probes, not as external leaderboard scoring.

Primary evidence is preserved under `PRIVATE/agent-bench-dogfood/`:

- Reports: `PRIVATE/agent-bench-dogfood/reports/`
- Raw redacted summaries: `PRIVATE/agent-bench-dogfood/raw/`
- Screenshots: `PRIVATE/agent-bench-dogfood/screenshots/`
- Machine-readable Step 20 summary: `PRIVATE/agent-bench-dogfood/reports/step20-first-round-summary.json`

## Results

Record-level harness results:

| Metric | Value |
| --- | ---: |
| Harness records | 16 |
| Pass records | 13 |
| Partial records | 3 |
| Real API or network records | 8 |
| Screenshot files | 52 |
| Records with explicit token usage | 3 |
| Known input tokens | 56185 |
| Known output tokens | 4185 |
| Known reasoning tokens | 1019 |
| Known total tokens | 60370 |

Capability-family final status:

| Family | Final Status | Evidence |
| --- | --- | --- |
| `AB-CODE-001` | pass | `step5-codefix-record.json`, `step6-ui-harness-record.json` |
| `AB-SHELL-001` | pass | `step7-shellfile-record.json`, `step8-shellfile-fix-record.json` |
| `AB-BROWSER-001` | pass | `step9-browser-state-record.json`, `step10-browser-supervision-record.json` |
| `AB-WEB-001` | pass after repair | `step11-web-research-record.json`, `step12-web-evidence-fix-record.json` |
| `AB-VISION-001` | partial | `step13-multimodal-input-record.json` |
| `AB-ASSET-001` | pass | `step14-multimodal-generation-record.json` |
| `AB-PLUGIN-001` | pass | `step15-plugin-skill-discovery-record.json` |
| `AB-MCP-001` | pass | `step16-mcp-tool-call-record.json` |
| `AB-AUTO-001` | pass after repair | `step17-automation-run-record.json`, `step18-automation-ledger-fix-record.json` |
| `AB-ROUTE-001` | pass | `step19-cross-provider-routing-record.json` |

The three partial records are meaningful dogfood findings, not discarded runs:

- Step 11 exposed weak source selection and source spillover; Step 12 fixed pinned-source evidence policy and UI source attribution.
- Step 13 showed that provider-backed `vision.analyze` can succeed, while the normal chat attachment path can still stall without a useful final answer or timeout.
- Step 17 exposed ambiguous automation finalization; Step 18 fixed interrupted-run recovery, triage artifacts, inbox visibility, and related UI layout.

## Product Fix Themes

- Runtime and model catalog normalization for provider-specific reasoning effort and apply-patch metadata.
- Task/execution-lane restoration and conversation rendering after provider lane switches.
- Browser and runtime evidence UI readability, including screenshot path layout and empty-state avoidance.
- Pinned-source Web evidence policy, source-origin attribution, and UI badges.
- Capability route artifact and media previews for vision and generated images.
- Plugin/skill registry loading behavior and fixture status consistency.
- Automation cancel/recovery triage, inbox artifacts, interrupted-run recovery, and Windows-safe atomic writes.
- Cross-provider handoff context clarity through `Active provider route` in context packs.

## Remaining Risks

- The normal chat multimodal attachment path can still stall without a useful final model answer or timeout message.
- Token and cost accounting is incomplete for image generation, Web/network lanes, and some automation runtime sessions.
- Some live validations depend on app-managed sidecar ports that can be reclaimed; current-source sidecar verification was needed during Step 19.
- This first round is a small-sample product dogfood, not a statistically meaningful benchmark score.

## Screenshot Index

| Screenshot Group | Count |
| --- | ---: |
| `baseline-20260626-step2` | 4 |
| `step5-codefix` | 1 |
| `step6-ui-harness` | 1 |
| `step7-shellfile` | 1 |
| `step8-shellfile-fix` | 1 |
| `step9-browser-state` | 6 |
| `step10-browser-supervision` | 2 |
| `step11-web-research` | 4 |
| `step12-web-evidence-fix` | 7 |
| `step13-multimodal-input` | 5 |
| `step14-multimodal-generation` | 4 |
| `step15-plugin-skill-discovery` | 2 |
| `step16-mcp-tool-call` | 6 |
| `step17-automation-run` | 3 |
| `step18-automation-ledger-fix` | 3 |
| `step19-cross-provider-routing` | 2 |

## Round 2 Adjustments

The next dogfood round should raise coverage rather than repeat the same smoke paths:

- Add a dedicated chat-attachment multimodal repair task that verifies timeout messaging, final-answer detection, and artifact linkage for image prompts in the normal chat lane.
- Add provider token/cost accounting coverage for automation runs, image generation, and Web/network lanes.
- Repeat selected tasks on a current-source sidecar launched by the harness, avoiding ambiguity when the app-managed sidecar reclaims a port.
- Extend cross-provider routing to include failure and fallback paths, not only successful handoff.
- Add plugin install/approval end-to-end coverage beyond discovery-only fixture execution.
- Add automation success-path finalization coverage, not only cancel/recover/interrupted-run recovery.
- Promote screenshot review into a small visual QA checklist for overflow, clipped paths, empty states, and misleading runtime/provider labels.

## Redaction

This summary is intentionally secret-free. It does not include API keys, bearer tokens, cookies, authorization headers, vault passwords, admin session tokens, or provider raw secrets.
