# AstraBridge Open-Source Foundation Decision Record

Status: pre-license developer-preview preparation. This record is a product
and maintainer decision aid, not legal advice and not a grant of rights.

Last reviewed: 2026-07-27

## Purpose

AstraBridge is preparing for an open-source developer preview so outside
developers can inspect, try, extend, and eventually contribute to a local,
multi-provider coding-agent workbench. Before any public release claim, the
maintainer must establish a project license, contribution terms, a private
security-reporting route, and a clear conduct/enforcement path.

This record preserves the current gap instead of pretending that a missing
root license or private contact is already in place.

## Evidence Snapshot

The following inventory was checked in the local repository on 2026-07-27.

| Foundation item | Current evidence | Consequence |
| --- | --- | --- |
| Project license | No `LICENSE`, `LICENSE.md`, or `LICENSE.txt` exists at the repository root. | No public source-use or code-contribution license may be claimed. |
| Contribution guide | No root `CONTRIBUTING.md` existed before this decision record. | The preparation guide now maps safe issue/reproduction and future PR workflow, but merge-ready external code remains gated by the license decision. |
| Code of conduct | No root `CODE_OF_CONDUCT.md` existed before this decision record. | The project now records conduct standards, while private enforcement intake remains a release gate. |
| Security policy | `docs/SECURITY_AND_ISOLATION.md` defines strong product and secret boundaries, but no root `SECURITY.md` or public vulnerability-reporting channel existed. | A public preview must not claim a private disclosure channel until the maintainer configures and verifies one. |
| Hosting | Local Git configuration names `https://github.com/YinzhuCheng/AstraBridge.git` as `origin`; the tracked `.github/` directory currently contains promotion workflows only. | GitHub-oriented issue, advisory, and branch-protection settings remain maintainer-admin decisions rather than repository facts. |
| Release discipline | `docs/RELEASE_CHECKLIST.md` and promotion workflows define validation, isolation, and secret-scan gates. | Public-foundation files must point contributors to the same safety boundaries rather than invent a parallel process. |

## License Decision Requested

The maintainer must explicitly choose one license and confirm the copyright
holder name before a root `LICENSE` file, a contribution license clause, or a
public release is added. Two viable choices are below.

| Option | Fit for AstraBridge | Operational consequences to confirm before use |
| --- | --- | --- |
| `Apache-2.0` — recommended for the stated developer-adoption goal | A permissive, well-known license with explicit patent-grant terms in its published text. It is a strong default when the priority is broad developer, research, and company adoption of a developer tool. | Use the exact license text; confirm copyright owner; retain required notices; audit third-party code, package, font, icon, and asset notices; decide whether a `NOTICE` file is required. The license text's contribution clause affects how intentionally submitted contributions are licensed. |
| `MPL-2.0` — reciprocal alternative | A file-level copyleft option that can encourage sharing modifications to covered source files while allowing a larger work to contain separate files under different terms. | Use the exact license text and required notices; confirm whether its file-level reciprocity matches the desired extension and plugin ecosystem; audit third-party compatibility and distribution obligations before packaging a desktop preview. |

The comparison is based on the published [Apache-2.0 text](https://spdx.org/licenses/Apache-2.0.html) and the published [MPL-2.0 text](https://www.mozilla.org/en-US/MPL/2.0/), including Mozilla's [MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/). The maintainer should obtain qualified legal review if project ownership, contributed code, employer rights, third-party assets, or distribution jurisdiction create uncertainty.

### Recommended Decision Route

For the user's stated aim—attract developers to collaborate, build a credible
public engineering portfolio, and avoid a monetization-first posture—the
recommended route is `Apache-2.0`, subject to the checks below. It minimizes
initial adoption friction while keeping the project's actual safety,
permission, and provider-authority policies independent of license wording.

This is a recommendation, not a selection. The root license remains absent
until the owner explicitly accepts it or selects another option.

## Required Owner Decisions

Before a public developer preview, the maintainer must record all of these:

1. License choice: `Apache-2.0`, `MPL-2.0`, or another explicitly named
   option with its own compatibility review.
2. Copyright holder name and whether any employer, collaborator, or prior
   contributor must consent.
3. Contribution licensing approach after the project license is selected,
   including whether a contributor license agreement or developer certificate
   of origin is needed.
4. Private vulnerability-reporting channel: either a verified repository-host
   private reporting feature or a dedicated monitored security contact.
5. Conduct-enforcement contact and expected acknowledgment/response window.
6. Third-party notice and distribution policy for source dependencies,
   packaged desktop dependencies, icons, fonts, bundled binaries, and examples.

## Public Foundation Artifact Map

| Path | State after this step | Owner action before preview |
| --- | --- | --- |
| `LICENSE` | Intentionally absent. | Add the exact selected text only after the license and copyright decisions are recorded. |
| `NOTICE` | Intentionally absent. | Create only if the selected license, included third-party materials, or distribution review requires it. |
| `CONTRIBUTING.md` | Present as a transparent preparation guide. | Replace the pre-license code-PR gate with final contribution terms after license selection. |
| `CODE_OF_CONDUCT.md` | Present as a conduct policy with no invented private contact. | Publish and test a private enforcement route before opening broad contributor intake. |
| `SECURITY.md` | Present as a pre-preview security policy that explicitly says no private reporting route is configured yet. | Configure a real private reporting route, add its exact instructions, and verify the route before public preview. |
| `.github/ISSUE_TEMPLATE/` | Not created in this step. | Step 10 owns safe bug, feature, documentation, and first-task templates. |
| Maintainer roster / governance | Not published in this step. | Publish only after the owner decides the named maintainers, review expectations, and contact surface. |

## Non-Negotiable Safety Rules

- Do not put credentials, bearer tokens, cookies, authorization headers, raw
  provider payloads, or private account state in issues, pull requests,
  screenshots, examples, or reports.
- Do not describe AstraBridge as the official Codex App or imply official
  account-login support. Its normal product state remains `.abproj` plus
  workspace-local `.astrabridge/`.
- Do not promote a provider/model from documented metadata or no-key fixtures
  to verified coding-agent authority without its existing evidence gates.
- Do not turn this decision record into a substitute for the release checklist,
  security boundary, or default product-stability execution queue.

## Completion Criteria for This Decision

This decision record is complete when it truthfully captures the current
foundation gap, presents at least two viable licenses with consequences,
recommends a route without selecting it, maps contribution/security/conduct
artifacts, and identifies the exact human decisions that block public preview.

The open-source foundation itself becomes release-ready only after the required
owner decisions are made and the resulting public files and host settings are
verified.
