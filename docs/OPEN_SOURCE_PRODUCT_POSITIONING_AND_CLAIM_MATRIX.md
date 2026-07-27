# AstraBridge Open-Source Product Positioning and Claim Matrix

Status: current public positioning boundary for the pre-preview repository.

Last verified: 2026-07-27

## Product Statement

AstraBridge is a local, developer-first coding-agent workbench built around
Codex CLI/app-server runtime patterns and AstraBridge-owned project, provider,
permission, and orchestration contracts. It gives a developer one visible
`Project -> Task` workspace while keeping provider/model/runtime lanes as
internal execution details.

Its differentiator is not merely a list of model endpoints. AstraBridge aims to
make provider adaptation inspectable and evidence-qualified, and to let a
developer author bounded agent workflows through GUI and code representations
that share declared graph and policy contracts. External provider routes do not
inherit the core runtime's authority by name, model family, or HTTP shape.

## Who This Is For

1. **Coding-agent evaluators** who want local project state, explicit task
   boundaries, and evidence before trusting a model or tool route.
2. **Workflow authors** who want to inspect, version, import, export, and test
   bounded orchestration graphs rather than hide the workflow in a prompt.
3. **Provider and adapter maintainers** who need separate model metadata,
   route-admission, reasoning, tool, fallback, and evidence lifecycles.
4. **Open-source contributors** who value reproducible no-key paths and clear
   ownership boundaries, while accepting that license and public intake remain
   pre-preview decisions.

## Vocabulary and Evidence Labels

These labels prevent public prose from treating a design, fixture, or endpoint
response as a proven coding-agent capability.

| Label | Meaning | Public wording rule |
| --- | --- | --- |
| `current-contract` | Current source and governance documents define the boundary or owner. | Describe the behavior as a product contract, not as provider-backed proof. |
| `deterministic-evidence` | Current tests or no-network fixtures prove a bounded behavior. | State the exact bounded behavior and do not generalize it to a live provider. |
| `documented` | Metadata or published source says a route/model has a declared property. | Say “documented” or “declared”; name the promotion gate still required. |
| `reduced-authority` | A route is deliberately review-only, confirmation-gated, and tool-restricted. | Never call it verified, default, autonomous, or coding-route eligible. |
| `unknown` or `deferred` | Current repository evidence is absent, stale, or intentionally out of scope. | Do not market it as a current capability. |

## Claim-Evidence Matrix

| Public claim | Current evidence state | Evidence and owner | Next validation / public limit |
| --- | --- | --- | --- |
| **Local project and task workspace:** AstraBridge uses `.abproj` plus workspace-local `.astrabridge/`, and presents `Project -> Task` rather than raw runtime threads. | `current-contract` | [Architecture](ARCHITECTURE.md) owns the Desktop/sidecar/runtime boundary; [security and isolation guidance](SECURITY_AND_ISOLATION.md) defines isolated state; the project summary defines task/lane vocabulary. | Step 3's clean-clone fixture revision `7737d36c51346ef6126d497aa8d48004448e966e` is now the local canonical branch head. Its public documentation/release transaction remains open, so do not claim a public fresh-install experience yet. |
| **Codex-derived core integration:** AstraBridge is built around Codex CLI/app-server runtime patterns, with AstraBridge-owned isolation and policy boundaries. | `current-contract` | [Architecture](ARCHITECTURE.md), [Provider capability and reasoning runbook](PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md), and current security guidance. | It is not the official Codex App, does not use official account login as a product path, and does not promise feature parity with any external Codex product. |
| **Evidence-qualified external provider lanes:** provider, model, endpoint, driver, authority, and evidence are separate decisions. | `current-contract` | [Provider capability and reasoning runbook](PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md) and the current architecture assign the owner surfaces and promotion lifecycle. | A compatible HTTP response or metadata record cannot be marketed as coding-agent compatibility. |
| **Current Qwen, DeepSeek, Kimi K3, and GLM reference routes:** the named routes are available only as review-only, reduced-authority subjects. | `reduced-authority` | The provider runbook's 2026-07-27 reference cohort records `qwen/qwen3.7-plus`, `deepseek/deepseek-v4-pro`, `kimi/kimi-k3`, and `glm/glm-5.2` as `documented / review_only / reduced_authority`, with `no_tools` and `ask`. | Each exact route still requires adapter dry-run, authorized provider smoke, tool-contract proof, coding-route verification, and default-route eligibility. No current live smoke claim is made here. |
| **Model metadata:** AstraBridge can maintain declared model capabilities, reasoning mappings, modalities, and catalog state separately from route authority. | `documented` plus `deterministic-evidence` | The provider runbook names declared catalog, normalized contract, and validated-evidence layers; current static/dry-run evidence is preserved under the documented private roots. | Do not infer context-window accuracy, reasoning behavior, tool support, or multimodal reliability for a specific endpoint without its exact current evidence. |
| **High-freedom orchestration through code and GUI-facing graph contracts:** supported canonical graphs can be imported, validated, dry-run, fixture-run, exported, reloaded, and re-imported without semantic change in the tested subset. | `deterministic-evidence` | On 2026-07-27, `tests.test_agent_orchestration_file_format` and `tests.test_provider_reference_cohort` passed 9 tests; three focused `TaskGraphApiTests` passed for a TypeScript SDK fixture round trip, executable supported-router export, and structured blocking of unsupported runtime-bound export. Ownership lives in the typed graph and task-graph contracts. | This is not a blanket promise of lossless GUI/code conversion for every graph or external format. Step 6 must deliver the public user-facing parity proof and enumerate any one-way transforms. |
| **Permissions, tools, and recovery remain visible product boundaries.** | `current-contract` | [Architecture](ARCHITECTURE.md), [interface governance](INTERFACE_GOVERNANCE.md), and the default stability plan assign durable task, event, scheduler, and policy owners. | No external route gains tool or write authority merely by being configured. Live authority remains evidence- and confirmation-gated. |
| **No-key evaluation path.** | `deterministic-evidence` | [No-Key First Ten Minutes](NO_KEY_FIRST_TEN_MINUTES.md) records an isolated Windows clean clone of current local canonical revision `7737d36c51346ef6126d497aa8d48004448e966e`: fresh application/runtime/Codex roots, a `.abproj` project, a `Supervisor / Worker / Synthesizer` fixture graph, and a completed run with 3 workers and 22 artifacts. `npm.cmd ci`, focused task-graph tests, build, editable sidecar install, import, and `pip check` passed; browser requests were loopback-only. | This proves the exact no-provider local-canonical fixture behavior only. The documentation transaction must still reach published source before a public fresh-clone claim. It does not prove a release installer, live provider/model behavior, tool authority, or coding-route eligibility. |
| **Plugins, skills, and capabilities are inspectable but not implicitly trusted.** | `current-contract` | [Architecture](ARCHITECTURE.md) and [security and isolation guidance](SECURITY_AND_ISOLATION.md) require metadata-first discovery and explicit enablement. | Do not market a plugin marketplace or automatic skill execution. Step 7 owns the supported-versus-experimental extension surface. |
| **Open-source developer preview readiness.** | `deferred` | [Open-source foundation decision record](OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md), [CONTRIBUTING](../CONTRIBUTING.md), [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md), and [SECURITY](../SECURITY.md). | No release claim is valid until the owner selects a license and configures private security and conduct-reporting contacts. |

## Public Narrative Rules

Use these formulations in README copy, demos, issues, and presentations:

- Say **“evidence-qualified external provider route”**, not “all models work
  like Codex.”
- Say **“review-only reduced-authority route”**, not “supported autonomous
  agent,” when the route is `no_tools` / `ask`.
- Say **“deterministic graph round trip for the tested subset”**, not “any GUI
  graph converts losslessly to code.”
- Say **“built around Codex CLI/app-server runtime patterns”**, not “the
  official Codex App” or “official Codex account integration.”
- Say **“no-key fixture onboarding has deterministic evidence”** only for the
  documented clean-user path; do not turn it into a provider or agent claim.

## Explicit Non-Goals for the First Public Preview

- official OpenAI account login or official Codex configuration as a product
  path;
- a generic endpoint proxy that equates OpenAI-compatible transport success
  with coding-agent semantics;
- universal, autonomous, tool-enabled multi-provider routing;
- a claim that every GUI graph, external workflow import, or generated code
  export round-trips without loss;
- cloud team governance, a plugin marketplace, or silent writes to official
  Codex configuration; and
- a public release before license, disclosure, support, and reproducible
  onboarding gates are complete.

## Reader Path

1. Start with [README](../README.md) for the product boundary and local setup.
2. Use this matrix to classify every material capability statement.
3. Read [Product Brief](PRODUCT_BRIEF.md) for audience and scope.
4. Read [Architecture](ARCHITECTURE.md) and [Interface Governance](INTERFACE_GOVERNANCE.md) for ownership and compatibility limits.
5. Read [Provider Capability and Reasoning Runbook](PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md) before relying on a provider/model route.
