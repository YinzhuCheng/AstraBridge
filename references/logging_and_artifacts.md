# Logging And Artifact Preservation

Last updated: 2026-06-27

## Default Rule

Preserve experiment artifacts by default. Do not clean intermediate files, caches, logs, raw LLM request payloads, raw LLM responses, parsed outputs, screenshots, validation reports, or demo runs unless the user explicitly asks for cleanup and names the target paths.

## Secret Safety

Artifacts must not contain:

- API keys
- bearer tokens
- cookies
- authorization headers
- provider raw secrets
- plaintext vault passwords

For grading, OCR, LLM, provider, or browser experiments, save enough redacted call records to reproduce the result without storing secrets.

## Where Artifacts Belong

- `PRIVATE/**`: local-only screenshots, demo runs, smoke captures, raw validation evidence, operator-only traces.
- `docs/**`: stable documentation, summaries, public provenance, and secret-safe conclusions.
- `PLAN/**`: execution plans and progress records, not raw payload dumps.
- `scripts/**`: reusable helpers, not run-specific outputs.

## Handoff Notes

When a substantive round adds artifacts, record:

- what was produced
- where it was stored
- whether it is local-only
- whether it was redacted
- which verification command or screenshot proved it

Do not write results back to external platforms unless the user explicitly approves writeback.
