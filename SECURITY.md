# AstraBridge Security Policy

## Current Status

This is a pre-preview security policy. AstraBridge has detailed product
security and isolation guidance, but a private vulnerability-reporting channel
has not yet been configured for public use. Do not interpret this file as a
claim that private reporting is currently available.

## Supported Versions

No public developer-preview release is currently designated as supported. A
supported-version table will be published with the first preview after its
release identity, install path, and private reporting route are verified.

## Reporting a Vulnerability

Do not disclose vulnerability details, credentials, access tokens, cookies,
authorization headers, raw provider requests, or personal data in a public
issue, pull request, discussion, screenshot, or log.

Before a public developer preview, the maintainer must configure exactly one
verified private reporting route:

1. a repository-host private vulnerability-reporting feature with a tested
   maintainer notification path; or
2. a dedicated monitored security contact with a documented acknowledgment
   expectation.

After that route is configured, this file must name the exact reporting method
and the supported-version policy before public contributor intake opens.

## Current Product Security Boundaries

The existing [security and isolation guidance](docs/SECURITY_AND_ISOLATION.md)
defines the current technical boundary. In particular, AstraBridge must not
persist plaintext provider credentials, official Codex configuration, or raw
secret-bearing transport data in project state, logs, screenshots, or reports.

For the currently demonstrated source-evaluation and deterministic packaging
scope, read [the developer preview baseline](docs/DEVELOPER_PREVIEW_BASELINE.md).
It does not create a private reporting route or authorize a public release.

The future public route must use the same redaction standard and must not ask a
reporter to send secrets as proof of impact.

## Preview Release Gate

A developer preview must remain blocked if this file still lacks a verified
private reporting method, a maintainer response owner, or a supported-version
statement. See [the foundation decision record](docs/OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md)
for the owner decisions that remain open.
