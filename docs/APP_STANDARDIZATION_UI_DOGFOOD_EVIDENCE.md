# AstraBridge UI Dogfood Evidence

## Step 23 repair round

- Date: 2026-07-15
- Scope: final task-graph route repair, template model defaults, dry-run interaction, and process hygiene.
- App URL: `http://127.0.0.1:4181/?astrabridge_launch=dogfood&sidecar=http%3A%2F%2F127.0.0.1%3A8852`
- Sidecar provenance: local `8852` API with the companion router listener on `8787`.
- Visible session: the existing in-app page showed the managed `astra` session before the browser control channel stopped responding.
- Operator mode: visible in-app UI clicks and read-only browser observation; no direct graph JSON submission or state injection.
- Provider calls this round: 0. Dry-run is a route/graph validation request and did not start model execution.
- Secret handling: no key file, Vault password, cookie, authorization header, or provider raw secret was read or persisted in this round.

## Repairs

1. Task-graph template recommendations now follow the effective model catalog when it is available and use current safe defaults when it is not. New template surfaces no longer recommend the retired `qwen3-coder-plus`, `glm-4.5`, or `deepseek-coder` names.
2. Terminal dry-run/run references retain sanitized worker bindings so the run inspector can explain the route after a completed validation.
3. Static template wording now says `Preflight` / `运行前要点`, making it clear that these are pre-run checks rather than the current run result.
4. Task-graph run controls use one native `click` path. The previous `pointerup` + `keydown` + `click` dispatch and time-window deduplication could lose or duplicate actions across browser-control implementations.

## UI evidence

- `PRIVATE/app-standardization-ui-dogfood/final/20260715-step23-release-gate/task-graph-dry-run-passed.png`
  - Valid visible task-graph screenshot.
  - Run inspection is open in the graph view.
  - Result is `PASS`, with `11 / 0 / 0` status counts and `没有阻塞或警告。`.
- `PRIVATE/app-standardization-ui-dogfood/final/20260715-step23-release-gate/template-screen-after-refresh.png`
  - Visible template browser after refresh.
  - Current recommended model names are rendered and the preflight label is present.
- `PRIVATE/app-standardization-ui-dogfood/final/20260715-step23-release-gate/task-graph-final-dry-run-passed.png`
  - Retained as a negative visual check: the capture completed after the page had returned to chat view, so it is not used as graph-view acceptance evidence.

## Automated verification

- Sidecar task-graph API tests: `12 passed`.
- Sidecar task-graph contract/persistence/worker tests: `62 passed, 14 subtests passed`.
- Desktop `TaskGraphWorkspace` tests: `82 passed`.
- Desktop TypeScript: `pnpm exec tsc --noEmit -p tsconfig.json` passed.
- Desktop production build: passed. Existing Vite warning remains because the `App` chunk is about 980 kB after minification.
- Process audit: exactly one expected frontend listener (`4181`) and one expected sidecar/router listener pair (`8852` / `8787`). The sidecar uses the repository virtual environment launcher and its child; no duplicate AstraBridge listener was found.
- Sidecar error log contains one preserved `ConnectionAbortedError` from the browser bridge aborting a request while the page-control channel timed out. This is a transport diagnostic, not evidence of an application route failure.

## Full gate audit

- Quick local gate: passed. Governance reported `0 error / 0 warning`, the secret scan reported `0`, the contract boundary audit passed, and its focused governance/security tests passed.
- Full local gate: not green. Governance, secret scan, contract audit, and the task-graph/API exercise passed; the complete sidecar suite ran `883` tests and reported `10 failures / 11 errors`.
- The full-suite failures cluster in the current automation-runner expectations, metadata/catalog fixture expectations, native-kernel permission fixtures, attachment capability fixtures, task conversation projection fixtures, and one asynchronous metadata-refresh timing case. They are separate from the Step 23 task-graph route repair; no provider call or secret was used to force the full-suite result.
- Release decision: keep Step 23 in progress. Do not claim the release gate is closed until the sidecar baseline is either repaired or explicitly rebaselined in a bounded follow-up with evidence.

## Remaining release-gate risks

- The in-app browser webview attachment channel became unresponsive after a click timeout. The existing broken tab was closed, and a replacement tab could not attach. This is recorded as `browser_webview_unavailable`; it prevents a fresh post-patch screenshot, but does not invalidate the earlier visible `PASS 11 / 0 / 0` screenshot or the HTTP 200 dry-run response.
- The four provider-backed dogfood workflows from Steps 16, 18, 20, and 22 are not all complete in this round. No claim is made that the full release gate is closed.
- Structured tool calling and MCP tool calling remain capability warnings for the current model route; they are surfaced in the inspector and are not silently treated as verified.
- The Vite chunk-size warning remains an optimization item, not a functional failure.
- Full sidecar regression is a separate baseline blocker: `run_local_gate.py --full` is not green even though the focused task-graph/UI gate is green. Its failures must be resolved or explicitly rebaselined before final release closure.

## Next entry

First triage the full sidecar baseline blocker without weakening the task-graph contract. Then restore a claimable in-app browser webview (without adding duplicate tabs), reload the current sidecar route, and repeat the visible task-graph Dry-run and screenshot gate. Continue the independent verifier pass for the remaining provider-backed workflows.

## Step 23 closure recheck

- Date: 2026-07-15.
- The historical full-gate failure above is preserved as a diagnostic record. The dependency and governance issues were repaired rather than suppressed: `Pillow` is now a runtime dependency, `pytest` and `jsonschema` are in the `dev` dependency group, `uv.lock` is regenerated, and generated `*.egg-info` directories are excluded from source governance scanning and git staging.
- Final full gate: `scripts/run_local_gate.py --full` passed. Governance reported `0 error / 0 warning`; the app-hardening secret scan reported `0 error / 0 warning`; contract-boundary audit passed; sidecar unittest discovery passed `884` tests; desktop tests passed `61` files / `448` tests; and the production TypeScript/Vite build passed. The Vite chunk-size warning remains an optimization warning only.
- Independent sidecar breakdown: `test_sidecar_services.py` passed `382`; the remaining sidecar suite passed `501` tests and `98` subtests. No provider call, token-consuming model run, key file, Vault password, cookie, authorization header, or raw provider secret was read or persisted.
- Process hygiene: the stale high-CPU sidecar instance was reaped using explicit AstraBridge ownership evidence and relaunched from current source. Final audit found one frontend listener on `4181` and one sidecar/router pair on `8852/8787`; no duplicate AstraBridge listener remained.
- Visible browser acceptance: the broken tab was closed, one replacement tab was opened, the managed `astra` session was visible, and only normal UI clicks were used to open Task Graph and click Dry-run. The run-check modal visibly reported `pass 11 / 0 / 0` and `no blocked or warning checks`. The final screenshot is `PRIVATE/app-standardization-ui-dogfood/final/20260715-step23-release-gate/task-graph-dry-run-final.png`.
- Remaining risk: the current route still surfaces capability warnings for unverified structured/MCP tool calling and the Vite chunk-size warning. These are visible, fail-closed signals and are not silently promoted to verified capability. Rapid repeated reloads may still destabilize the Codex browser-control transport, but the recovered single tab passed the final screenshot gate.
- Release decision: Step 23 is complete. Any later provider-backed expansion or browser-transport hardening must start under a new independent plan; this plan's historical failures must not be used as the current gate result.
