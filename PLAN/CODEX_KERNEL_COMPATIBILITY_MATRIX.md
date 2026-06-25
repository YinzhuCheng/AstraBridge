# Codex Kernel Compatibility Matrix

Last updated: 2026-06-25

## Purpose

This matrix ties an exact Codex CLI version and runtime lane to preserved AstraBridge evidence.

It exists to prevent two failure modes:

- treating a locally observed version as `verified` before a repeatable smoke suite exists
- discussing plugin or skill support in a way that hides current app-config limits or missing evidence

## Status Definitions

- `verified`: the exact binary/version/platform combination has probe evidence and preserved smoke evidence
- `probed`: the exact binary/version/platform combination has direct probe evidence, but no qualifying smoke evidence yet
- `partial`: only part of the required evidence exists for that runtime lane
- `blocked`: evidence shows an incompatible or broken kernel behavior for AstraBridge
- `unknown`: AstraBridge does not yet have enough trustworthy evidence to classify the lane

## Required Entry Schema

Each matrix entry must record these fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `matrix_id` | yes | Stable AstraBridge identifier for the assessed lane |
| `codex_version` | yes | Exact Codex CLI semver under assessment |
| `release_anchor` | yes | Upstream release line or tag used for orientation |
| `platform` | yes | `windows`, `wsl`, or another explicit execution platform |
| `execution_lane` | yes | Human-readable runtime lane description |
| `binary_locator` | yes | Exact binary path, configured locator, or explicit target root |
| `overall_status` | yes | One of `verified`, `probed`, `partial`, `blocked`, `unknown` |
| `probe_result` | yes | What has actually been observed or exercised |
| `smoke_result` | yes | `passed`, `failed`, `not_run`, or `not_applicable` |
| `known_breakages` | yes | Concrete incompatible behavior or explicit `none recorded` |
| `required_mitigations` | yes | Exact follow-up needed before promotion or rollout |
| `evidence_paths` | yes | Repo paths, artifact paths, or test references supporting the entry |
| `last_reviewed_at` | yes | Date of the most recent review |

## Promotion Rule

No entry may be promoted to `verified` unless both conditions are true:

1. the exact binary/version/platform has a preserved smoke artifact path
2. the smoke artifact is tied to probe evidence and an exact binary locator

For step 13 and later, run this gate before accepting a matrix edit that marks any entry `verified`:

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m astrabridge_sidecar.codex_kernel_matrix_gate --matrix D:\AstraBridge\PLAN\CODEX_KERNEL_COMPATIBILITY_MATRIX.md --repo-root D:\AstraBridge
```

The gate rejects:

- missing required entry fields
- missing evidence references
- any `verified` entry without an exact semver, a non-ambiguous binary locator, a passing smoke report, and a preserved kernel probe snapshot

## Current Assessed Entries

| Matrix ID | Version | Platform | Execution Lane | Overall Status | Probe Result | Smoke Result |
| --- | --- | --- | --- | --- | --- | --- |
| `AB-CODEX-20260625-WIN-0137` | `0.137.0` | `windows` | Native Windows Codex CLI plus app-server used by AstraBridge desktop runtime | `blocked` | Binary/version are observed; dedicated read-only probes exist and the no-key smoke suite now preserves a failing Windows artifact that captures `thread/resume` incompatibility plus missing MCP visibility | `failed` |
| `AB-CODEX-20260625-WSL-0137` | `0.137.0` target line | `wsl` | Linux-native Codex runtime launched through AstraBridge WSL bootstrap and rewrite layer | `partial` | Existing WSL readiness checks cover binary discovery, `codex --version`, and minimal app-server initialize smoke, but the new plugin/skill/MCP probe path is not yet recorded as WSL-specific evidence | `not_run` |

## Entry Details

### `AB-CODEX-20260625-WIN-0137`

- `matrix_id`: `AB-CODEX-20260625-WIN-0137`
- `codex_version`: `0.137.0`
- `release_anchor`: `codex-cli 0.137.0` / `rust-v0.137.0` / released 2026-06-04
- `platform`: `windows`
- `execution_lane`: `Native Windows Codex CLI plus app-server used by AstraBridge desktop runtime`
- `binary_locator`: `D:\Tools\OpenAI\Codex\bin\codex.EXE`
- `overall_status`: `blocked`
- `probe_result`: `Observed local baseline version is 0.137.0. AstraBridge now has documented probe contracts plus read-only probe helpers for binary/version, app-server protocol, MCP visibility, plugin discovery, and skill discovery. A preserved no-key Windows smoke artifact now exists and shows that the current lane is still incompatible for promotion because the thread lifecycle and MCP visibility checks fail under the isolated runtime.`
- `smoke_result`: `failed`
- `known_breakages`:
  - `thread_resume_returns_no_rollout_found`
  - `mcp_server_status_list_times_out`
  - `app_owned_mcp_servers_not_visible_in_isolated_codex_home`
  - `rendered_config_disables_plugins`
  - `app_server_flags_fragile`
- `required_mitigations`:
  - `Investigate the Codex 0.137.0 thread/resume rollout contract before promoting the Windows lane.`
  - `Investigate why mcpServerStatus/list times out and app-owned MCP servers remain invisible in the isolated CODEX_HOME smoke workspace.`
  - `Keep overall_status below verified until a preserved smoke report passes and the step 13 gate validates the updated entry.`
- `evidence_paths`:
  - `PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md`
  - `PLAN/CODEX_KERNEL_COMPATIBILITY_SURFACE_MAP.md`
  - `PLAN/CODEX_KERNEL_PROBE_CONTRACT.md`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/codex_kernel_probe.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/codex_app_server_probe.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/codex_kernel_matrix_gate.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/codex_mcp_probe.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/codex_plugin_probe.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/codex_skill_probe.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/codex_kernel_smoke.py`
  - `apps/astrabridge-sidecar/tests/test_codex_kernel_probe.py`
  - `apps/astrabridge-sidecar/tests/test_codex_app_server_probe.py`
  - `apps/astrabridge-sidecar/tests/test_codex_kernel_matrix_gate.py`
  - `apps/astrabridge-sidecar/tests/test_codex_mcp_probe.py`
  - `apps/astrabridge-sidecar/tests/test_codex_plugin_probe.py`
  - `apps/astrabridge-sidecar/tests/test_codex_skill_probe.py`
  - `apps/astrabridge-sidecar/tests/test_codex_kernel_smoke.py`
  - `PRIVATE/demo-runs/codex-kernel-smoke-20260625T161220655872-c1aced/reports/kernel-probe-snapshot.json`
  - `PRIVATE/demo-runs/codex-kernel-smoke-20260625T161220655872-c1aced/reports/smoke-report.json`
- `last_reviewed_at`: `2026-06-25`

### `AB-CODEX-20260625-WSL-0137`

- `matrix_id`: `AB-CODEX-20260625-WSL-0137`
- `codex_version`: `0.137.0` target line
- `release_anchor`: `codex-cli 0.137.0` / `rust-v0.137.0` / released 2026-06-04
- `platform`: `wsl`
- `execution_lane`: `Linux-native Codex runtime launched through AstraBridge WSL bootstrap and rewrite layer`
- `binary_locator`: `ASTRABRIDGE_WSL_CODEX_BIN` or `$HOME/.local/share/astrabridge/bin/codex`
- `overall_status`: `partial`
- `probe_result`: `AstraBridge already contains WSL readiness checks for Linux-native Codex discovery, version output, and a minimal initialize-path smoke. That is useful evidence, but the new step-3-through-step-7 probe helpers have not yet been aggregated into a WSL-specific compatibility snapshot, and no preserved WSL kernel smoke artifact exists.`
- `smoke_result`: `not_run`
- `known_breakages`:
  - `wsl_runtime_requires_linux_native_codex`
  - `rendered_config_disables_plugins`
  - `wsl_probe_coverage_incomplete_for_plugin_and_skill_surfaces`
- `required_mitigations`:
  - `Run the step 9 snapshot path against the WSL lane once available.`
  - `Run the step 12 kernel smoke suite against the Linux-native WSL binary and preserve the artifact path.`
  - `Verify MCP path rewriting and plugin/skill discovery behavior after WSL config sync.`
- `evidence_paths`:
  - `PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md`
  - `PLAN/CODEX_KERNEL_COMPATIBILITY_SURFACE_MAP.md`
  - `PLAN/CODEX_KERNEL_PROBE_CONTRACT.md`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/wsl_dependency_service.py`
  - `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
- `last_reviewed_at`: `2026-06-25`

## Next Update Conditions

Update this matrix when any of the following happens:

- the active Codex CLI version changes
- the binary locator changes
- a new probe surface lands
- the kernel smoke suite produces a preserved artifact
- plugin/skill feature flags or app-server launch flags change

When updating an entry, preserve the old entry until the replacement has its own evidence path.
