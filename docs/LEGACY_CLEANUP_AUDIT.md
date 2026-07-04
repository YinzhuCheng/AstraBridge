# Legacy Cleanup Audit

Last updated: 2026-06-27

## Purpose

This audit classifies legacy-string matches so future agents can distinguish current product facts from historical evidence, guardrails, and compatibility shims.

## Current Product Boundary

- Normal project format: `.abproj`
- Normal workspace state: `.astrabridge/`
- OpenAI is a normal API-key provider, not an official account-login path
- Official Codex state such as `~/.codex/config.toml` and project `.codex*` files is not a normal AstraBridge write target
- `PRIVATE/**` and preserved demo/validation evidence are retained by default

## Classification Rules

- `guardrail`: text intentionally names unsupported legacy paths so they are not reintroduced
- `historical-evidence`: preserved plans, audit notes, or negative tests
- `compatibility-shim`: a small delegating module or route kept only for older private imports or preserved evidence
- `current`: canonical AstraBridge implementation or documentation
- `cleanup-candidate`: old naming that should be renamed when touching the nearby code

## Current Summary

- Product-facing docs should describe AstraBridge names and paths.
- Historical plans under `PLAN/**` may mention old names as evidence, but they are not current entry points unless their progress block says otherwise.
- Web-lane implementation ownership is canonicalized:
  - current MCP implementation: `apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_web_mcp_server.py`
  - current service implementation: `apps/astrabridge-sidecar/astrabridge_sidecar/web_tool_service.py`
  - legacy modules `lcr_web_mcp_server.py` and `lcr_web_service.py` are compatibility shims only
- The previously mojibake dogfood plans have been rewritten as readable current-state records.
- Old project-format rejection tests remain valuable negative coverage.

## Audit Matrix

| Path or cluster | Classification | Current handling |
| --- | --- | --- |
| `AGENTS.md` / `README.md` / `docs/SECURITY_AND_ISOLATION.md` negative mentions of `.lcrproj`, `.lcr`, `.codexproj`, `.codex-shell`, or official OpenAI login | `guardrail` | Keep as prohibitions, not product guidance. |
| `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` | `historical-evidence` | Completed normalization record; do not reopen as the active plan unless the user explicitly asks to revise that record. |
| Dogfood and capability execution plans that mention older file paths in completion records | `historical-evidence` | Keep records intact; add newer notes instead of rewriting preserved evidence. |
| `apps/astrabridge-sidecar/tests/test_sidecar_services.py` old project/state rejection tests | `historical-evidence` | Keep unless equivalent negative coverage replaces them. |
| `apps/astrabridge-sidecar/tests/test_web_lane.py` and web helper tests | `current` | Tests target `astrabridge_web_mcp_server` and `web_tool_service`. |
| `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_mcp_server.py` | `compatibility-shim` | Delegates to `astrabridge_web_mcp_server`; no new logic belongs here. |
| `apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_service.py` | `compatibility-shim` | Delegates to `web_tool_service`; no new logic belongs here. |
| `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py` old `lcr minimal visual mode:` prefix | `compatibility-shim` | Kept only so preserved threads get readable visual-review titles; new content should use `astrabridge minimal visual mode:`. |
| `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` legacy-named aliases or evidence fields | `cleanup-candidate` | Rename opportunistically only with focused tests because payload compatibility may be involved. |
| `apps/astrabridge-sidecar/astrabridge_sidecar/server.py` old SSE event aliases or old compatibility routes | `cleanup-candidate` | Keep only when needed for old clients or preserved evidence; prefer current AstraBridge routes/events. |
| `apps/astrabridge-desktop/src/App.tsx` old event aliases | `cleanup-candidate` | Remove only after sidecar aliases are retired and UI tests cover current event names. |
| CSS animation names with legacy prefixes | `current` | Renamed to `astrabridge-*` keyframes. |

## Rules For Future Changes

- Do not add new product behavior to `lcr_*` modules.
- Do not create new public routes, event names, fields, or tool names with legacy prefixes.
- Prefer adding a tiny explicit shim over leaving old implementation bodies in old module names.
- When a compatibility shim is reduced or removed, update [LEGACY_COMPATIBILITY_SHIMS.md](/D:/AstraBridge/docs/archive/LEGACY_COMPATIBILITY_SHIMS.md).
- Keep scans secret-safe and exclude `PRIVATE/**`, build outputs, and dependency directories unless the user names a specific target.
