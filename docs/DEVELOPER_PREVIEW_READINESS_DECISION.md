# Developer Preview Readiness Decision

Status: `pause` for a public developer preview. This is the current
evidence-bound DG-OSS-04 outcome, not a release announcement, a public
support promise, or an instruction to open repository-host intake.

Last verified: 2026-07-27

Machine evaluator: [run_developer_preview_readiness_decision.py](../scripts/run_developer_preview_readiness_decision.py).
Focused regression: [test_developer_preview_readiness_decision.py](../apps/astrabridge-sidecar/tests/test_developer_preview_readiness_decision.py).

## DG-OSS-04 Verdict

**Branch C — pause.** The public developer-preview transition is paused.
DG-OSS-04 makes this branch mandatory while a legal, security, or privacy gate
is unresolved. The repository currently has all three: no selected project
license or contribution terms, no verified private vulnerability-reporting
route, and no verified private conduct-reporting route.

This verdict preserves the demonstrated local no-provider source path and
deterministic package/update rehearsal. It does not downgrade those results,
but it prevents them from being misrepresented as a public preview or release.

## Evidence Scorecard

| Evidence area | Current state | Decision consequence |
| --- | --- | --- |
| No-key source evaluation | `demonstrated` | A bounded local source-evaluation route remains inspectable. |
| Flagship coding workflow | `pass` | The deterministic task, approval, failure, and recovery reference remains usable as evidence. |
| Native GUI/code parity | `pass` within the named subset | Retain the bounded graph claim and its explicit HTTP-integration limit. |
| Four reference provider routes | `reduced_authority` | Do not claim live coding-route, tool, write, or default-route authority. |
| First extension candidate | `warning_gated` | Keep the candidate experimental; do not enable, install, or accept it as a merge-ready intake route. |
| Security, privacy, and support | `blocked` | Mandatory pause input; no private report channel or public support commitment exists. |
| Package and update baseline | `blocked` for public release | Local identity/staging/update rehearsal is not a public installer or distribution authorization. |
| Contributor cohort | `rehearsed_pre_preview` / `pending_public_intake` | Local templates and two provider-free rehearsals exist, but public intake remains disabled. |

The failure-first [Public Quality and Reliability Dossier](PUBLIC_QUALITY_RELIABILITY_DOSSIER.md)
is the canonical card-level ledger. The evaluator requires all four of its
non-pass cards to remain visible instead of substituting a passing no-key or
GUI check for a release decision.

## Mandatory Release Blockers

| Gate | Category | Owner | Required evidence before reconsideration |
| --- | --- | --- | --- |
| `license_and_contribution_terms` | legal | Project and legal foundation owner | Selected root license, copyright/notice review, and final contribution terms. |
| `private_vulnerability_reporting` | security | Security maintainer | Tested private route, response owner, and supported-version policy in [SECURITY.md](../SECURITY.md). |
| `private_conduct_reporting` | privacy | Conduct-enforcement owner | Monitored private conduct contact and a stated response expectation in [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md). |
| `public_support_and_issue_triage` | support | Community and maintainer-triage owner | Explicit repository-host activation and triage ownership only after the legal and private-reporting gates are verified. |
| `authorized_distribution_release` | distribution | Release owner | Signing/distribution approval, clean-user installer validation, artifact provenance, and a release evidence note. |

The first three rows make `pause` mandatory. The last two independently block a
public preview or release even after a future legal/security/privacy decision.

## Dissenting and Qualification Evidence

- Provider metadata and deterministic adapter evidence do not establish live
  provider smoke, tool contracts, coding-route eligibility, or default-route
  status.
- The GUI/code proof covers one native graph subset; the broader Task Graph HTTP
  integration hang remains a default-stability qualification gap.
- The extension candidate is deliberately warning-gated and fails closed on
  authority widening.
- Deep Windows release-artifact paths still need hardening before an installer
  release, even though the documented short-root rehearsal passes.

These limits are reasons to preserve the existing evidence and to avoid a
public release claim, not reasons to erase passing deterministic work.

## Current Public Scope

Allowed now:

- local or private no-provider evaluation using the documented boundaries;
- inspection of redacted, secret-free deterministic evidence; and
- bounded local contributor rehearsals that remain `pending_public_intake`.

Not allowed now:

- public developer-preview release, installer distribution, or live update
  service claim;
- activating public issue intake, a support SLA, or a named private contact;
- accepting merge-ready external code; or
- promoting provider metadata or reduced-authority routes to coding-agent,
  tool, or write authority.

## Next Owner-Gated Execution Unit

- ID: `OSS-FOUNDATION-CLEARANCE-01`
- Status: `owner_gated`
- Coordinator: project and legal foundation owner
- Goal: clear the five named release gates before any new public-preview
  decision is evaluated.
- Activation condition: an authorized owner selects the license and
  contribution terms, configures and verifies both private reporting routes,
  assigns public-triage ownership, and authorizes distribution review.
- Completion evidence: the five blocker rows above have current, independently
  checkable evidence. The coordinator then reruns the preview baseline,
  contributor cohort, quality dossier, and readiness evaluator.

This is an explicit handoff to owner-gated foundation work, not a new public
release queue and not authorization for an agent to create contacts, choose a
license, publish, or change repository-host settings.

## Reproduce the Decision

Use fresh, empty local evidence roots. The evaluator consumes secret-free
baseline and contributor-cohort evidence; it makes no provider or network
call and never changes public state.

```powershell
cd D:\AstraBridge
python scripts\run_developer_preview_readiness_decision.py `
  --preview-baseline-evidence <secret-free-preview-baseline-evidence.json> `
  --contributor-cohort-evidence <secret-free-contributor-cohort-evidence.json> `
  --output-root PRIVATE\readiness\reports\decision
```

The output must report `gate=DG-OSS-04`, `verdict=pause`, and `branch=C` while
the mandatory foundation gates remain unresolved. The focused regression fails
if an input hides a release blocker or changes the cohort to active public
intake.
