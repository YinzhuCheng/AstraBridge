# AstraBridge Developer Preview Baseline

Status: pre-release baseline. Source evaluation and isolated packaging evidence
are runnable; this is not permission to publish a release, distribute an
installer, or claim a public support/security channel.

Last verified: 2026-07-27

## What This Baseline Establishes

This document separates the developer-facing paths that have evidence from
the things that still require an owner decision or a real distribution
operation. It is the public counterpart to the broader
[release checklist](RELEASE_CHECKLIST.md), not a replacement for it.

| Surface | Current evidence | Boundary |
| --- | --- | --- |
| No-key source evaluation | `demonstrated` | The [No-Key First Ten Minutes](NO_KEY_FIRST_TEN_MINUTES.md) path was run from the exact local source revision `c8988fef6f1139ac056fadb68e395122ee59254a` in a clean Windows environment. It is a deterministic, no-provider fixture path, not an installer test. |
| Release identity and staging | `pass` | A 2026-07-27 readiness run validated release version `0.1.0`, 28 identity bindings, two deterministic staged inventories of 904 files, and the updater contract. It does not prove that an artifact is signed, published, or downloadable. |
| Windows update transaction | `pass` | A 2026-07-27 isolated `canary` rehearsal passed clean staged-bundle checks, update transaction, rollback, and four recovery scenarios. It does not contact a public endpoint or prove a public installer/update service. |
| Public installer or developer-preview release | `blocked` | The legal, private-reporting, conduct, support-intake, distribution, and release-owner gates below remain open. |

The deterministic baseline aggregator is
`scripts/run_developer_preview_baseline_check.py`. It accepts summaries from
the existing release and update gates, emits a compact secret-free evidence
packet, and deliberately classifies the public release as blocked until the
owner gates are resolved.

## Bounded Installation and Fresh-State Route

For a developer trying AstraBridge today, use the source route in
[No-Key First Ten Minutes](NO_KEY_FIRST_TEN_MINUTES.md). It requires the
documented Windows, Python, Node, and npm prerequisites; creates only normal
project state (`.abproj` plus workspace-local `.astrabridge/`); and reaches a
bounded task-graph fixture without a provider account or credential.

That route is the supported evaluation route for this baseline. There is no
public binary download, installer, signed release artifact, or supported
version table yet.

Maintainers can reproduce the package-contract and update-transaction evidence
without publishing anything:

```powershell
cd D:\AstraBridge
python scripts\run_release_readiness_gate.py --artifact-root PRIVATE\rr --run-id preview-rr
python scripts\run_windows_update_rehearsal.py --artifact-root PRIVATE\wu --run-id preview-wu --channel canary
python scripts\run_developer_preview_baseline_check.py `
  --release-readiness-summary PRIVATE\rr\preview-rr\reports\summary.json `
  --windows-update-summary PRIVATE\wu\preview-wu\windows-update-rehearsal\summary.json `
  --output-root PRIVATE\preview-baseline
```

Use short `PRIVATE` artifact roots such as `PRIVATE\rr` and `PRIVATE\wu` on
Windows. The staged source tree is large enough that deeply nested evidence
paths can exceed the host path-length limit; a short root is the reproducible
workaround. Preserve both a failure report and the successful retry as local
diagnostic evidence rather than deleting either.

These commands assess existing source, stage a bounded local workspace, and
simulate an isolated transaction. They do not sign, publish, download, install
to an end-user machine, contact a real update endpoint, or call a model
provider.

## Security, Privacy, and Data Boundaries

The technical boundary is defined by
[Security and Isolation](SECURITY_AND_ISOLATION.md) and the pre-preview
[Security Policy](../SECURITY.md).

| Data or action | Current rule |
| --- | --- |
| Project state | Normal project state is `.abproj` plus workspace-local `.astrabridge/`. Do not substitute official Codex files or legacy project formats. |
| Application and runtime state | AstraBridge uses its own configured app-data, runtime, and Codex-home roots; it must remain isolated from official Codex configuration. |
| Provider credentials and raw transport data | Do not persist plaintext credentials, raw authorization material, or raw secret-bearing transport data in project state, logs, screenshots, reports, or public discussion. |
| Provider activity | Provider calls are optional and require explicit authorization. The no-key route and the release/update evidence summarized here do not establish live provider behavior. |
| Plugins, skills, and metadata | Treat manifests, catalogs, and skill files as untrusted metadata until explicit review and approval; no candidate example gains automatic install or write authority. |
| Evidence retention | Preserve redacted diagnostics and validation artifacts. Never use blind cleanup as recovery, and never add secrets to a report to make it more reproducible. |

There is currently no private vulnerability-reporting route and no private
conduct-reporting route. Those absences are intentionally explicit in
[SECURITY.md](../SECURITY.md) and [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md);
they are release blockers, not an invitation to disclose sensitive details in
public channels.

## Support and Reproduction Before Public Intake

This baseline does not create a public support promise, an active issue tracker
workflow, or a current maintainer response commitment. The local
[Contributor Feedback Protocol](CONTRIBUTOR_FEEDBACK_PROTOCOL.md) now defines
prepared safety templates, routing, and a provider-free cohort rehearsal, but
its `pending_public_intake` status keeps public intake and its future response
expectation disabled. Until the license, private-reporting, and explicit
maintainer-enablement gates are complete, keep a non-sensitive report locally
or use only a maintainer-approved public channel for a non-security discussion.

A reproducible, non-sensitive report should include:

1. AstraBridge version or source commit.
2. Operating system and relevant Python, Node, npm, and package versions.
3. The exact no-key or package-validation command used.
4. Expected result, actual result, and small redacted reproduction steps.
5. Redacted diagnostics, screenshots, and artifact paths where useful.
6. Whether the issue reproduces without a provider credential.

Never put vulnerability details, credentials, access tokens, cookies,
authorization headers, raw provider requests, private user data, or secret
values in an issue, pull request, screenshot, or log. Do not report a
vulnerability publicly while the private route is unconfigured.

## Recovery and Rollback Expectations

For source evaluation, stop the local Desktop/sidecar only after preserving
redacted diagnostics, restore the workspace from the latest valid checkpoint
when applicable, and return to the last known-green source or build artifact.
Follow the broader [release checklist](RELEASE_CHECKLIST.md#rollback-gate) for
the exact evidence note and recovery discipline.

The `canary` rehearsal demonstrated an isolated staged transaction that
commits after a health check and rolls back interrupted `initialized`,
`candidate_staged`, and `activation_written` stages to the prior generation.
It is evidence for the updater design only. It is not a promise that a future
published installer, end-user update, or remote endpoint has the same result
until that real artifact is separately validated.

## Explicit Release Blockers and Owners

| Blocker | Owner | Required resolution before a public release claim |
| --- | --- | --- |
| License, copyright ownership, contribution terms, and third-party notices | Project and legal foundation owner | Select and verify the license, ownership, contribution terms, and required notices described in the [foundation decision record](OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md). |
| Private vulnerability reporting and supported versions | Security maintainer | Configure and test one private reporting route, name a response owner, and publish a supported-version policy in `SECURITY.md`. |
| Private conduct reporting | Conduct-enforcement owner | Configure a monitored private conduct contact and a response expectation in `CODE_OF_CONDUCT.md` or its linked policy. |
| Safe public support and issue triage | Community and maintainer-triage owner | The prepared [Contributor Feedback Protocol](CONTRIBUTOR_FEEDBACK_PROTOCOL.md) supplies local templates, reproduction guidance, routing, and a future response expectation. Keep public intake disabled until the license, private reporting routes, and explicit maintainer ownership are complete and verified. |
| Authorized distribution | Release owner | Approve signing, distribution target, installer clean-user validation, artifact provenance, and a release evidence note before publication. |

The current four-provider reference cohort remains documented and
reduced-authority. Missing live provider smoke blocks any live-provider or
coding-route claim; it does not turn the no-key source route into a provider
test. See [Provider Truth and Authority Surface](PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md)
for the route-specific boundary.

## Claim Boundary

It is accurate to say that AstraBridge currently offers a documented no-key
source evaluation path and that its release identity, deterministic staging,
and isolated update transaction have reproducible local evidence. It is not
accurate to say that AstraBridge has released a public installer, supports a
publicly designated version, provides private security or conduct reporting,
accepts merge-ready external code, or operates a live signed update service.

For a failure-first index across this baseline and the other public evidence
cards, see [Public Quality and Reliability Dossier](PUBLIC_QUALITY_RELIABILITY_DOSSIER.md).
The current DG-OSS-04 outcome is [Developer Preview Readiness Decision](DEVELOPER_PREVIEW_READINESS_DECISION.md): public preview remains paused until the named foundation gates are resolved.
