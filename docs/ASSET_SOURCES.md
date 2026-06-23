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
