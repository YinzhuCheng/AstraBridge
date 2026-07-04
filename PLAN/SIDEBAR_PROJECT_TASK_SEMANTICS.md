# AstraBridge Project / Task / Lane Semantics

Last updated: 2026-06-27

## Summary

AstraBridge user navigation is `Project -> Task`.

`Session` / `conversation` is not a product-level work unit. When old UI or docs used "session" to mean a user-visible work item, it must now be called `Task`. The Chinese UI may keep `对话框` for the composer/input control, but must not use `会话` as a task synonym.

Runtime `thread` ids still exist because AstraBridge integrates with Codex CLI/app-server semantics. They are internal execution lanes inside a task and should be hidden from ordinary users.

## Product Model

- Project: workspace boundary plus `.abproj`.
- Task: the user-visible unit of work inside a project. A project contains many tasks.
- Conversation view: the center pane for one task. It merges messages from that task's execution lanes.
- Execution lane: one provider/model/runtime route inside a task. It is backed by a Codex runtime thread id, but the UI should call it an execution lane.
- Provider handoff: switching the active execution lane inside the same task.

## Codex CLI Mapping

Codex CLI uses `thread` as a user-facing work unit. AstraBridge does not.

When adapting Codex CLI/app-server features:

- Codex `new thread` -> AstraBridge `new task`.
- Codex `fork thread` / `branch thread` -> AstraBridge `branch task`.
- Codex runtime `thread_id` -> AstraBridge internal execution-lane id.
- Codex thread status and events -> AstraBridge task activity / diagnostics.

Different user-visible AstraBridge tasks normally correspond to different runtime thread ids. Within one task, provider/model switches may create or activate additional runtime thread ids, but those ids stay inside the task and are shown as lane-switch activity rows rather than sidebar items.

## UI Rules

- Left sidebar title is `Projects & tasks` / `项目与任务`.
- Left sidebar renders only project rows and task rows.
- Task rows show title and relative time only.
- Thread/lane counts, active provider/model, missing lane, handoff, and checkpoint metadata belong in hover cards, diagnostics, or activity rows.
- Center pane title and empty states refer to the current task, not the active execution lane.
- Composer/input may be called `对话框`; this is a control name, not a product data model.
- If a technical detail must mention `thread_id`, place it in developer/debug evidence, not primary UI copy.

## Implementation Rules

- Do not rename runtime payload fields such as `thread_id`, `active_provider_thread_id`, or generated Codex protocol types unless a dedicated migration plan owns that change.
- Keep `/api/projects/sidebar` additive and backward-compatible; it may return `threads` for hover/debug compatibility, but frontend navigation must not render them as a third level.
- `TaskConversationService.conversation(...)` is the visible source for task messages.
- Sending, handoff, goal, compact, and recovery operations may still target the current task's active provider thread internally.
- New user-visible actions should be named task actions: `New task`, `Branch task`, `Rename task`, `Archive task`.
