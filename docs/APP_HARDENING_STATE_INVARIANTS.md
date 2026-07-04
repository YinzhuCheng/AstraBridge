# AstraBridge App Hardening State Invariants

## Purpose

This document is the Step 3 baseline for the app-hardening plan. It turns the
first dogfood mismatches into explicit product state invariants and maps each
invariant to the later hardening steps that should enforce it.

Scope:

- Project, task, runtime thread, provider thread, project context, automation,
  inbox, and artifact state.
- User-visible restore, handoff, conversation rendering, automation recovery,
  and evidence/reporting behavior.
- Security and retention expectations for reports, screenshots, and raw
  summaries.

Terminology note: in this document, `runtime thread`, `provider thread`, and
`thread id` are internal execution-lane concepts. User-visible navigation is
Project -> Task. The composer/input control may still be called the dialog
box, but a user work unit is never called a session or thread in product copy.

This is a checklist and contract document. Step 4 and later steps implement,
test, and polish the behavior.

## Entity Relationship Map

Project:

- Owns the current project identity, active workspace, current task id, current
  thread id, default runtime settings, and durable `.abproj` /
  workspace-local `.astrabridge/` state.
- Must be the source of truth for which task and visible execution lane the UI
  restores after app reload, sidecar reload, or provider switch.

Task:

- Represents the user-visible objective.
- Owns provider thread entries, branch-task entries, handoff events, context
  references, goal records, plan records, and checkpoints.
- Should remain stable when the provider/runtime route changes; provider
  changes create or update provider thread entries, not a new user-visible task
  unless the user explicitly asks for one.

Provider thread:

- Represents a runtime/Codex thread bound to a task and a provider route.
- Exactly one provider thread should be active for the current task when at
  least one live provider thread exists.
- Route metadata is part of the thread entry and must survive restore,
  conversation decoration, context pack generation, and UI rendering.

Runtime thread cache:

- Represents the execution projection returned by the runtime layer.
- May contain native thread status, cached shell settings, turns, and coding
  events.
- Task metadata is allowed to override or enrich this projection during
  decoration so restored UI state stays aligned with product state.

Project context pack:

- Must describe the active task and active provider route.
- Default runtime settings are useful fallback context, but must not hide the
  actual active provider route after handoff or thread restore.

Automation:

- Owns automation definitions and run records.
- Each run is either controlled by a live executing process or is in a durable
  terminal state with a diagnostic reason.
- Run finalization may create artifacts and inbox items when triage says the
  result requires review.

Inbox:

- References an automation id, run id, disposition, and optional artifact.
- Must be resolvable back to the run and retain enough state for the user to
  understand why the item exists.

Artifact:

- References controlled workspace output such as reports, screenshots, media,
  generated summaries, or validation records.
- Must not expose raw secrets. Secret-bearing request payloads, headers, vault
  material, cookies, and authorization values are never valid artifact content.

## Core Invariants

STATE-001 Project/task pointer consistency:
The current project, current task id, and active execution-lane id must point
to the same user-visible task after app reload, sidecar reload, provider lane
switch, or project restore.

STATE-002 Thread ownership uniqueness:
A runtime thread id must belong to at most one task provider/fork entry. If a
restore path discovers an existing owner, it must switch to that owner rather
than duplicating ownership.

STATE-003 Active provider thread ownership:
The active provider thread id for the current task must reference an entry in
that task's provider threads. If no live thread exists, the fallback must be
explicit and diagnostic.

STATE-004 Route metadata preservation:
Provider id, model id, reasoning/tool metadata, and route hints must be
preserved when binding, restoring, decorating, or listing provider threads,
unless the user or runtime explicitly records a route change.

STATE-005 Handoff event completeness:
A provider handoff must bind the target thread to the task, make the target
thread active, and record source route, target route, reason, and time in a
handoff event.

STATE-006 Missing-thread fallback transparency:
If the active provider thread is missing from runtime storage, the task entry
must mark the thread as missing with a reason and time. UI and reports must show
this as recoverable diagnostic state rather than silently rendering the wrong
task.

STATE-007 Conversation renderability:
If the API returns renderable turns, the UI must not show a misleading empty
conversation state. If renderability fails, the UI must expose an actionable
diagnostic that distinguishes no messages, stale runtime error, parse failure,
and missing thread.

STATE-008 Stale runtime error normalization:
Runtime status such as stale `systemError` or `notLoaded` may be normalized to
idle only when the latest durable turn completed cleanly and the raw status is
still available for diagnostics.

STATE-009 Active route context clarity:
Context packs and task handoff summaries must include an explicit active
provider route line. Default runtime settings may appear as defaults, not as the
current route when they differ.

STATE-010 Automation running-run recovery:
A run in `running` state must either be owned by the current executing process
or be recovered to a terminal failed/interrupted state with a durable diagnostic
reason.

STATE-011 Automation artifact and inbox traceability:
Terminal automation runs that need user review must have resolvable artifact
and inbox references. Cancelled, failed, interrupted, and needs-review paths
must be distinguishable in API and UI state.

STATE-012 Artifact path and redaction safety:
Artifacts, screenshots, media previews, and raw summaries must stay within
allowed workspace/product paths and must pass redaction checks before becoming
public docs or staged changes.

## First-Round Dogfood Mismatches

Old task restore:

- Symptom: after provider lane switching, the UI could restore an older task
  or display state that did not match the active runtime execution lane.
- Related invariants: STATE-001, STATE-002, STATE-003, STATE-006.
- Next enforcement point: Step 4 task/execution-lane/provider-thread restore tests,
  followed by Step 8 sidecar provenance checks.

Empty conversation:

- Symptom: a conversation with API-visible content could render as an empty or
  misleading state in the UI after runtime/status drift.
- Related invariants: STATE-007, STATE-008.
- Next enforcement point: Step 5 conversation terminal/empty/error state
  hardening.

Handoff context:

- Symptom: provider handoff context could be ambiguous when default runtime
  settings differed from the active provider route.
- Related invariants: STATE-004, STATE-005, STATE-009.
- Next enforcement point: Step 4 restore coverage, Step 6 provider capability
  contract, and Step 19 cross-surface UI polish.

Automation stuck running:

- Symptom: interrupted automation runs could remain visibly running or lack a
  clear review artifact/inbox trail.
- Related invariants: STATE-010, STATE-011.
- Next enforcement point: Step 16 success-path finalization and Step 17
  stuck/interrupted watchdog hardening.

Artifact/media preview drift:

- Symptom: artifact and media preview paths need consistent path safety,
  preview layout, and durable evidence records.
- Related invariants: STATE-011, STATE-012.
- Next enforcement point: Step 12 artifact/media preview and path security.

Provider metadata compatibility:

- Symptom: provider-specific route metadata, health, and usage signals were not
  consistently visible across runtime/provider/UI/report surfaces.
- Related invariants: STATE-004, STATE-009, STATE-012.
- Next enforcement point: Step 6 runtime/provider contract and Step 7
  provider health, route preview, and token/cost reporting.

## Test And Checklist Matrix

| Invariant | Verification target | Later step |
| --- | --- | --- |
| STATE-001 | Project reload restores matching current task and visible execution lane | Step 4 |
| STATE-002 | Existing thread owner is reused instead of duplicated | Step 4 |
| STATE-003 | Active provider thread always belongs to current task | Step 4 |
| STATE-004 | Provider route metadata survives bind/restore/decorate/list | Step 6 |
| STATE-005 | Handoff creates a complete event and activates target thread | Step 4 |
| STATE-006 | Missing active thread produces explicit diagnostic fallback | Step 4 |
| STATE-007 | Renderable API turns never show misleading empty UI state | Step 5 |
| STATE-008 | Stale runtime errors normalize only with clean completed turn | Step 5 |
| STATE-009 | Context pack includes active provider route separately from defaults | Step 6, Step 19 |
| STATE-010 | Orphaned running automation is recovered to terminal diagnostic state | Step 17 |
| STATE-011 | Review-worthy terminal runs resolve to artifact/inbox evidence | Step 16, Step 17 |
| STATE-012 | Artifact/report/screenshot paths and content pass redaction checks | Step 12, Step 18 |

## Later-Step References

- Step 4 should turn STATE-001 through STATE-006 into sidecar and UI restore
  coverage.
- Step 5 should turn STATE-007 and STATE-008 into conversation rendering tests
  and screenshots.
- Step 6 and Step 7 should turn STATE-004 and STATE-009 into provider contract,
  health, and usage signal coverage.
- Step 8 should make sidecar provenance visible enough to debug restore and
  route mismatches.
- Step 12 should enforce STATE-012 for artifact/media previews and path safety.
- Step 16 and Step 17 should enforce STATE-010 and STATE-011 for automation
  success, cancel, fail, and interrupted paths.
- Step 18 should apply secret-scan and redaction checks to all public docs and
  durable evidence.
- Step 19 should verify that the user can understand these states from the UI
  without reading raw API responses.

## Security Notes

- Public docs may describe state contracts, sanitized provider/model labels, and
  aggregate usage signals.
- Public docs must not include API keys, bearer tokens, cookies, authorization
  headers, raw vault material, admin/session tokens, or provider raw secrets.
- Private raw summaries should be retained for reproducibility, but they still
  need redaction before being promoted to public docs or staged changes.
