# Provider Truth and Authority Surface

Status: current public route-evidence surface for the pre-preview repository.

Owner: `open-source-productization` owns the wording on this page.
`provider-compatibility` owns catalog/profile metadata; `provider-adaptation`
owns route-admission and authority evidence.

This is a route-level support surface, not a provider-family badge. A model can
have documented metadata and passing deterministic adapter checks while still
being unable to run tools or act as a coding route. Do not generalize one
route's result to another model, endpoint, credential scope, or provider.

## Read the Two Axes Separately

Every route card below has two independent axes:

1. **Evidence** says what kind of observation exists. `documented` means the
   catalog/profile declares a value; `pass` means the bounded, provider-free
   deterministic cohort passed. Neither is a live-provider result.
2. **Authority** says what the runtime may do now. A route at `review_only` /
   `reduced_authority` remains confirmation-gated with no tools, regardless of
   how much documented metadata it has.

The distinction is intentional: a transport-compatible HTTP shape, a large
advertised context window, or a reasoning default is not evidence of a safe
coding-agent route.

## Current Reference Route Cards

The values in the first five columns are declared catalog/profile metadata.
They are useful for selection and adapters, but are not live endpoint
measurements. `Context` is advertised context, `reasoning default` is
AstraBridge's normalized default request posture, and `transport` is the
current adapter protocol label.

| Exact route | Declared input modalities | Advertised context | Transport | Normalized reasoning default | Metadata evidence |
| --- | --- | --- | --- | --- | --- |
| `qwen/qwen3.7-plus` | `text, image` | `1,000,000` advertised | `responses` | `medium` | `documented` |
| `deepseek/deepseek-v4-pro` | `text` | `1,000,000` advertised | `chat` | `high` | `documented` |
| `kimi/kimi-k3` | `text, image, video` | `1,048,576` advertised | `chat` | `xhigh` | `documented` |
| `glm/glm-5.2` | `text` | `1,000,000` advertised | `chat` | `xhigh` | `documented` |

The deterministic reference cohort binds the exact model IDs above to adapter,
context, neutral-handoff, tool-receipt, and fallback checks without contacting
a provider. Its current route-authority result is deliberately the same for
all four routes:

| Exact route | Deterministic checks | Route admission / authority | Runtime posture | Exact next gate |
| --- | --- | --- | --- | --- |
| `qwen/qwen3.7-plus` | `pass` | `review_only` / `reduced_authority` | `no_tools` / `ask` | `execution_route_adapter_dry_run` |
| `deepseek/deepseek-v4-pro` | `pass` | `review_only` / `reduced_authority` | `no_tools` / `ask` | `execution_route_adapter_dry_run` |
| `kimi/kimi-k3` | `pass` | `review_only` / `reduced_authority` | `no_tools` / `ask` | `execution_route_adapter_dry_run` |
| `glm/glm-5.2` | `pass` | `review_only` / `reduced_authority` | `no_tools` / `ask` | `execution_route_adapter_dry_run` |

The rows do **not** claim output-modality reliability, endpoint-specific
context behavior, live reasoning behavior, tool support, autonomous writes,
or coding-route eligibility. The current cohort has no verified, experimental,
or default external coding-route claim.

## Meaning of the Public States

| State | Is a current reference route in this state? | Meaning and safe interpretation |
| --- | --- | --- |
| `core` | No external route is labeled core. | AstraBridge's own local runtime is a core product boundary; that does not promote an external API route. The recorded `openai/gpt-5.5` control receives no external-provider bypass. |
| `supported` | No. | Use only after the exact route completes its required evidence lifecycle; do not infer it from a provider family. |
| `experimental` | No current external coding-route claim. | A future explicitly scoped preview may be experimental, but it still needs a named evidence/authority boundary. |
| `reduced_authority` | Yes: all four rows above. | The route is inspectable and may be reviewed, but remains `review_only`, `no_tools`, and `ask`; it is not autonomous, default, or coding-route eligible. |
| `blocked` | Not in the current all-present baseline. | The evaluator blocks the exact route if its catalog model or semantic fixture is missing or mismatched. That is route-local, not a provider-wide failure. |
| `unknown` / `deferred` | Live provider smoke is deferred for all four rows. | No live result is available in this surface. Absence, expiration, or lack of authorization keeps authority downgraded rather than silently falling back. |

`documented` and `pass` are evidence labels, not substitutes for the authority
states in this table. A route can truthfully be both `documented` and
`reduced_authority`.

## Kimi K3 Is a Reference Record, Not an Exception

`kimi/kimi-k3` is present because its exact catalog record and deterministic
contract are available. Its declared `text, image, video` inputs, advertised
`1,048,576` context, `chat` transport, and `xhigh` normalized reasoning
default are metadata, not a live Kimi Platform result. Kimi K3 receives no
bypass: it follows the same lifecycle as Qwen, DeepSeek, and GLM:

`documented -> adapter_dry_run_passed -> provider_smoke_passed -> tool_contract_passed -> coding_route_verified -> default_route_eligible`

No provider credential is required, read, stored, or sent to inspect this
surface or run its deterministic checks. A provider-backed smoke is a separate
future operation requiring explicit current-turn authorization and a
secret-owning runner; even then, its result applies only to that exact route.

## Sources, Owners, and Defect Handoff

| Truth layer | Owner | Source of record | If it is wrong |
| --- | --- | --- | --- |
| Declared model, modality, context, transport, and reasoning fields | `provider-compatibility` | [Catalog and profile implementation](../apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/) and [Provider Capability and Reasoning Runbook](PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md) | Correct the model-level catalog/profile source and its focused contract test; do not invent a provider-wide capability. |
| Deterministic adapter, handoff, receipt, fallback, and context checks | `provider-adaptation` | [Reference cohort evaluator](../apps/astrabridge-sidecar/astrabridge_sidecar/providers/reference_cohort.py) and [focused cohort test](../apps/astrabridge-sidecar/tests/test_provider_reference_cohort.py) | Preserve a secret-free failing artifact, retain the route's downgrade, and repair the exact failed contract. |
| Route-admission and tool/write authority | `provider-adaptation` | [Codex-core multi-provider execution contract](../PLAN/CODEX_CORE_MULTI_PROVIDER_EXECUTION_CONTRACT.md) | Do not promote on metadata or a sibling route's evidence. Re-enter at the exact required promotion gate. |
| Public statement on this page | `open-source-productization` | [Product positioning and claim matrix](OPEN_SOURCE_PRODUCT_POSITIONING_AND_CLAIM_MATRIX.md) and this source-backed surface test | Remove or downgrade any claim that lacks current route-specific evidence. |

If a defect affects AstraBridge's shared task, permission, persistence,
recovery, or default-route behavior rather than a single provider adapter,
hand it to the [canonical product stability and interoperability plan](../PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md).
The handoff packet must name the exact route, expected and observed state,
focused command or sanitized artifact, source revision, and next gate. Do not
automatically retry through another endpoint, provider, model, or credential
scope.

## Reproduce the No-Provider Check

From `D:\AstraBridge\apps\astrabridge-sidecar`:

```powershell
python -m unittest tests.test_provider_truth_authority_surface tests.test_provider_reference_cohort
```

This command is provider-free. It checks that the public rows stay aligned to
the current catalog/profile and deterministic cohort. For the broader
maintenance and authorized-smoke procedure, use the
[Provider Capability and Reasoning Runbook](PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md).
