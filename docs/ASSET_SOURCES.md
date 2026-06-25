# Asset Sources

## Current Status

No new external visual assets have been added during the current cleanup/normalization phase.

## Local-Only Artifacts

The following remain local-only and must not be treated as tracked asset sources:

- screenshots under `PRIVATE/demo-runs/**`
- browser smoke captures
- validation screenshots
- demo workspace artifacts

These artifacts are preserved for local verification and handoff quality, but they are not part of the committed asset provenance set.

## Rules

- Do not commit screenshots or demo captures from `PRIVATE/**`.
- Do not store secrets, raw provider credentials, cookies, or authorization headers in any asset artifact.
- If a future step adds external icons, logos, or other committed visual assets, record their source URLs and usage notes here.

## Plugin And Skill Icon Policy

- Official plugin/skill icons may be used only from an explicit AstraBridge-reviewed override entry with clear provenance and usage notes.
- Safe manifest-local plugin/skill icons are limited to bundle-local raster assets that stay inside the declaring plugin root or skill root.
- Remote manifest icon URLs are never trusted by default. Only validated official-source URLs are allowed, and they are referenced by URL instead of being durably downloaded into the repo.
- AstraBridge-generated fallback icons are replacement assets, not official brand assets. They are stored only under AstraBridge-managed isolated runtime state and must be labeled as generated fallback provenance in metadata and UI.
- If a future change adds approved official plugin or skill icon assets to the repository, record the exact source URL, license/usage note, and owning step here before release.
