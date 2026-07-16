---
name: ui-dogfood-browser-readiness
description: Operate and verify AstraBridge UI through the in-app browser using a DOM-first readiness gate, screenshot evidence, and explicit failure classification. Use for any UI dogfood, visual regression, click-driven product validation, or browser-capture failure investigation.
---

# UI Dogfood Browser Readiness

Use this skill whenever a task claims visible AstraBridge behavior, asks for
screenshots, or needs to distinguish an application failure from an in-app
browser automation failure.

## Preserve The Acceptance Boundary

1. Use visible in-app browser actions for product workflows. Do not substitute
   API writes, state injection, or page-evaluate mutation for a click path.
2. Do not claim visual acceptance without a captured screenshot. A usable DOM
   is functional evidence, not visual evidence.
3. Preserve screenshots, DOM-ready notes, failures, and redacted diagnostics
   under the task's existing `PRIVATE/**` evidence root. Never persist keys,
   passwords, cookies, authorization headers, Vault contents, or raw secrets.
4. Treat password and key inputs as no-capture zones. After filling a sensitive
   field, do not request a DOM snapshot, screenshot, console log, value read,
   or broad text extraction until the value is cleared or the app has replaced
   the field. Verify submission with a non-sensitive session/status locator.

## Browser Readiness Gate

Run this sequence before every screenshot-dependent acceptance point.

1. Read the browser-control skill documentation for the current runtime.
2. Call `user.openTabs()` and claim the user-visible AstraBridge tab. Prefer
   it over opening a duplicate URL. Reuse that claimed tab for the whole run.
3. Confirm the URL targets the intended sidecar and inspect a fresh DOM
   snapshot. Require at least one page-specific signal: app shell, selected
   page heading, composer, task graph, or the control being tested.
4. Capture the pre-action screenshot. Perform the UI action with visible
   click/type/drag/hover behavior. Inspect fresh DOM state before the next
   action. Capture the post-action screenshot.
5. For a changed interactive control, capture at least one hover, focus,
   disabled, expanded, or error state when it exists.
6. Before ending, keep the live tab as `handoff` when later work needs it;
   otherwise finalize tabs as the final browser operation.

## Failure Classification

Record exactly one classification before retrying or repairing anything.

| Observation | Classification | Required response |
| --- | --- | --- |
| No user tab or tab cannot be claimed | `browser_tab_unavailable` | Create one local tab only when appropriate; do not diagnose AstraBridge yet. |
| Claimed tab has no readable DOM / webview cannot attach | `browser_webview_unavailable` | Reclaim the same visible tab once. Do not reload or change sidecar until the retry is classified. |
| DOM shows launcher, missing key, wrong project, or anonymous state | `session_or_route_mismatch` | Diagnose the visible session, project, URL, and sidecar. Do not treat it as a screenshot failure. |
| DOM is readable but screenshot capture fails | `browser_screenshot_channel_failure` | Retry one screenshot after a short readiness check. Keep DOM evidence, mark visual acceptance pending, and do not call the product broken. |
| DOM and screenshot show blank/error surface | `app_or_sidecar_surface_failure` | Preserve the visible evidence first, then inspect sidecar/runtime diagnostics. |
| Screenshot shows overlap, clipping, oversized type, card stacking, redundant text, or unclear controls | `product_ui_defect` | Repair the product surface and repeat the same visible flow. |

## Retry Limits And Safety

1. Do not repeatedly reload, reopen, or guess URLs. One reclaim and one
   screenshot retry are the normal maximum for a single readiness point.
2. Do not treat a fresh anonymous sidecar as a substitute for an authenticated
   managed-Vault acceptance run.
3. Do not read plaintext desktop key files merely to recover a browser session.
   Use only a visibly authorized login/Vault flow when the task requires it.
4. Do not issue a live model request to prove a screenshot channel. Keep the
   browser and provider failures independently classified.
5. When the user explicitly authorizes a local password/key read for login,
   keep it in memory only, submit it only to the visible local AstraBridge
   form, clear the field immediately after submission, and clear the in-memory
   variable before any subsequent diagnostic capture.

## Evidence Note

For each readiness gate, record: `app_url`, sidecar port or provenance,
claimed-tab result, DOM signal, screenshot result, classification, visible
actions, provider request count, secret-redaction status, and next entry.

When the screenshot channel alone fails, the correct conclusion is:
`functional DOM evidence available; visual acceptance pending`.
