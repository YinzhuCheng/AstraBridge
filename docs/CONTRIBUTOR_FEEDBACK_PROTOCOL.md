# Contributor Feedback Protocol

Status: pre-preview rehearsal protocol. The local templates and cohort make
feedback reproducible, but they do not activate public issue intake, create a
private reporting route, select a license, name a maintainer, or accept
merge-ready external code.

Last verified: 2026-07-27

## Current Boundary

The repository is pre-license. A developer may prepare a bounded, non-sensitive
proposal, documentation correction, or deterministic reproduction. They must
not publish vulnerability details, conduct reports, credentials, raw provider
traffic, private user data, or merge-ready external code through this protocol.

The authoritative policy remains [CONTRIBUTING](../CONTRIBUTING.md),
[SECURITY](../SECURITY.md), [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md), and the
[Open-Source Foundation Decision Record](OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md).
If the question is security- or conduct-sensitive, do not use a public issue
or discussion. No private route has been configured yet.

## Local Feedback Templates

The repository contains these local GitHub-compatible templates under
`.github/ISSUE_TEMPLATE/`. `config.yml` disables blank issues so the prepared
surface cannot silently bypass the safety prompts.

| Template | Use only for | Owner routing hint | Not a claim of |
| --- | --- | --- | --- |
| `issue-feedback.md` | Non-sensitive bounded product observation | Documentation, task graph, Desktop, runtime, provider metadata, extensions, release, or public claim | Current public support commitment |
| `bug-reproduction.md` | Redacted, non-security reproduction | Task graph, runtime, Desktop, provider metadata/authority, extensions, release, or documentation | A provider-backed smoke or automatic route promotion |
| `feature-proposal.md` | Bounded product/design discussion | Named subsystem owner and public-claim owner | Permission to submit merge-ready code |
| `documentation-evidence.md` | Evidence, wording, date, ownership, or limitation correction | Documentation or public-claim owner | A route or installer promotion without evidence |
| `first-contribution-proposal.md` | Pre-license candidate/rehearsal | Skill/orchestration/extensions or other named owner | Plugin auto-enablement, tool authority, or code-intake approval |

The templates can be reviewed locally now. A repository owner must explicitly
enable public intake only after the foundation and safety gates are complete.

## Non-Sensitive Intake Gate

Every feedback item must contain:

1. One bounded goal or defect.
2. Source commit/version, operating system, and exact redacted steps.
3. Expected and actual result, plus the smallest secret-free artifact or
   public source reference needed to inspect it.
4. One likely subsystem route and any compatibility, authority, migration, or
   public-claim consequence.
5. An explicit statement when the evidence is no-key, deterministic,
   reduced-authority, warning-gated, blocked, or unverified.

Never request a credential, a paid provider call, raw provider payload, a
private security/conduct disclosure, or an outside writeback merely to make a
report more complete.

## Routing and Review Rules

| Topic | Initial owner route | Required record |
| --- | --- | --- |
| Public wording, claim evidence, no-key workflow, cohort process | `open-source-productization` | Evidence class, result date, reproduction path, and limitation |
| Declared provider metadata or model facts | `provider-compatibility` | Exact provider/model, source, and metadata boundary |
| Route admission, authority, tool/write posture, or transport behavior | `provider-adaptation` | Exact route, required gate, and no cross-provider promotion claim |
| Native graph source, GUI/code transform, task state, or graph run | `agent-orchestration` / `task-graph` | Graph/schema version, reproduction, and semantic or authority consequence |
| Candidate skills, presets, plugin enablement, or installation | `skill-orchestration` / `extensions` | Candidate class, manifest/preset, validation, and authority boundary |
| Desktop rendering or UI behavior | `astrabridge-desktop` | Screen, viewport, expected/actual behavior, and screenshot with sensitive data removed |
| Runtime, persistence, migration, shared protocol, updater, release, or broad integration failure | Canonical product-stability owner | Exact command/artifact and a handoff that does not create a parallel runtime contract |
| Security or conduct | **blocked from public intake** | Follow the applicable policy only after its private route is configured |

## First-Contribution Cohort

The [cohort manifest](../examples/contributor-feedback-cohort/cohort-manifest.json)
selects three bounded candidate tasks and runs the existing candidate-skill
validation twice in independent empty roots. It is a finite rehearsal of setup,
validation, review state, and future response expectation, not a simulation of
an external maintainer or a code merge.

```powershell
cd D:\AstraBridge
python scripts\run_contributor_feedback_cohort_rehearsal.py --output-root PRIVATE\contributor-cohort\reports\rehearsal
python -m unittest discover -s apps\astrabridge-sidecar\tests -p test_contributor_feedback_cohort_rehearsal.py
```

The runner writes a secret-free evidence packet. When evidence is retained
under `PRIVATE/`, place the run below a `reports/` bucket as shown so it also
fits the repository artifact-governance scan. Both independent rehearsals must
pass the existing lint/compile/dry-run candidate validation and retain the
out-of-allowlist authority-widening block. Its review result remains
`pending_public_intake` until the owner explicitly enables public intake.

## Maintainer Response Expectation

Current status: `pending_public_intake`. There is no current public support
SLA, named private contact, or promise that a local template submission reaches
a maintainer.

After all activation conditions below are satisfied, the public tracker may be
enabled with this response expectation:

> Within 7 calendar days after public intake is explicitly activated, the
> maintainer records one of `acknowledged`, `needs-info`,
> `accepted-for-design`, `declined`, or `blocked` on a non-sensitive item.

Activation conditions are:

1. A project license and contribution terms are selected.
2. Private vulnerability and private conduct-reporting routes are configured
   and verified.
3. A maintainer explicitly enables public feedback intake and owns triage.

This is an activation contract for future intake, not a workaround for missing
private contacts or an immediate response promise today.

## Decision Record Path

When an owner accepts a change that could alter provider semantics,
orchestration contracts, authority, migration behavior, or public claims, add
a small decision record under `docs/decisions/<YYYY-MM-DD>-<slug>.md` using
this structure:

```markdown
# Decision: <short title>

Status: proposed | accepted | rejected | superseded
Owner: <named subsystem owner>
Public claim affected: <claim or none>

## Context and bounded change

## Evidence and reproduction

## Compatibility, authority, and migration consequences

## Decision and non-goals

## Validation and rollback or downgrade path
```

Do not create a decision record merely to assert a desired provider, installer,
or contribution state. Its evidence and validation must come first; rejected
or blocked decisions remain visible rather than being removed from history.
