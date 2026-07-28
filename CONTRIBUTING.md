# Contributing to AstraBridge

## Current Participation Status

AstraBridge is preparing for an open-source developer preview. The project
license and contribution-license terms have not yet been selected, so the
repository is not yet accepting merge-ready external code contributions.

You can still help by proposing a bounded improvement, reproducing a bug with
redacted evidence, reviewing documentation, or discussing an extension idea.
Read [the open-source foundation decision record](docs/OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md)
before opening a contribution discussion.

Use the [Contributor Feedback Protocol](docs/CONTRIBUTOR_FEEDBACK_PROTOCOL.md)
to inspect the prepared local feedback templates and rehearse one bounded,
provider-free first-contribution path. Its `pending_public_intake` status does
not open an issue tracker, create a response promise, or permit merge-ready
external code.

## Before You Share Anything

- Never include API credentials, cookies, authorization headers, vault data,
  plaintext provider keys, private user data, or raw provider payloads.
- Do not reproduce a provider issue with an unapproved paid or key-backed call.
  Prefer the documented no-key or deterministic path first.
- Treat `.abproj` and workspace-local `.astrabridge/` as AstraBridge project
  state. Do not add official Codex configuration or legacy project formats as
  a normal product workflow.
- Read [SECURITY.md](SECURITY.md) before reporting a security-sensitive issue.
  Do not place vulnerability details in a public issue while no private route
  is configured.

## Safe Ways to Help Before Licensing Is Final

1. Describe one user problem, expected behavior, actual behavior, operating
   system, application version or commit, and secret-free reproduction steps.
2. Propose a documentation clarification or a small, bounded product example.
3. For a proposed code change, first open a design discussion with the affected
   subsystem, compatibility risk, test strategy, and intended public claim.
4. Wait for maintainer confirmation of the final license and contribution terms
   before submitting code intended for inclusion in the project.

## Future Code Contribution Workflow

After the license decision and public intake are enabled, a contribution should:

1. Start from a focused issue or approved design record.
2. Change the smallest ownership boundary that solves the stated problem.
3. Add or update deterministic tests and evidence appropriate to the risk.
4. Run the relevant local gates, preserving secret-free artifacts rather than
   deleting diagnostics.
5. Explain compatibility, provider-authority, state-migration, and user-visible
   consequences in the pull request.
6. Respond constructively to review and keep unrelated work out of the change.

## Local Validation Starting Points

Use the smallest validation suite that covers the changed surface, then expand
to the repository gates when the change affects active guidance or release
behavior.

```powershell
cd D:\AstraBridge
python scripts\repo_governance_check.py --repo .
python scripts\run_local_gate.py --quick
```

The existing [verification matrix](docs/VERIFICATION_MATRIX.md) and
[release checklist](docs/RELEASE_CHECKLIST.md) define broader test and
promotion requirements. Do not claim a live provider route is verified merely
because a no-key demo, a metadata refresh, or a transport response passed.

## Bounded Extension Rehearsal

Before license and public intake decisions are complete, use the
[Extension and First-Contribution Surface](docs/EXTENSION_AND_FIRST_CONTRIBUTION_SURFACE.md)
to make a proposal or reproduce one finite extension path. Its candidate
read-only skill example provides a local lint/compile/dry-run route with an
explicit authority-widening failure case. It is not an auto-enabled plugin,
live-provider route, or permission to submit merge-ready external code.

## Design Boundaries to Preserve

- AstraBridge is an independent, local coding-agent workbench; it is not the
  official Codex App.
- External providers remain evidence-qualified routes. Provider-specific state
  must not bypass AstraBridge permissions, task lineage, tool policy, or
  recovery controls.
- GUI and code orchestration must preserve the same declared policy and task
  semantics rather than silently changing authority during conversion.
- Keep secrets out of repository files and preserve secret-free diagnostics and
  validation evidence by default.

## Conduct and Security

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Security
and sensitive disclosures follow [SECURITY.md](SECURITY.md), which currently
records the private-reporting configuration required before broad public intake.
