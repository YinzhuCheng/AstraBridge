# Codex Kernel Compatibility Surface Map

Last updated: 2026-06-25

## Purpose

This document inventories the current AstraBridge touchpoints that depend on official Codex CLI and Codex app-server behavior. It defines the compatibility boundary for future kernel probes, upgrade gates, and plugin/skill integration work.

Classification used in this map:

- `stable`: app-owned integration point with low ambiguity; behavior is mostly under AstraBridge control
- `probed`: integration point already has an explicit status check or smoke-like validation path
- `fragile`: integration point depends on exact Codex CLI/app-server flags, request shapes, notification shapes, or process behavior that could break on upgrade
- `unknown`: protocol or catalog surface exists in generated/types or planning assumptions, but AstraBridge does not yet actively probe or consume it

## Current Baseline

- Observed local Windows CLI: `D:\Tools\OpenAI\Codex\bin\codex.EXE`
- Observed CLI version: `codex-cli 0.137.0`
- Product baseline constant: `CODEX_CLI_BASELINE = "0.137.0"`
- Normal product state boundary: `.abproj`, workspace-local `.astrabridge/`, AstraBridge-managed app data, AstraBridge-managed isolated `CODEX_HOME`
- Explicit non-goal boundary: official Codex `~/.codex/config.toml`, project `.codex*`, official account-login path

## Dependency Inventory

| Surface | Current dependency on Codex kernel | Classification | Why it matters for upgrades | Owning files |
| --- | --- | --- | --- | --- |
| Binary resolution on Windows | Runtime launch resolves Codex from `ASTRABRIDGE_CODEX_BIN` or `shutil.which("codex")` and fails send/start if missing. | `stable` | CLI relocation or binary naming changes will break runtime start immediately. | `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/common.py` |
| Binary resolution in WSL | WSL launch resolves a Linux-native Codex binary from `ASTRABRIDGE_WSL_CODEX_BIN` or `$HOME/.local/share/astrabridge/bin/codex`. | `stable` | WSL runtime is separate from Windows runtime and must stay Linux-native. | `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/wsl_dependency_service.py` |
| Runtime environment status | Sidecar exposes `codex_cli`, host, distro, running state, and redacted runtime config through `RuntimeService.environment()`. | `stable` | Desktop and audits depend on this as the current source of truth for active kernel state. | `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, `apps/astrabridge-desktop/src/types.ts` |
| Isolated `CODEX_HOME` policy | Runtime config writes into AstraBridge-managed `CODEX_HOME` and exports `CODEX_HOME` to subprocesses and app-server launch paths. | `stable` | Isolation is a product invariant; upgrade work must preserve it. | `apps/astrabridge-sidecar/astrabridge_sidecar/common.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/automations/runner.py`, `docs/SECURITY_AND_ISOLATION.md` |
| Rendered `config.toml` contract | AstraBridge writes a Codex `config.toml` with model, provider, reasoning effort, catalog path, MCP config, and feature flags. | `fragile` | Any schema or option-name drift in Codex config can silently degrade runtime behavior. | `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py` |
| Feature gating via config | Rendered config currently forces `[features] plugins = false`, `plugin_sharing = false`, and `remote_plugin = false`. | `fragile` | Plugin integration work must revisit this; Codex flag semantics may change across versions. | `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py` |
| Provider routing via Codex model provider config | AstraBridge injects custom `model_providers.<provider>` sections that point back to the local router and use `CODEX_ROUTER_API_KEY`. | `fragile` | This depends on Codex continuing to honor current provider config fields and routing behavior. | `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py` |
| Model catalog baseline | AstraBridge maintains a Codex-facing model catalog and encodes a baseline CLI version constant. | `stable` | Compatibility work needs to know whether catalog assumptions remain valid under newer kernels. | `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py` |
| App-server process launch contract | App-server is launched either as `codex app-server --listen stdio://` or via WSL with websocket transport and `--disable plugins --disable plugin_sharing --disable remote_plugin`. | `fragile` | These exact flags and transport modes are kernel-facing dependencies and are likely upgrade breakpoints. | `apps/astrabridge-sidecar/astrabridge_sidecar/app_server_client.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/wsl_dependency_service.py` |
| App-server initialization handshake | AstraBridge sends JSON-RPC `initialize` with `experimentalApi: true` and `requestAttestation: false`, then emits `initialized`. | `fragile` | Request/response shape or required capability fields could change between Codex releases. | `apps/astrabridge-sidecar/astrabridge_sidecar/app_server_client.py`, `apps/astrabridge-desktop/src/protocol/generated/InitializeResponse.ts` |
| Core app-server request set | Generated request types include `thread/start`, `thread/resume`, `thread/fork`, `turn/start`, approvals, MCP reload, `plugin/list`, `plugin/install`, `skills/list`, and related methods. | `unknown` | The protocol surface exists locally, but AstraBridge has not yet built a dedicated compatibility probe for these methods. | `apps/astrabridge-desktop/src/protocol/generated/ClientRequest.ts` |
| Core app-server notification set | Generated server notifications include thread lifecycle, turn lifecycle, MCP server status, skill changes, reasoning deltas, and realtime events. | `fragile` | Runtime orchestration depends on exact notification semantics and event continuity. | `apps/astrabridge-desktop/src/protocol/generated/ServerNotification.ts` |
| Desktop protocol-generated plugin surface | Generated v2 types describe plugin list/read/install/uninstall, plugin details, icons, screenshots, shares, and app/plugin relations. | `unknown` | AstraBridge carries the schema but does not yet consume it through a product UI or sidecar API. | `apps/astrabridge-desktop/src/protocol/generated/v2/Plugin*.ts`, `apps/astrabridge-desktop/src/protocol/generated/v2/AppInfo.ts`, `apps/astrabridge-desktop/src/protocol/generated/v2/AppSummary.ts` |
| Desktop protocol-generated skill surface | Generated v2 types describe `skills/list`, skill metadata, `skills/changed`, skill config write, and skill references in user input. | `unknown` | This is the main protocol entry point for future skill integration, but it is not yet probed or surfaced in AstraBridge UI. | `apps/astrabridge-desktop/src/protocol/generated/v2/Skills*.ts`, `apps/astrabridge-desktop/src/protocol/generated/v2/UserInput.ts`, `apps/astrabridge-desktop/src/protocol/generated/v2/AskForApproval.ts` |
| WSL readiness and smoke | WSL dependency status actively checks `codex --version`, `command -v codex`, and a minimal `initialize` app-server smoke through stdio. | `probed` | This is the closest existing kernel probe and should be reused, not replaced blindly. | `apps/astrabridge-sidecar/astrabridge_sidecar/wsl_dependency_service.py`, `apps/astrabridge-desktop/src/App.tsx` |
| WSL config sync and path rewriting | Before WSL app-server launch, AstraBridge rewrites `config.toml`, translates Windows paths to WSL paths, and patches stdio MCP commands to Linux-friendly values. | `fragile` | Codex config schema changes, MCP block changes, or WSL path assumptions can break the WSL runtime. | `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` |
| Runtime launch cwd isolation | App-server is intentionally launched from `<workspace>/.astrabridge/runtime-cwd` instead of the workspace root. | `stable` | Upgrade work must preserve this process-local file isolation behavior. | `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` |
| MCP config rendering | AstraBridge renders Codex MCP TOML from app-owned JSON config and injects presets such as `context7`, `astrabridge_web`, `yunwu_image`, and `astrabridge_capabilities`. | `stable` | Plugin/skill work will sit next to this surface and must avoid regressing current MCP behavior. | `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_config_service.py`, `apps/astrabridge-desktop/src/features/i18n/catalog.ts` |
| Capability runtime MCP dependency | Capability UI and capability MCP server assume Codex can load `astrabridge_capabilities` from isolated `CODEX_HOME`. | `probed` | Existing UI smoke covers the preset as visible product behavior, but there is no general kernel MCP compatibility probe yet. | `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_config_service.py`, `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.tsx`, `PLAN/CAPABILITY_RUNTIME_SURFACE_MAP.md` |
| Automation standalone execution | Standalone automation shells out to `codex exec <prompt>` and maps AstraBridge permission modes to Codex sandbox flags. | `fragile` | Any CLI syntax drift in `codex exec` or sandbox flags will break automation runs. | `apps/astrabridge-sidecar/astrabridge_sidecar/automations/runner.py`, `PLAN/AUTOMATIONS_SURFACE_MAP.md` |
| Runtime UI assumptions | The Runtime setup panel currently exposes WSL bootstrap status, isolated `CODEX_HOME`, and runtime/isolation audit results, but not plugin/skill/kernel compatibility status. | `stable` | This is the intended first UI landing zone for new kernel compatibility status. | `apps/astrabridge-desktop/src/App.tsx`, `apps/astrabridge-desktop/src/types.ts` |
| Documentation and operator claims | Docs explicitly claim isolated state, Codex CLI/app-server runtime patterns, WSL-managed install, and no normal dependency on official Codex state. | `stable` | Upgrade and plugin work must either preserve these claims or update docs and gates in lockstep. | `docs/ARCHITECTURE.md`, `docs/HANDOFF.md`, `docs/SECURITY_AND_ISOLATION.md`, `docs/RELEASE_CHECKLIST.md` |

## Compatibility Boundary

The current Codex kernel compatibility boundary for AstraBridge is:

1. Codex CLI binary discovery and launch
2. Codex `config.toml` schema currently written by AstraBridge
3. Codex app-server transport and JSON-RPC protocol used by `AppServerClient`
4. Codex model-provider routing behavior for local router-backed providers
5. Codex MCP loading behavior from isolated `CODEX_HOME`
6. Codex WSL app-server behavior and Linux-native install path
7. Codex `exec` CLI behavior used by standalone automations
8. Generated protocol surfaces for plugins and skills, even where not yet productized

Everything outside that list should be treated as either:

- an explicit non-goal for current product behavior, such as official Codex user config or official account login
- a future integration area that must be added only through probed and documented surfaces

## Current Gaps

The inventory shows these immediate gaps:

- There is no single secret-free kernel probe snapshot yet.
- There is no compatibility matrix tying exact Codex versions to evidence.
- Plugin and skill protocol surfaces exist in generated types, but AstraBridge does not yet expose them through sidecar APIs or UI.
- Current WSL smoke is useful but too narrow to serve as the full kernel compatibility gate.
- Automation `codex exec` compatibility is not independently probed.
- Current runtime config disables plugin-related features, which is correct for today's baseline but blocks future plugin integration until deliberately redesigned.

## Recommended Next Step

The next implementation step should define a secret-free `CodexKernelProbeSnapshot` contract that can cover the inventory above without mutating user state or relying on private official Codex App APIs.
