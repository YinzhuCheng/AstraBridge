# Legacy Cleanup Audit

Last updated: 2026-06-23

## Purpose

This audit classifies current legacy-string matches so that later cleanup steps can work from evidence instead of rescanning and re-deciding scope.

Scan baseline used for this audit:

```powershell
cd D:\AstraBridge
rg -n "Local Codex Router|Research OS|LCR|lcr|\.lcrproj|\.lcr|\.codexproj|\.codex-shell|lcr-models" --glob "!PRIVATE/**" --glob "!node_modules/**" --glob "!dist/**" .
```

## Classification Rules

- `delete`: remove the matched legacy path or compatibility layer entirely
- `rewrite`: keep the behavior, but rewrite names, docs, or fields to current AstraBridge wording
- `rename`: current behavior stays, but identifiers should be renamed to remove legacy naming
- `historical-evidence`: keep as explicit history or negative regression evidence
- `false-positive`: scan hit is intentional guardrail text, test fixture data, or internal-only noise that is not the immediate cleanup target

## Current Summary

- Product-facing doc/rule hits are now mostly negative-path warnings or active-plan text, not normal-path product guidance.
- The highest-value cleanup targets are still in sidecar/runtime/Desktop contracts that expose `lcr_*` tool names, SSE event names, evidence field names, preset names, and compatibility routes.
- Old project-format tests are intentionally valuable and should stay as negative coverage.

## Audit Matrix

| Path | Matched content / cluster | Classification | Reason | Responsible step |
| --- | --- | --- | --- | --- |
| `AGENTS.md` | `Research OS Local Codex Router prototype` in repo intro | `rewrite` | Current rule file should describe current product identity without leaning on old prototype branding. | `3.3` |
| `AGENTS.md` | Negative rule mentioning `.lcrproj`, `.lcr`, `.codexproj`, `.codex-shell` | `false-positive` | Intentional guardrail text; it prevents reintroduction of old product paths. | none |
| `README.md` | Negative warning about legacy `.lcrproj`, `.lcr`, `.codexproj`, `.codex-shell` | `false-positive` | Intentional “not supported” product warning, not a normal-path legacy entry. | none |
| `HANDOFF.md` | Negative warning about legacy `.lcrproj`, `.lcr`, `.codexproj`, `.codex-shell` | `false-positive` | Intentional non-goal statement, not stale operator guidance. | none |
| `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` | Many `LCR`, `Research OS`, `.lcrproj`, `.codexproj`, `.codex-shell` mentions | `historical-evidence` | The active cleanup plan must name the legacy targets it is retiring. | none |
| `docs/DEMO_RUNBOOK.md` | “No legacy `.lcr`, `.lcrproj`, `.codexproj`, `.codex-shell`, or `lcr-models` product path appears.” | `false-positive` | This is an acceptance assertion for absence, not a stale product path. | none |
| `docs/RELEASE_CHECKLIST.md` | Legacy scan command containing old path names | `false-positive` | The scan must reference the strings it is checking for. | none |
| `docs/SECURITY_AND_ISOLATION.md` | “official OpenAI account login” negative rule | `false-positive` | This is an intentional prohibition, aligned with current product policy. | none |
| `apps/astrabridge-sidecar/tests/test_sidecar_services.py` | Old project-format rejection tests for `.codexproj` / `.lcrproj` and `.codex-shell` / `.lcr` state | `historical-evidence` | These are important negative tests proving hard cut behavior; do not delete unless replaced by equivalent negative coverage. | `3.2` |
| `apps/astrabridge-sidecar/tests/test_sidecar_services.py` | Imports and assertions for `lcr_web_*`, `lcr.event`, `lcrVerifiedEvidence`, `lcrCompletionQuality`, `LCR`-named checks | `rename` | Test expectations are still tied to legacy public/runtime names and should follow the product-facing rename chain. | `3.3` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` | `LEGACY_BROWSER_SMOKE_TOOL_NAME`, `_LCR_WEB_TOOL_*`, `_normalize_lcr_web_tool_name`, `lcrVerifiedEvidence`, `lcrCompletionQuality`, compatibility aliases | `rename` | This file still carries the main legacy public contract surface. These names are likely visible in API payloads, tool metadata, or event traces. | `3.3` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/server.py` | SSE events `lcr.hello` / `lcr.event`, compatibility routes `/api/router/mcp/preset/lcr-web`, `/api/lcr-web/*` | `rewrite` | These are behavior-level compatibility routes and event names. They should be explicitly removed or reduced once the current AstraBridge contract is the only supported surface. | `3.2` |
| `apps/astrabridge-desktop/src/App.tsx` | EventSource listeners for `lcr.hello` / `lcr.event` | `rewrite` | Desktop still subscribes to old SSE event names for compatibility. Remove after server-side legacy event support is retired. | `3.2` |
| `apps/astrabridge-desktop/src/features/runtime/threadRendering.ts` | `lcrVerifiedEvidence`, `lcrCompletionQuality` fields | `rename` | These legacy field names leak into the desktop event/evidence contract and should be renamed to AstraBridge-neutral names. | `3.3` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_config_service.py` | `lcr_web_preset()`, `apply_lcr_web_preset()`, preset name `lcr_web`, tool names `lcr_web_*` | `rewrite` | This is a current compatibility layer. It needs either deletion or clear relegation behind non-default compatibility routing. | `3.2` and `3.3` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_service.py` and `lcr_web_mcp_server.py` | Legacy module filenames, server/tool names, schema `lcr-web-research-record-v1`, debug env `LCR_MCP_DEBUG_LOG` | `rename` | Internal files may temporarily remain, but externally visible tool/server/schema/env names should be moved to AstraBridge naming. | `3.3` then `4.2` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/checkpoint_service.py` | `EXCLUDED_LCR_LOG_NAMES`, `EXCLUDED_LCR_ASSET_DIR_NAMES` | `rename` | Internal constants still express legacy semantics even though behavior now guards AstraBridge workspace state. | `3.2` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/isolation_audit_service.py` | check names `workspace_no_old_lcr_state`, `workspace_no_old_codex_shell_state` | `rewrite` | The checks are still valid, but names may surface in diagnostics and should be rewritten to “legacy state” wording. | `3.3` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/modal_service.py` | sample file path `lcr-approval-smoke.txt`, normalized log key `lcr_log_read` | `rename` | User-visible examples and modal/tool keys should no longer carry `lcr` naming. | `3.3` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/tool_context_service.py` | `LEGACY_BROWSER_SMOKE_TOOL_NAME = "lcr_browser_smoke"` and `lcr_web_` checks | `rename` | Current context metadata still hard-codes legacy tool names. | `3.3` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/wsl_dependency_service.py` | probe client name `lcr-bootstrap-check` | `rename` | Internal probe naming should not keep legacy branding once cleanup reaches runtime polish. | `3.3` or `4.2` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/yunwu_image_mcp_server.py` and `yunwu_image_service.py` | `lcr-yunwu-image`, `LCR_MCP_DEBUG_LOG`, multipart boundary `lcr-yunwu-*` | `rename` | Current MCP server naming still carries legacy prefixes. | `3.3` |
| `apps/astrabridge-desktop/src/styles.css` | keyframe names `lcr-shimmer-sweep`, `lcr-number-pop` | `rename` | CSS animation names are internal-only, but trivial cleanup candidates once higher-value contract renames are done. | `3.3` or `4.3` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/project_context_service.py` | skip entry `.codex-shell` | `historical-evidence` | This remains a useful exclusion/guard against legacy state contamination. Keep unless replaced by a broader legacy-state abstraction. | `3.2` |
| `apps/astrabridge-sidecar/astrabridge_sidecar/project_tools_service.py` | `SKIP_LCR_DIRS`, `allow_lcr` naming | `rename` | Internal naming still reflects old semantics; behavior should remain but names should become legacy-neutral. | `3.2` |
| `apps/astrabridge-sidecar/tests/test_sidecar_services.py` fixture asset names such as `portal_ice_crystal_lcr.png`, `key_yellow_lcr.png`, git identity `lcr@example.invalid` / `LCR Test` | `false-positive` | These are test fixtures or synthetic identities, not current product path names. Rename only if touched during nearby test cleanup. | optional later |

## Recommended Next Actions

### For step 3.2

Prioritize behavior-level compatibility layers and explicit old project/state handling:

- server compatibility routes and SSE event aliases
- `mcp_config_service` compatibility preset path
- legacy-named internal exclusion constants where the behavior is still valid but the implementation should stop modeling “LCR mode”

### For step 3.3

Prioritize externally visible or contract-like legacy names:

- runtime tool names and aliases
- evidence field names such as `lcrVerifiedEvidence` and `lcrCompletionQuality`
- MCP server/tool/display names
- modal/tool/log example names
- user-visible diagnostic check names

## Non-Goals For This Audit

- No code deletion or renaming was performed here.
- No test expectations were changed here.
- No private paths or secrets are recorded in this audit.
