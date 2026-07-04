# Ownership Boundaries

Last updated: 2026-06-27

## Product State

AstraBridge-owned project state is limited to:

- `.abproj`
- workspace-local `.astrabridge/`

Legacy `.lcr*`, `.codexproj`, `.codex-shell`, and official OpenAI account-login paths are not supported product state. They may appear only in guardrails, compatibility shims, historical records, or negative tests.

## Subsystem Boundaries

| Area | Owns | Does not own |
| --- | --- | --- |
| `apps/astrabridge-desktop/` | Desktop/web UI, i18n, runtime panels, browser-facing workflows, screenshot QA surfaces. | Provider secrets, official Codex user state, sidecar persistence internals. |
| `apps/astrabridge-sidecar/` | Project/runtime/provider/model APIs, router policy, capability services, local validation, sidecar provenance. | UI layout, committed private artifacts, unsupported official OpenAI account login. |
| `PLAN/` | Execution plans, surface maps, historical progress records. | Raw secrets, runtime logs, long-lived private artifacts. |
| `docs/` | Active operator docs, architecture, governance, security, release, handoff, provenance. | Private demo evidence, raw provider payloads, generated caches. |
| `docs/archive/` | Historical compatibility and archived guidance. | Current product entry points. |
| `PRIVATE/` | Local-only evidence, screenshots, validation artifacts, demo runs, private operator material. | Tracked product source, committed secrets, release assets. |
| `scripts/` | Local automation, validation, audit, capture, and harness helpers. | Product runtime APIs unless explicitly documented. |

## User Mental Model

The user-visible navigation model is:

```text
Project -> Task
```

Runtime lanes, provider threads, handoff routes, and Codex kernel thread ids are internal execution details. They may appear in task activity rows, diagnostics, hover cards, or debug evidence, but they should not become primary left-sidebar navigation.

`Session` / `conversation` is not a user-visible work-unit name in AstraBridge. Old UI copy that used "session" or `会话` to mean a task should be migrated to `Task` / `任务`. The composer/input control may still be called `对话框`.

Codex CLI thread-oriented actions are mapped at the product boundary:

- Codex `new thread` -> AstraBridge `new task`.
- Codex `fork thread` / `branch thread` -> AstraBridge `branch task`.
- Codex `thread_id` -> internal execution-lane id.

## Runtime And Provider Boundaries

- Provider/model selection belongs to AstraBridge provider routing and catalog metadata.
- Sending uses the current task's active provider lane.
- Display uses the task-level composite conversation.
- Web search is a standalone web lane unless a future user request explicitly merges it into model-backed capability routing.
- OpenAI, DeepSeek, Kimi, Qwen, Yunwu, and compatible endpoints are normal configurable API-key providers.

## Compatibility Shims

Compatibility shims must stay small and delegate to canonical AstraBridge implementations. They are allowed only when older preserved evidence, fixtures, or imports still need to load.

Current shim inventory is maintained in:

- `docs/archive/LEGACY_COMPATIBILITY_SHIMS.md`

New implementation work must import canonical AstraBridge modules.
