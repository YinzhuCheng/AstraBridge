# Legacy Compatibility Shims

Last updated: 2026-06-27

## Purpose

This archive records legacy entry points that remain only to keep old private runs, preserved evidence, or transitional imports readable. These names are not product architecture and must not be used for new implementation work.

## Current Rule

- New code imports AstraBridge-named modules and APIs.
- Legacy modules stay small and delegate to canonical implementations.
- Tests should target canonical modules unless the test is explicitly proving a compatibility shim still imports.
- Historical plans may mention old names as evidence; active docs should describe current AstraBridge names.

## Archived Shim Inventory

| Legacy entry point | Canonical implementation | Status | Notes |
| --- | --- | --- | --- |
| `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_mcp_server.py` | `apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_web_mcp_server.py` | shim only | The legacy module now aliases the canonical module object so monkeypatches and old imports resolve to the same implementation. |
| `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_service.py` | `apps/astrabridge-sidecar/astrabridge_sidecar/web_tool_service.py` | shim only | Kept for older imports; the service class source of truth is `AstraBridgeWebService`. |
| `lcr minimal visual mode:` thread-title prefix | `astrabridge minimal visual mode:` | parser compatibility only | `task_service.py` accepts the old prefix only to keep preserved threads readable. New prompts and tests should use the AstraBridge prefix. |

## Do Not Revive

Do not reintroduce these as active product paths:

- `.lcrproj`
- `.lcr/`
- `.codexproj`
- `.codex-shell/`
- official OpenAI account login as an AstraBridge product auth path

Guardrail docs and negative regression tests may mention these strings only to prove they are rejected or unsupported.

## Governance Check

`scripts/repo_governance_check.py` treats this archive, historical plans, compatibility shim files, and negative tests as allowed contexts for legacy names. New active code that introduces legacy product paths outside those contexts should fail the local governance gate.
