---
name: Bug reproduction (non-security)
about: Report a reproducible product defect with redacted, bounded evidence.
title: "[bug] "
labels: ""
assignees: ""
---

<!-- astrabridge-feedback-template: bug-reproduction -->
<!-- Do not include credentials, tokens, cookies, authorization headers, vault data, private user data, raw provider payloads, or vulnerability details. -->

## Safety gate

- [ ] This is not a security vulnerability or conduct report.
- [ ] I removed credentials, private data, provider payloads, and raw transport headers.
- [ ] I did not make an unapproved provider-backed or paid request to reproduce this issue.

## Environment

- AstraBridge version or source commit:
- Operating system:
- Python / Node / package versions when relevant:
- Evaluation route: `no-key`, `deterministic fixture`, or another explicitly authorized route:

## Reproduction

1. Exact redacted steps:
2. Expected result:
3. Actual result:
4. Smallest redacted log, screenshot, or artifact reference:

## Route and owner hint

Choose one: `task-graph`, `runtime`, `desktop`, `provider-metadata`, `provider-authority`, `extensions`, `release`, or `documentation`.

## Boundary check

State whether the result affects a documented deterministic path, a reduced-authority provider route, an experimental candidate, or an unverified/release-blocked surface. Do not promote a route in this report.
