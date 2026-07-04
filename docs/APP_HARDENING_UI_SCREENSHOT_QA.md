# App Hardening UI Screenshot QA

This document defines the standard screenshot review checklist for
`PLAN/ASTRABRIDGE_APP_HARDENING_EXECUTION_PLAN.md` Step 9 and later UI-facing
hardening rounds.

The checklist is a product evidence gate, not a visual taste note. A UI step is
not complete until screenshots prove the visible surface is readable, stable,
and not misleading at the relevant viewport sizes.

## Required Report Shape

Each UI-facing hardening report should include a `ui_review` object with this
schema marker:

```json
{
  "schema_version": "astrabridge-ui-screenshot-qa-v1",
  "required": true,
  "surface": "runtime",
  "viewports": [
    {
      "name": "desktop",
      "width": 1365,
      "height": 900,
      "screenshot": "PRIVATE/app-hardening/screenshots/example-desktop.png",
      "capture_scope": "page_not_desktop"
    }
  ],
  "checklist": {
    "overflow": { "status": "pass", "evidence": "No horizontal clipping visible." },
    "clipping": { "status": "pass", "evidence": "Labels and buttons render fully." },
    "empty_state": { "status": "not_applicable", "evidence": "Surface is populated." },
    "loading_state": { "status": "pass", "evidence": "No stale loading indicator after wait." },
    "error_state": { "status": "pass", "evidence": "Visible error is specific and actionable." },
    "path_readability": { "status": "pass", "evidence": "Long paths wrap or truncate intentionally." },
    "provider_runtime_labels": { "status": "pass", "evidence": "Provider/runtime labels match API state." },
    "button_semantics": { "status": "pass", "evidence": "Visible actions use clear labels or familiar icons." },
    "narrow_layout": { "status": "pass", "evidence": "Narrow screenshot has no incoherent overlap." }
  },
  "issues_found": [],
  "fixes_applied": [],
  "remaining_risk": []
}
```

Allowed item statuses are:

- `pass`: Screenshot evidence supports the check.
- `fail`: Screenshot evidence shows a defect that should be fixed in the same
  step unless it is explicitly deferred with risk.
- `not_applicable`: The condition is not present on this surface, with a reason.
- `not_checked`: Only allowed for a non-UI step where `required` is false.

## Checklist Items

| Item | Pass condition | Typical failure |
| --- | --- | --- |
| `overflow` | Content stays within its layout region; horizontal scroll is intentional and usable. | Text or panels escape their container, overlap adjacent UI, or hide controls. |
| `clipping` | Labels, headings, badges, chips, and buttons render enough text to be understood. | Button text is cut off, long words are crushed, or badges become unreadable. |
| `empty_state` | Empty states explain what is missing and what the user can do next. | Blank panel, generic “no data”, or stale empty state despite available data. |
| `loading_state` | Loading indicators resolve, or persistent loading states explain the blocker. | Spinner or disabled panel remains without diagnosis after the surface settles. |
| `error_state` | Errors name the failing subsystem and provide a next action or useful evidence. | Generic request failure, raw stack, raw endpoint only, or failure hidden from UI. |
| `path_readability` | Long local paths and artifact URLs wrap, truncate, or occupy a dedicated row without vertical letter stacking. | Path text breaks every character, pushes layout sideways, or hides the filename. |
| `provider_runtime_labels` | Provider, model, sidecar, runtime, route, and session labels match known API state or clearly show `unknown` with context. | UI implies the wrong provider/runtime, hides stale state, or treats unknown as success. |
| `button_semantics` | Buttons and icon actions use familiar icons, labels, disabled states, and clear intent. | Ambiguous commands, duplicate-looking destructive actions, or disabled buttons with no context. |
| `narrow_layout` | At a narrow viewport, content remains scannable and controls remain reachable without incoherent overlap. | Sidebar/content collision, cramped cards, path columns crushed into unreadable fragments, or text covering controls. |

## Capture Requirements

For UI-facing steps:

- Capture at least one desktop viewport screenshot, normally `1365x900`.
- Capture a narrow viewport screenshot when the surface has sidebars, long
  paths, dense tables, cards, provider/runtime labels, or artifact previews.
- Prefer `scripts/capture_astrabridge_page.mjs` for AstraBridge local URLs
  because it captures the page, not the Windows desktop foreground.
- Preserve raw capture reports under `PRIVATE/app-hardening/raw/`.
- After changing `PRIVATE/app-hardening/` evidence or related public docs, run
  `python .\scripts\app_hardening_secret_scan.py --repo .` before treating the
  step as done.
- Do not persist API keys, bearer tokens, cookies, authorization headers, vault
  passwords, admin tokens, provider raw secrets, or desktop key contents in
  screenshots, reports, or raw summaries.
- Secret scanning does not OCR screenshot pixels. Review screenshot content
  manually for leaked credentials, vault material, desktop key paths, or other
  operator-only text.

## Review Rule

If a screenshot exposes a high-impact UI/UX defect on the touched surface,
repair and recapture within the same numbered step. If the defect belongs to a
later planned surface or an older running process, record it as `remaining_risk`
with the exact next entry point.
