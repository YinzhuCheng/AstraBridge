# Public Quality and Reliability Dossier

Status: current pre-preview evidence index. It is intentionally a failure-first
quality record, not a release announcement or a promise that every product
surface is production-ready.

Last verified: 2026-07-27

Machine-readable source: [PUBLIC_QUALITY_RELIABILITY_DOSSIER.json](PUBLIC_QUALITY_RELIABILITY_DOSSIER.json).
Machine checker: [run_public_quality_reliability_dossier.py](../scripts/run_public_quality_reliability_dossier.py).

## Read the Non-Pass Ledger First

The following facts are current product boundaries. They are deliberately
listed before the passing deterministic checks so a developer does not need to
infer limits from a footnote.

| Claim area | Current result | What is not claimed | Where to inspect or reproduce the limit |
| --- | --- | --- | --- |
| Four reference provider routes | `reduced_authority` | Qwen, DeepSeek, Kimi K3, and GLM are not live-verified coding routes, do not receive tools, and are not defaults. | [Provider Truth and Authority Surface](PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md) shows `review_only`, `no_tools`, `ask`, and the next exact route gate. |
| First extension candidate | `warning_gated` | The example is not auto-enabled, installed, provider-qualified, or merge-ready external code. | [Extension and First-Contribution Surface](EXTENSION_AND_FIRST_CONTRIBUTION_SURFACE.md) retains candidate warnings and a blocked allowlist-widening request. |
| Security, privacy, and support | `blocked` | There is no configured private vulnerability-reporting route, private conduct-reporting route, supported-version policy, or public support commitment. | [SECURITY.md](../SECURITY.md), [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md), and the [Developer Preview Baseline](DEVELOPER_PREVIEW_BASELINE.md). |
| Package and update baseline | `blocked` | No public installer, signed distribution, live update service, or authorized developer-preview release exists. | [Developer Preview Baseline](DEVELOPER_PREVIEW_BASELINE.md) lists the five named owner gates and the Windows short-artifact-root workaround. |

Any card not in `pass` or `demonstrated` appears in the machine-generated
negative ledger. A future change must update both its evidence and this ledger;
it may not use a passing sibling route, a screenshot, or static metadata to
hide a missing authority or release gate.

The [Developer Preview Readiness Decision](DEVELOPER_PREVIEW_READINESS_DECISION.md)
applies DG-OSS-04 to this ledger and records the current mandatory `pause`
verdict for a public developer preview.

## Evidence Cards

| Claim | Evidence class and date | Reproduce from public source | Named owner | Boundaries and known limitations |
| --- | --- | --- | --- | --- |
| No-key source evaluation | `deterministic_evidence` / `demonstrated` on 2026-07-27 | [No-Key First Ten Minutes](NO_KEY_FIRST_TEN_MINUTES.md) | `open-source-productization`, `task-graph` | Exact recorded source revision and Windows toolchain only; not an installer, provider, tool-authority, or coding-route proof. |
| Flagship coding workflow | `deterministic_evidence` / `pass` on 2026-07-27 | [Guide](FLAGSHIP_CODING_AGENT_REFERENCE.md), [runner](../scripts/run_flagship_coding_agent_reference.py), [test](../apps/astrabridge-sidecar/tests/test_flagship_coding_agent_reference.py) | `open-source-productization`, `task-graph`, `astrabridge-sidecar` | Includes an expected failed fixture run and retry recovery; does not prove live model behavior or autonomous writes. |
| Four reference provider routes | `documented_and_deterministic` / `reduced_authority` on 2026-07-27 | [Surface](PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md), [cohort evaluator](../apps/astrabridge-sidecar/astrabridge_sidecar/providers/reference_cohort.py), [test](../apps/astrabridge-sidecar/tests/test_provider_truth_authority_surface.py) | `open-source-productization`, `provider-compatibility`, `provider-adaptation` | All four routes remain review-only; live smoke, tool contract, coding-route verification, and default eligibility are deferred. |
| GUI/code orchestration parity | `deterministic_evidence` / `pass` on 2026-07-27 | [Guide](GUI_CODE_ORCHESTRATION_PARITY.md), [runner](../scripts/run_gui_code_orchestration_parity.py), [test](../apps/astrabridge-sidecar/tests/test_gui_code_orchestration_parity.py) | `open-source-productization`, `agent-orchestration`, `task-graph`, `astrabridge-desktop` | Covers one native graph and supported subset. A source-owned GUI edit blocks; universal conversion and source write-back are not claimed. |
| First extension candidate | `deterministic_evidence` / `warning_gated` on 2026-07-27 | [Guide](EXTENSION_AND_FIRST_CONTRIBUTION_SURFACE.md), [runner](../scripts/run_first_contribution_extension_example.py), [test](../apps/astrabridge-sidecar/tests/test_first_contribution_extension_example.py) | `open-source-productization`, `skill-orchestration`, `extensions` | Lint/compile/dry-run pass, but candidate lifecycle warnings remain visible and authority widening is blocked. |
| Security and privacy boundary | `current_contract_and_scan` / `blocked` on 2026-07-27 | [Security and Isolation](SECURITY_AND_ISOLATION.md), [hardening scanner](../scripts/app_hardening_secret_scan.py), [test](../apps/astrabridge-sidecar/tests/test_app_hardening_secret_scan.py) | `security`, `open-source-productization`, `repository-governance` | Product isolation and redaction are current rules; public preview remains blocked until private reporting and support decisions are complete. |
| Package and update baseline | `deterministic_evidence` / `blocked` on 2026-07-27 | [Baseline](DEVELOPER_PREVIEW_BASELINE.md), [readiness gate](../scripts/run_release_readiness_gate.py), [update rehearsal](../scripts/run_windows_update_rehearsal.py), [baseline checker](../scripts/run_developer_preview_baseline_check.py) | `release`, `open-source-productization`, `security` | Identity/staging/update rehearsal pass locally, while legal, safety, support, signing, distribution, and installer gates remain open. |

## Known Qualification Gaps

| Gap | Current consequence | Owner and evidence boundary |
| --- | --- | --- |
| Broader Task Graph HTTP integration | The focused GUI/code parity runner and test pass, but the larger `test_task_graph_api` suite previously hung in `test_http_api_lists_templates_instantiates_graph_and_updates_node_and_edge`. This dossier therefore does not claim a broad HTTP-suite pass. | Default stability/task-graph owner. The preserved Step 6 handoff names the exact test and artifact; future closure must rerun the full suite rather than treating parity evidence as a substitute. |
| Deep Windows release-artifact paths | A deeply nested release-readiness artifact root produced `FileNotFoundError` while staging generated Desktop files. Short roots pass and are documented, but path-length hardening remains required before any installer release. | Release owner; [Developer Preview Baseline](DEVELOPER_PREVIEW_BASELINE.md#bounded-installation-and-fresh-state-route). |

These are not silently downgraded to informational decoration. The first gap
limits the scope of the GUI/card pass; the second remains part of the public
release-blocked state.

## Reproduce the Dossier

Use new, empty local artifact directories. The commands below do not make a
provider call, publish an artifact, or change public release state.

```powershell
cd D:\AstraBridge
python scripts\run_flagship_coding_agent_reference.py --output-root PRIVATE\qd\flagship
python scripts\run_gui_code_orchestration_parity.py --output-root PRIVATE\qd\gui
python scripts\run_first_contribution_extension_example.py --output-root PRIVATE\qd\extension
python apps\astrabridge-sidecar\skills\agentic-update-pipeline\scripts\run_four_provider_reference_cohort.py --workspace-root . --run-id quality-provider
python scripts\app_hardening_secret_scan.py --repo . --public-doc docs\DEVELOPER_PREVIEW_BASELINE.md --json-out PRIVATE\qd\security-scan.json
```

Follow [Developer Preview Baseline](DEVELOPER_PREVIEW_BASELINE.md) first to
produce a release-readiness summary, isolated update-rehearsal summary, and
compact preview-baseline evidence. Then aggregate the cards:

```powershell
python scripts\run_public_quality_reliability_dossier.py `
  --flagship-evidence PRIVATE\qd\flagship\evidence.json `
  --provider-cohort-report PRIVATE\agentic-update-pipeline\runs\quality-provider\validation\reference-cohort.json `
  --gui-parity-evidence PRIVATE\qd\gui\evidence.json `
  --extension-evidence PRIVATE\qd\extension\evidence.json `
  --preview-baseline-evidence PRIVATE\qd\preview\evidence.json `
  --security-scan-report PRIVATE\qd\security-scan.json `
  --output-root PRIVATE\qd\dossier
```

The final packet contains `evidence.json` and `evidence.md`. It reports seven
cards and repeats every non-pass card in a negative ledger. It intentionally
uses public source paths and reproducible artifact contracts instead of raw
private logs, provider payloads, credentials, or headers.

## Quality Interpretation Rules

- `pass` and `demonstrated` describe only the exact deterministic scope of a
  card. They do not widen adjacent provider, plugin, installer, or authority
  claims.
- `reduced_authority`, `warning_gated`, and `blocked` are usable evidence
  states, not cosmetic caveats. They stay visible until the card's named
  evidence gate changes them.
- An expected failure exercise is meaningful only when the failed state and
  its recovery are both preserved. A recovered result must not erase the
  original failed evidence.
- A scan result proves only the files and boundaries it checked. It is not a
  substitute for a configured private reporting route, legal decision, or
  real distribution review.
- The local dossier runner and the underlying deterministic runners are
  provider-free. Live provider smoke remains separately authorized and
  route-specific.
