# Extension and First-Contribution Surface

## Current decision

AstraBridge has one public, bounded first-extension route today: a
**candidate skill manifest that resolves to an existing canonical native graph**.
It is a local, provider-free rehearsal for a contribution discussion, not an
auto-enabled plugin, a new scheduler, or a merge-ready external code path.

The executable example is
[`examples/extension-contribution/contributor-read-only-brief/`](../examples/extension-contribution/contributor-read-only-brief/).
It binds `example.contributor-read-only-brief` to the existing
`supervisor_worker_synthesizer` graph and intentionally limits itself to a
read-only workspace MCP rule, one bounded routing allowlist, no nesting, no
direct teammate messages, and explicit `ask` approval for risky effects.

The example remains `candidate`. Discovery, validation, and a successful
fixture-like dry-run do **not** enable it, install it, qualify a provider, or
grant tool/write authority.

## Extension classification

| Surface | Current class | Stable entry / owner | Required validation and limit |
| --- | --- | --- | --- |
| Portable native Agent Orchestration JSON examples | **supported**, only for the documented native subset | `examples/agent-orchestration/`; `agent-orchestration` owner | Import, canonical lint/compile/dry-run, and semantic round-trip evidence. Source-owned GUI graphs do not silently write back. |
| Candidate skill manifests that bind one canonical graph | **experimental** | `examples/extension-contribution/` for the public example; skill-to-graph contract owner | Closed parameter schema, safe bindings, canonical lint/compile/dry-run, secret scan, and a failure case. Candidate status is not productized status. |
| Plugin/skill discovery, enablement, installation, and project presets | **experimental** | Extensions registry and `PluginSkillInventoryPanel`; `extensions` owner | Metadata-first discovery plus explicit enablement. Install/apply is isolated and rollback-aware; no marketplace, auto-trust, or auto-enablement claim. |
| Declared provider/model metadata and reference-cohort records | **experimental**, maintainer-reviewed | Provider catalog and [Provider Truth and Authority Surface](PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md); `provider-compatibility` owner | Source-backed metadata checks may update declared facts only. They never promote route authority, tool access, or live coding eligibility. |
| Loss-aware external workflow adapters such as ComfyUI or LangGraph | **experimental** | Adapter contract and task-graph import/export owner | A supported subset must preserve fields or explicitly report loss/block the transform. It is not universal conversion coverage. |
| Provider transports, capability adapters, A2A trust/gateway behavior, scheduler/runtime/protocol code, and Desktop/sidecar host supervision | **internal** | Named owners in [Code Ownership and Contracts](CODE_OWNERSHIP_AND_CONTRACTS.md) | Requires the owning stability/runtime queue, route admission, policy, security, and compatibility evidence. It is not a newcomer extension surface. |
| Public plugin marketplace, automatic third-party execution, unaudited live-provider extensions, and merge-ready external code intake | **deferred** | Owner decisions in [Open-Source Foundation Decision Record](OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md) | Blocked pending license/contribution terms, private security/conduct contacts, and the relevant live-authority gates. |

“Supported” here means only the exact native graph subset backed by current
evidence. It does not turn every source file, GUI graph, plugin, adapter, or
provider configuration into a stable public API.

## The bounded first-extension example

The sample has a finite, inspectable configuration contract:

- Files: `SKILL.md` and `orchestration-manifest.json` only.
- Required parameter: `task_goal`; optional `constraints` and `worker_scope`.
- Canonical graph: `supervisor_worker_synthesizer`; no inline graph or second
  runtime is introduced.
- Declared upper limits: maximum 3 agents, 1 parallel lane, 30,000 tokens, 1 provider
  call, and 0 retries. Validation itself invokes no provider, MCP, or agent.
- Authority: only a read-only workspace rule is declared; file writes,
  installs, external writes, direct provider SDK calls, and direct peer
  messaging remain prohibited.
- Failure boundary: a request for `glm/glm-5.2`, outside the allowlist, is
  rejected with structured `requested_route_widens_*_allowlist` blockers.

The preserved evidence shows canonical lint, compile, and dry-run all passed,
while candidate lifecycle and unavailable/uncertain route evidence remain
visible warnings. It made zero network/provider/MCP/agent-execution calls:
[evidence.md](../PRIVATE/open-source-productization/validation/step7-first-contribution-extension-20260727/evidence.md).

## Reproduce the example

Use a new, empty evidence directory:

```powershell
python scripts\run_first_contribution_extension_example.py `
  --output-root PRIVATE\demo-runs\first-contribution-extension

Push-Location apps\astrabridge-sidecar
python -m unittest discover -s tests -p test_first_contribution_extension_example.py
Pop-Location
```

For manual inspection, the existing CLI accepts the sample directory as a
skill reference. Use a parameters file or JSON value containing only
secret-free task text. Do not put provider keys, cookies, authorization
headers, private reasoning, or raw provider payloads in the manifest or its
parameters.

## First-contribution route

Before licensing and public intake are finalized, the appropriate action is a
**proposal/rehearsal**, not a merge-ready external code submission:

1. Choose exactly one classified surface and identify its named owner.
2. Start from the candidate sample or a native graph example; do not modify
   runtime/protocol/provider internals as a first change.
3. State the input schema, canonical graph/template reference, bounded policy,
   expected output, compatibility note, and failure behavior.
4. Run the smallest relevant deterministic validation and preserve a
   secret-free report under `PRIVATE/**`.
5. Share the proposal with the affected subsystem and public-claim owner.
   Wait for license and contribution-term confirmation before submitting code
   intended for repository inclusion.

The current [CONTRIBUTING](../CONTRIBUTING.md) and [SECURITY](../SECURITY.md)
rules still apply. In particular, a green no-key check does not authorize a
provider call, install, external write, official Codex configuration change,
or security disclosure in a public channel.

## Compatibility and promotion rules

- Keep a candidate skill at `candidate` until the owner reviews its schema,
  graph reference, policy, fixtures, and negative cases.
- A `validated` status needs current structural evidence; `productized` needs
  the complete supported fixture/MCP/typed-edge evidence defined by the
  skill-to-graph contract. Provider-qualified or external-A2A-qualified
  statuses need their separate route/trust gates.
- Tightening a budget, narrowing a route allowlist, adding approval, or
  reducing context visibility is allowed within the candidate boundary.
  Widening authority requires a reviewed manifest/version change and cannot be
  hidden in a prompt, GUI action, preset, or fallback.
- A new built-in graph template, plugin install path, transport adapter, or
  runtime capability is not an example-only change; route it to the named
  internal owner and the applicable stability plan.

## Owners

- First-extension sample and public contribution wording:
  `open-source-productization`.
- Native graph/file-format contract: `agent-orchestration`.
- Skill-to-graph resolution and policy checks: `skill-orchestration`.
- Plugin/skill registry, enablement, presets, and install lifecycle:
  `extensions`.
- Provider metadata/transport/admission: `provider-compatibility` and the
  default stability queue.

See the [claim-evidence matrix](OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md)
for public wording boundaries and [GUI / Code Orchestration Parity](GUI_CODE_ORCHESTRATION_PARITY.md)
for the currently supported native graph subset.
