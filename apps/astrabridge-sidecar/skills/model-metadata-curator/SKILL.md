---
name: model-metadata-curator
description: Refresh, validate, and report AstraBridge provider/model metadata for Codex-compatible third-party providers, including Yunwu, DeepSeek, Kimi, and Qwen.
---

# Model Metadata Curator

Use this skill when AstraBridge needs provider/model metadata refreshed, validated, or exported for Codex app-server compatibility.

## Workflow

1. Read `references/provider-sources.json` for the source URLs and seed policy.
2. Run `scripts/collect_metadata.py --sources references/provider-sources.json --out <proposal.json>` to produce a sanitized proposal.
3. Import the proposal through the sidecar metadata APIs, or manually map the proposal into router model records.
4. Run `scripts/run_test_matrix.py` only when the user explicitly authorizes real provider-key usage. Use key files or environment variables; never write secret values to outputs.
5. Check the generated effective catalog for Codex `ModelInfo` completeness before treating a model as available to Codex.

## Guardrails

- Third-party models default to text-only for Codex agent turns until image/tool behavior is verified.
- Do not enable `supports_parallel_tool_calls`, `supports_search_tool`, `apply_patch_tool_type`, or hosted image/web tools without a passing smoke test.
- Keep Yunwu Apifox URLs even when they are not machine-readable; seed Yunwu models from the user-provided screenshot and mark `source_status=screenshot_seed`.
- Keep temperature UI normalized to `0-2`; provider adapters may clamp or omit values for stricter upstreams such as Qwen/DashScope.
- Kimi K2.x smoke tests showed upstream only accepts `temperature=1` when the field is present; use `kimi_only_temperature_1` so non-1 UI values are omitted with a warning.
- Never save API keys, bearer tokens, cookies, auth headers, or raw key-file contents.

