# AstraBridge Icon System

Last updated: 2026-07-03

## Purpose

This document defines the first stable icon-language rules for AstraBridge.

The goal is to stop ad hoc icon swaps and make later replacement work consistent across the sidebar, topbar, composer, inspector, browser, files, and setup surfaces.

This step does not yet redesign the full icon library. It defines the rules, the semantic families, and the ban list that Step 10 and later steps must follow.

## Near-Term Strategy

1. Keep the product on a single outline-based family while the Starbridge-specific shapes are introduced.
2. Treat current `lucide-react` icons as temporary geometry donors, not as the finished brand language.
3. Replace raw Unicode symbols before inventing decorative one-off icons.
4. Replace icons in clusters, not one by one:
   - primary navigation cluster
   - mode-switching cluster
   - high-frequency composer cluster
   - inspector entry cluster

## Product Semantics

User-facing icon language should reflect current AstraBridge terminology:

- `Project` is the outer container.
- `Task` is the main user-facing work unit.
- Internal execution `thread` / `lane` concepts are runtime details and should not dominate the visible icon language.
- `Conversation` remains a composer/message concept, not the primary sidebar hierarchy term.

This means future icons should emphasize project, task, route, relay, review, and observation semantics rather than generic chat-app thread metaphors.

## Visual Rules

### 1. Geometry

- Default working sizes: `14px`, `15px`, `16px`
- Default stroke: `1.8` to `1.9`
- Only the most prominent primary-nav icon may use `2.0`
- No filled glyphs as the baseline family
- No emoji-like silhouettes
- Corners should stay slightly softened, not round and cute

### 2. Optical behavior

- Icons should read clearly at narrow sidebar widths and dense toolbars.
- Details should survive on pale backgrounds without needing thick outlines.
- A glyph must still read when rendered in a single ink color.
- Motion, glow, or background chrome must never be required to understand the icon.

### 3. Color behavior

- Rest state: ink/silver-blue neutral
- Hover: edge contrast first, color shift second
- Active: limited cool-blue emphasis
- Warning/error: warm state tint, but do not introduce a separate icon family
- Disabled: lower contrast only; do not swap to a different visual style

### 4. Surface discipline

- Main task canvas uses the quietest icon treatment.
- Sidebar and inspector may use slightly stronger edge contrast.
- Setup surfaces may tolerate clearer branding, but still no thick capsules or novelty glyphs.

## Semantic Families

### 1. Observatory

Used for app-level entry points and observation surfaces.

Examples:

- app home / workspace view
- status
- browser
- files
- settings overview

Preferred motifs:

- frame
- lens
- panel
- observation reticle

### 2. Relay / Bridge

Used where AstraBridge should feel distinct from a generic SaaS app.

Examples:

- handoff
- route switch
- goal progression
- send / dispatch
- managed session status

Preferred motifs:

- route segment
- bridge span
- node-to-node transfer
- directional relay

### 3. Project / Task

Used for the user-facing hierarchy.

Examples:

- project
- task
- archived task
- forked task

Preferred motifs:

- structured folder for project
- checklist / workboard for task
- branch-marked task for fork

Avoid making tasks look like casual chat threads.

### 4. Mode and Trust

Used for permission mode, workflow mode, review state, and guarded execution.

Examples:

- ask
- auto
- full access
- default mode
- plan mode
- goal mode

Preferred motifs:

- verification
- autonomous relay
- open gate
- route board
- trajectory

### 5. Payload and Capture

Used for attachments, voice, files, folders, and multimodal entry points.

Examples:

- add attachment
- file
- folder
- image
- voice transcribe

Preferred motifs:

- clip / intake
- file sheet
- folder frame
- waveform / microphone kept minimal

### 6. Inspection and Review

Used for inspector tabs and detailed runtime controls.

Examples:

- review
- browser navigation
- file count
- reload
- external open

Preferred motifs:

- compare rail
- scoped navigation arrows
- refresh orbit
- outward launch

## Banned Styles

The following styles are explicitly banned from future branded UI:

1. Raw Unicode UI symbols used as permanent icons, including:
   - `●`
   - `□`
   - `✎`
   - `×`
   - `↑`
2. Mixed outline and filled icons inside the same high-frequency control group without a semantic reason
3. Generic heavy-pill SaaS badges used to compensate for weak icon semantics
4. Cute or playful illustration-style glyphs in task, review, browser, or settings surfaces
5. Thick dark outlines that only work on white cards
6. Color-dependent icons that fail when rendered in a single ink tone

## Replacement Rules

1. Replace banned legacy symbols first.
2. Replace primary navigation before lower-frequency settings details.
3. Replace mode pickers as a single cluster so permission and workflow language stay coherent.
4. Replace composer controls as a single cluster so add/voice/send actions feel intentional together.
5. Replace inspector entry points before inspector secondary buttons.
6. When a surface already uses a stable glyph but the semantics are weak, prefer semantic improvement over ornamental customization.

## State Rules

Every replacement should be checked in at least these states:

- rest
- hover
- active or selected
- disabled when applicable
- compact/narrow layout where applicable

For mode pickers and menu rows, also verify:

- trigger button
- open menu row
- selected row marker
- tooltip / detail card

## Implementation Guidance For Step 10+

1. Start from the Tier 1 matrix in `docs/BRAND_ICON_REPLACEMENT_MATRIX.md`.
2. Remove raw Unicode symbols from visible shell UI before refining secondary inspector controls.
3. Introduce Starbridge-specific SVGs only where the default outline metaphor is not enough:
   - managed session status
   - goal mode
   - send / dispatch
   - task fork / route branch
4. Keep the code path additive-first:
   - reuse `lucide-react` where the semantic fit is already good
   - add local brand SVG components only where needed
   - do not break existing payloads or runtime behavior for purely visual changes

## Out of Scope

This document does not yet define:

- the final SVG asset pack
- cursor overlay shapes
- waiting animation node glyphs
- per-provider logos

Those belong to later execution steps.
