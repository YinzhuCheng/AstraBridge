# AstraBridge

AstraBridge is a local, developer-first coding-agent workbench built around
Codex CLI/app-server runtime patterns and AstraBridge-owned project, provider,
permission, and orchestration contracts. It uses app-owned project state,
app-owned provider routing, and isolated runtime paths instead of official
Codex user state.

It is not the official Codex App. OpenAI, DeepSeek, Kimi, Qwen, Yunwu, and
other compatible backends are treated as evidence-qualified API-key provider
lanes with separate model metadata, adapter policy, health checks, route
authority, and local project state. A compatible endpoint is not automatically
a verified coding-agent route.

## Why AstraBridge

- Keep one visible `Project -> Task` workspace while provider/model/runtime
  lanes remain inspectable internal execution details.
- Treat provider adaptation as a product contract: metadata, protocol,
  reasoning, tool authority, fallback, and validation evidence are separate
  decisions.
- Author bounded agent workflows through portable graph contracts and inspect
  them in GUI and code-oriented forms instead of hiding the workflow in one
  prompt.
- Preserve explicit permission, artifact, recovery, and secret-redaction
  boundaries as part of the coding workflow.

Read [the product positioning and claim matrix](docs/OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md)
for the exact evidence level behind each statement. In particular, the current
Qwen, DeepSeek, Kimi K3, and GLM reference routes are review-only,
reduced-authority lanes; they are not autonomous or default coding routes.

## Product Facts

- Normal project format: `.abproj`
- Normal workspace state: `.astrabridge/`
- Main operator surface: LLM API Manager
- Main metadata source: provider/model catalog managed by AstraBridge
- Main workflow target: a local coding workspace with evidence-qualified core
  and external execution lanes
- User navigation: `Project -> Task`; runtime `thread_id` values remain
  internal execution-lane identifiers
- Graph authoring: deterministic tested subsets support canonical import,
  dry-run, fixture run, export, reload, and re-import; public GUI/code parity
  evidence is still being expanded
- Official OpenAI account login is not a product path
- Legacy `.lcrproj`, `.lcr`, `.codexproj`, and `.codex-shell` are not normal product paths

## Repo Layout

- `apps/astrabridge-sidecar/`: sidecar services, project/runtime/provider/model APIs
- `apps/astrabridge-desktop/`: desktop/web UI, i18n, browser-facing workflow surfaces
- `docs/`: active operator, security, release, and demo documentation
- `PLAN/`: tracked execution plans, surface maps, and historical execution records
- `PRIVATE/`: local-only demo runs, screenshots, validation artifacts, and private operator material

## Quickstart

### Sidecar

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest discover -s tests
python -m astrabridge_sidecar.server --serve --port 8826 --seed-root D:\AstraBridge
```

### Desktop

```powershell
cd D:\AstraBridge\apps\astrabridge-desktop
npm.cmd install
npm.cmd run test
npm.cmd run build
npm.cmd run dev
```

### Browser Smoke URL Shape

Use the desktop dev server with an explicit sidecar URL:

```text
http://127.0.0.1:4181/?astrabridge_launch=dogfood&sidecar=http://127.0.0.1:8826&smoke=1
```

For the documented no-provider onboarding route, follow
[No-Key First Ten Minutes](docs/NO_KEY_FIRST_TEN_MINUTES.md). It creates an
isolated project and runs a deterministic task-graph fixture; it does not
prove live provider behavior or, until its dependency-manifest gate is
published, a release-ready clean-clone experience.

## Demo Modes

### No-key demo

Use this by default when validating UI, project state, browser smoke wiring, or local product workflows.

- Does not require real provider token spend
- Suitable for layout checks, local state checks, and smoke plumbing

### Key-backed smoke

Use this only when the task explicitly requires real provider connectivity or model behavior verification.

- Requires user-approved secret loading path
- Must report only secret-safe status fields
- Must not persist plaintext keys, headers, cookies, or raw provider secrets

## Secret Safety

- Do not commit API keys, bearer tokens, cookies, auth headers, or provider raw secrets
- Do not read Desktop plaintext key files unless the user explicitly authorizes that exact action
- Do not push anything under `PRIVATE/**` except intentionally tracked documentation such as `PRIVATE/README.md`
- Do not write official Codex `~/.codex/config.toml` or project `.codex*` files during normal AstraBridge use

## Open-Source Participation Status

AstraBridge is preparing for an open-source developer preview. Its license and
external code-contribution terms have not yet been selected, so it does not yet
accept merge-ready external code contributions. The current decision, safe
pre-license participation path, conduct policy, and security-reporting gate are
documented in [the open-source foundation decision record](docs/OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md),
[CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
and [SECURITY.md](SECURITY.md).

## Current Entry Points

- [Canonical Document Registry](/D:/AstraBridge/docs/DOCUMENT_REGISTRY.md)
- [Current Product Stability And Interoperability Plan](/D:/AstraBridge/PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md)
- [Project Summary](/D:/AstraBridge/docs/PROJECT_SUMMARY.md)
- [Repository Governance](/D:/AstraBridge/docs/REPO_GOVERNANCE.md)
- [Verification Matrix](/D:/AstraBridge/docs/VERIFICATION_MATRIX.md)
- [Ownership Boundaries](/D:/AstraBridge/docs/OWNERSHIP_BOUNDARIES.md)
- [Project Log](/D:/AstraBridge/docs/PROJECT_LOG.md)
- [Asset Sources](/D:/AstraBridge/docs/ASSET_SOURCES.md)
- [Demo Runbook](/D:/AstraBridge/docs/DEMO_RUNBOOK.md)
- [No-Key First Ten Minutes](/D:/AstraBridge/docs/NO_KEY_FIRST_TEN_MINUTES.md)
- [Security And Isolation](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)
- [Product Positioning And Claim Matrix](/D:/AstraBridge/docs/OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md)
- [Release Checklist](/D:/AstraBridge/docs/RELEASE_CHECKLIST.md)
- [Completed Repository Normalization Record](/D:/AstraBridge/PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md)
- [Legacy Compatibility Shim Archive](/D:/AstraBridge/docs/archive/LEGACY_COMPATIBILITY_SHIMS.md)

`docs/DOCUMENT_REGISTRY.json` is the machine-readable source for document and plan status. Do not resume a plan merely because its own historical progress block says `In progress`; follow the registry's status, replacement, and activation fields.

## Local Governance Gate

Use the quick local gate after repository hygiene, documentation, script, or narrow governance changes:

```powershell
python scripts/run_local_gate.py --quick
```

Use the full local gate before release preparation or broad cross-subsystem handoff:

```powershell
python scripts/run_local_gate.py --full
```

Use the fail-closed promotion gate when you need a machine-readable PR, nightly, or release verdict bound to one commit, clean-tree state, toolchain versions, and artifact digests:

```powershell
python scripts/run_promotion_gate.py --mode pr --expected-commit <sha>
python scripts/run_promotion_gate.py --mode nightly --expected-commit <sha>
python scripts/run_promotion_gate.py --mode release --expected-commit <sha>
```

The canonical CI entry points now live under `.github/workflows/` and call `scripts/run_promotion_gate.py` rather than duplicating suite lists in workflow YAML.

Use the release-readiness gate when release identity, staged contents, or package provenance changes:

```powershell
python scripts/run_release_readiness_gate.py --run-id local-readiness
```

It verifies one canonical release identity, builds a clean staged workspace from an explicit allowlist, emits inventory/hash/SBOM-input evidence, and proves two staging runs are deterministic.
