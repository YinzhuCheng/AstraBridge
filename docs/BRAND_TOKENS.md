# AstraBridge Brand Tokens

Last updated: 2026-07-03

## Purpose

This document defines the first stable token layer for AstraBridge's brand system.

The intent is to stop ad hoc UI restyling. New UI work should first consume these tokens, then add surface-specific adjustments only where needed.

## Token Layers

### 1. Brand palette

These tokens define the visual identity baseline:

- `--brand-sky-*`: cool background ramp
- `--brand-ink-*`: primary and secondary text ramp
- `--brand-accent-*`: primary interaction blue
- `--brand-success-500`
- `--brand-danger-500`

These values may vary by `data-appearance`, but the naming stays stable.

### 2. Material tokens

These tokens define how AstraBridge surfaces feel:

- `--brand-glass-strong`
- `--brand-glass`
- `--brand-glass-muted`
- `--brand-glass-raised`
- `--brand-edge-soft`
- `--brand-edge-strong`
- `--brand-edge-accent`
- `--brand-shell-shadow`
- `--brand-float-shadow`
- `--brand-highlight`
- `--brand-blur`

Use these for shell surfaces, menus, inspector chrome, and future branded overlays.

### 3. Semantic app tokens

These remain the main consumption layer for most components:

- `--bg`
- `--panel`
- `--panel-2`
- `--text`
- `--muted`
- `--accent`
- `--surface`
- `--surface-subtle`
- `--sidebar-bg`
- `--workspace-bg`
- `--inspector-bg`
- `--control-bg`
- `--control-active-bg`

If a component already uses these semantic tokens, prefer keeping that contract.

### 4. Shell interaction tokens

These tokens are for layout chrome and high-frequency navigation behavior:

- `--shell-surface`
- `--shell-surface-strong`
- `--shell-sidebar-surface`
- `--shell-divider`
- `--shell-divider-strong`
- `--shell-hover`
- `--shell-active`
- `--shell-active-strong`
- `--shell-kbd-bg`
- `--shell-kbd-border`
- `--shell-count-bg`
- `--shell-count-border`
- `--shell-tab-active`
- `--shell-menu-popover`
- `--shell-menu-hover`

## Usage Rules

1. Prefer semantic tokens in ordinary component code.
2. Use `--brand-*` tokens when creating a new surface primitive or a reusable visual language rule.
3. Use `--shell-*` tokens for sidebar, topbar, inspector, menus, pills, counts, and similar chrome elements.
4. Do not introduce new raw color values into shell UI unless the token layer cannot express the requirement.
5. If a new appearance theme is added, override the brand palette first, not individual component selectors.
6. Background systems, icon systems, cursor overlays, and waiting animations should build on these tokens instead of introducing isolated palettes.

## Out of Scope

This token layer does not yet define:

- constellation wallpaper assets
- cursor/trail rendering
- waiting animation timing
- icon geometry

Those belong to later execution steps in `PLAN/ASTRABRIDGE_BRAND_SYSTEM_EXECUTION_PLAN.md`.
