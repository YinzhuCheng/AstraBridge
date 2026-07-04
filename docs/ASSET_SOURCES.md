# Asset Sources

## Current Status

The current AstraBridge brand-system asset set uses AstraBridge-authored local vectors, code-generated brand primitives, and local-only review artifacts.

No third-party external visual asset is currently relied on by the active Starbridge brand system.

## Repository Visual Asset Inventory

| Asset group | Paths | Provenance | License / usage note | Notes |
| --- | --- | --- | --- | --- |
| App icon source family | `brand/icon-source.svg` | AstraBridge-authored local vector source | Project-owned local asset | Canonical source for the main AstraBridge app icon family. |
| App icon exports | `icons/app-icon.png`, `icons/32x32.png`, `icons/128x128.png`, `icons/256x256.png`, `icons/icon.ico`, `apps/astrabridge-desktop/src-tauri/icons/icon.png`, `apps/astrabridge-desktop/src-tauri/icons/32x32.png`, `apps/astrabridge-desktop/src-tauri/icons/128x128.png`, `apps/astrabridge-desktop/src-tauri/icons/128x128@2x.png`, `apps/astrabridge-desktop/src-tauri/icons/icon.ico` | Derived from `brand/icon-source.svg` | Project-owned local exports | Raster and platform packaging outputs for the canonical app icon. |
| Web favicon | `apps/astrabridge-desktop/public/favicon.svg` | AstraBridge-authored local vector | Project-owned local asset | Simplified favicon used by the desktop web preview. |
| Brand wallpaper accent overlay | `apps/astrabridge-desktop/src/assets/brand-constellation.svg` | AstraBridge-authored local SVG added during the Starbridge wallpaper work | Project-owned local asset | Controlled accent overlay for permissive wallpaper surfaces. This is not a third-party star map. |
| Legacy bootstrap raster icon | `apps/astrabridge-desktop/src-tauri/icons/local-codex-router-icon.png` | Project-owned local raster retained from the initial AstraBridge split | Internal legacy asset; not a third-party brand asset | Keep for compatibility only. Do not reuse as a current Starbridge brand source without an explicit provenance review. |

## Programmatic Brand Assets

The following brand surfaces are generated in code and do not rely on external bitmap packs or third-party icon kits:

- wallpaper base / star / line layers in `apps/astrabridge-desktop/src/styles.css`
- Orion-inspired constellation rendering in `apps/astrabridge-desktop/src/features/brand/StarbridgeCornerConstellation.tsx`
- waiting-state constellation motion in `apps/astrabridge-desktop/src/features/brand/StarbridgeWaitingConstellation.tsx`
- composer rail / star-track rendering in `apps/astrabridge-desktop/src/features/brand/ComposerStarTrack.tsx`
- Starbridge icon family in `apps/astrabridge-desktop/src/features/brand/StarbridgeIcons.tsx`
- cursor glow / star-dust overlay in `apps/astrabridge-desktop/src/features/brand/StarbridgeCursorOverlay.tsx`

These are product code, not external visual-source imports.

## Local-Only Artifacts

The following remain local-only and must not be treated as tracked asset sources:

- screenshots under `PRIVATE/demo-runs/**`
- browser smoke captures
- validation screenshots
- demo workspace artifacts
- raw LLM experiment traces and validation reports under `PRIVATE/**`

These artifacts are preserved for local verification and handoff quality, but they are not part of the committed asset provenance set.

## Provenance Workflow

When a new visual asset enters the product:

1. Prefer AstraBridge-authored vectors, CSS/canvas primitives, or controlled local generation over third-party downloads.
2. If a raster or icon family is exported from a local source asset, record the canonical source file and treat the derived files as exports, not independent origins.
3. If an asset is generated locally with an image model, keep the prompt/run notes or generation report under `PRIVATE/**`, with secrets removed, and record the committed output path here.
4. If any external visual asset is committed, record the exact source URL, file-level license or usage grant, owning step, and where it appears in the product before merge.
5. If provenance or licensing is unclear, the asset must stay local-only or be replaced with an AstraBridge-authored fallback.

## Rules

- Do not commit screenshots or demo captures from `PRIVATE/**`.
- Do not store secrets, raw provider credentials, cookies, or authorization headers in any asset artifact.
- Do not treat review screenshots, browser smoke captures, or validation evidence as committed visual assets.
- If a future step adds external icons, logos, or other committed visual assets, record their source URLs and usage notes here in the same round.
- Use `references/logging_and_artifacts.md` for local-only logging, raw evidence, and artifact-preservation rules.

## Plugin And Skill Icon Policy

- Official plugin/skill icons may be used only from an explicit AstraBridge-reviewed override entry with clear provenance and usage notes.
- Safe manifest-local plugin/skill icons are limited to bundle-local raster assets that stay inside the declaring plugin root or skill root.
- Remote manifest icon URLs are never trusted by default. Only validated official-source URLs are allowed, and they are referenced by URL instead of being durably downloaded into the repo.
- AstraBridge-generated fallback icons are replacement assets, not official brand assets. They are stored only under AstraBridge-managed isolated runtime state and must be labeled as generated fallback provenance in metadata and UI.
- If a future change adds approved official plugin or skill icon assets to the repository, record the exact source URL, license/usage note, and owning step here before release.
