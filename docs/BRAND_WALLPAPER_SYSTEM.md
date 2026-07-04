# AstraBridge Wallpaper System

Last updated: 2026-07-03

## Purpose

This document defines the first restrained wallpaper system for AstraBridge.

The goal is not decoration for its own sake. The wallpaper layer should make the shell feel recognizably Starbridge while preserving dense, work-focused readability.

## Layer Model

The wallpaper system uses three programmatic layers, plus one controlled accent overlay for permissive surfaces:

1. `base layer`
   - low-contrast cool glow
   - establishes atmospheric depth without visible texture noise

2. `star layer`
   - sparse point field
   - creates the observatory / star-map cue

3. `line layer`
   - faint constellation-like connecting lines
   - only strong enough to be noticed peripherally

4. `accent constellation overlay`
   - explicit Starbridge line structure used only where the UI can tolerate more visible brand presence
   - currently used on settings and launch-isolation style surfaces

The base, star, and line layers are generated in CSS through gradients. The accent overlay uses the local asset `apps/astrabridge-desktop/src/assets/brand-constellation.svg`.

## Current Tokens

Defined in `apps/astrabridge-desktop/src/styles.css`:

- `--wallpaper-base-layer`
- `--wallpaper-star-layer`
- `--wallpaper-line-layer`
- `--wallpaper-cluster-layer`
- `--wallpaper-cluster-layer-secondary`
- `--wallpaper-root-opacity`
- `--wallpaper-root-line-opacity`
- `--wallpaper-sidebar-opacity`
- `--wallpaper-settings-opacity`
- `--wallpaper-empty-opacity`

## Surface Intensity Rules

### Main shell

- Wallpaper is present globally behind the shell.
- It must stay low-contrast and mostly peripheral.
- Primary chat reading and writing surfaces must remain quieter than the background.

### Sidebar

- Stronger than the task workspace.
- Enough to carry Starbridge identity even when the rest of the shell is visually calm.
- Should not make list rows harder to scan.

### Settings / launcher / manager hero

- Stronger than ordinary task surfaces.
- These are acceptable places to show more obvious brand layering.
- Still must avoid poster-like hero treatment.
- If screenshot review shows the CSS-only layer is too subtle, these surfaces are allowed to use the explicit constellation overlay.

### Empty states

- Can use a slightly stronger star/line signal than busy work surfaces.
- Should help the empty state feel intentional rather than sterile.

## Constraints

1. No wallpaper layer may interfere with text contrast.
2. No wallpaper layer may block interaction or add pointer noise.
3. Narrow layouts should reduce line intensity first before reducing base readability.
4. Main task content must remain calmer than sidebar, settings, and launcher surfaces.
5. This wallpaper system is not a substitute for the later edge, icon, motion, or cursor steps.
6. Explicit constellation structure should stay off dense reading surfaces unless a later step proves it can remain quieter than the content.

## Out of Scope

This document does not define:

- bitmap wallpaper assets
- animated background motion
- branded waiting-state animations
- cursor effects
- icon language

Those belong to later steps in `PLAN/ASTRABRIDGE_BRAND_SYSTEM_EXECUTION_PLAN.md`.
