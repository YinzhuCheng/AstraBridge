# Codex Kernel Probe Contract

Last updated: 2026-06-25

## Purpose

This document defines the JSON contract for a secret-free `CodexKernelProbeSnapshot`.

The contract is designed for:

- read-only kernel inspection
- compatibility matrix evidence
- runtime UI status rendering
- upgrade smoke gating
- future plugin and skill integration checks

The probe output must be safe to persist in git-ignored validation paths such as `PRIVATE/**` or workspace-local runtime evidence paths after normal redaction rules are applied.

## Design Rules

`CodexKernelProbeSnapshot` must follow these rules:

- It must not contain API keys, bearer tokens, cookies, auth headers, refresh tokens, session tokens, account emails, account IDs, or provider raw secrets.
- It may contain filesystem paths, CLI version strings, feature support states, environment variable names, MCP server names, plugin IDs, skill names, and warning strings.
- It must distinguish observed facts from inferred compatibility.
- It must be valid even when the probe is partial, unsupported, or interrupted.
- It must allow later probe steps to append richer evidence without breaking existing consumers.

## Fact Boundary

The snapshot is split into two top-level sections:

- `observed`: direct facts collected from the current environment, current generated protocol files, current rendered config, or current read-only CLI/app-server interactions
- `inferred`: AstraBridge's compatibility judgement derived from observed facts

Rule:

- `observed` must not claim `verified`, `partial`, `blocked`, `ready`, or similar product-level conclusions unless those words are part of an upstream raw status string.
- `inferred` is the only place allowed to summarize upgrade readiness, plugin readiness, skill readiness, or compatibility risk.

## JSON Shape

```json
{
  "schema_version": "codex-kernel-probe-v1",
  "generated_at": "2026-06-25T15:12:03+08:00",
  "probe_run_id": "kernel-probe-20260625T151203-abc123",
  "observed": {
    "binary": {},
    "platform": {},
    "runtime_roots": {},
    "app_server": {},
    "protocol_features": {},
    "mcp_features": {},
    "plugin_features": {},
    "skill_features": {}
  },
  "inferred": {
    "compatibility_status": "unknown",
    "compatibility_summary": null,
    "kernel_upgrade_readiness": "unknown",
    "plugin_integration_readiness": "unknown",
    "skill_integration_readiness": "unknown",
    "risk_flags": [],
    "required_follow_up_checks": []
  },
  "known_warnings": [],
  "evidence": {
    "sources": [],
    "commands": [],
    "artifacts": []
  }
}
```

## Top-Level Fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | `string` | yes | Contract version, starting at `codex-kernel-probe-v1`. |
| `generated_at` | `string` | yes | Snapshot completion timestamp in ISO 8601 format. |
| `probe_run_id` | `string` | yes | Stable identifier for one probe execution. |
| `observed` | `object` | yes | Fact-only runtime/kernel observation block. |
| `inferred` | `object` | yes | Compatibility judgement derived from `observed`. |
| `known_warnings` | `array<string>` | yes | Secret-free warnings that do not fit one feature block. |
| `evidence` | `object` | yes | Secret-free references to files, commands, or sources used to build the snapshot. |

## Observed Section

### `observed.binary`

Binary discovery and version facts.

```json
{
  "path": "D:\\Tools\\OpenAI\\Codex\\bin\\codex.EXE",
  "path_source": "ASTRABRIDGE_CODEX_BIN",
  "version_text": "codex-cli 0.137.0",
  "version_semver": "0.137.0",
  "version_parse_status": "ok",
  "launch_descriptor": "D:\\Tools\\OpenAI\\Codex\\bin\\codex.EXE"
}
```

Required fields:

- `path`: `string | null`
- `path_source`: `"env_override" | "which" | "wsl_default" | "runtime_status" | "unknown"`
- `version_text`: `string | null`
- `version_semver`: `string | null`
- `version_parse_status`: `"ok" | "missing" | "unparseable" | "error" | "not_checked"`
- `launch_descriptor`: `string | null`

### `observed.platform`

Platform and host facts.

```json
{
  "execution_host": "windows",
  "platform_family": "windows",
  "platform_os": "windows",
  "wsl_distro": null
}
```

Required fields:

- `execution_host`: `"windows" | "wsl" | "unknown"`
- `platform_family`: `string | null`
- `platform_os`: `string | null`
- `wsl_distro`: `string | null`

### `observed.runtime_roots`

Isolated runtime root facts.

```json
{
  "isolated_codex_home": "C:\\Users\\name\\AppData\\Local\\AstraBridge\\cx",
  "codex_home_source": "astrabridge_default",
  "project_runtime_root": "D:\\AstraBridge\\PRIVATE\\demo-runs\\example\\AppData\\runtime\\projects\\Codex-Workspace",
  "workspace_runtime_cwd": "D:\\repo\\.astrabridge\\runtime-cwd"
}
```

Required fields:

- `isolated_codex_home`: `string | null`
- `codex_home_source`: `"ASTRABRIDGE_CODEX_HOME" | "astrabridge_default" | "resolver" | "runtime_status" | "unknown"`
- `project_runtime_root`: `string | null`
- `workspace_runtime_cwd`: `string | null`

### `observed.app_server`

Current app-server availability and transport facts.

```json
{
  "transport": "stdio",
  "launch_mode": "direct",
  "available": true,
  "initialize_status": "supported",
  "thread_start_status": "unknown",
  "thread_resume_status": "unknown",
  "turn_start_status": "unknown",
  "approval_events_status": "unknown",
  "mcp_elicitation_status": "unknown",
  "disconnect_status": "not_observed",
  "error_shape_status": "unknown",
  "last_checked_at": "2026-06-25T15:12:03+08:00"
}
```

Required fields:

- `transport`: `"stdio" | "websocket" | "unknown"`
- `launch_mode`: `"direct" | "wsl_exec" | "reused_client" | "unknown"`
- `available`: `boolean`
- `initialize_status`: support enum
- `thread_start_status`: support enum
- `thread_resume_status`: support enum
- `turn_start_status`: support enum
- `approval_events_status`: support enum
- `mcp_elicitation_status`: support enum
- `disconnect_status`: `"not_observed" | "clean" | "unexpected" | "error" | "unknown"`
- `error_shape_status`: support enum
- `last_checked_at`: `string | null`

### `observed.protocol_features`

Secret-free protocol capability hints. These are still facts because they describe what was observed in generated types or live app-server interactions, not whether AstraBridge should trust them.

```json
{
  "source_kind": "generated_types_and_runtime",
  "client_methods": {
    "initialize": "supported",
    "thread/start": "declared",
    "thread/resume": "declared",
    "turn/start": "declared",
    "plugin/list": "declared",
    "skills/list": "declared",
    "mcpServerStatus/list": "declared"
  },
  "server_notifications": {
    "thread/started": "declared",
    "turn/started": "declared",
    "skills/changed": "declared",
    "mcpServer/startupStatus/updated": "declared"
  },
  "notes": []
}
```

Required fields:

- `source_kind`: `"runtime_only" | "generated_types_only" | "generated_types_and_runtime" | "unknown"`
- `client_methods`: `record<string, protocol-status>`
- `server_notifications`: `record<string, protocol-status>`
- `notes`: `array<string>`

`protocol-status` enum:

- `"supported"`
- `"declared"`
- `"unsupported"`
- `"disabled_by_app"`
- `"not_checked"`
- `"error"`
- `"unknown"`

### `observed.mcp_features`

MCP visibility facts for isolated `CODEX_HOME`.

```json
{
  "config_render_status": "supported",
  "config_updated_at": "2026-06-25T14:55:12+08:00",
  "reload_status": "declared",
  "server_status_list_status": "declared",
  "expected_servers": [
    "astrabridge_capabilities",
    "astrabridge_web",
    "context7"
  ],
  "visible_servers": [],
  "expected_tools": [
    "astrabridge_capability_routes"
  ],
  "visible_tools": [],
  "notes": []
}
```

Required fields:

- `config_render_status`: support enum
- `config_updated_at`: `string | null`
- `reload_status`: protocol-status
- `server_status_list_status`: protocol-status
- `expected_servers`: `array<string>`
- `visible_servers`: `array<string>`
- `expected_tools`: `array<string>`
- `visible_tools`: `array<string>`
- `notes`: `array<string>`

### `observed.plugin_features`

Plugin discovery and plugin-management facts.

```json
{
  "config_feature_state": "disabled_by_app",
  "list_status": "declared",
  "installed_status": "declared",
  "read_status": "declared",
  "install_status": "declared",
  "uninstall_status": "declared",
  "share_status": "declared",
  "marketplace_status": "declared",
  "discovered_plugins": [],
  "notes": []
}
```

Required fields:

- `config_feature_state`: `"enabled" | "disabled_by_app" | "unknown"`
- `list_status`: protocol-status
- `installed_status`: protocol-status
- `read_status`: protocol-status
- `install_status`: protocol-status
- `uninstall_status`: protocol-status
- `share_status`: protocol-status
- `marketplace_status`: protocol-status
- `discovered_plugins`: `array<PluginProbeRecord>`
- `notes`: `array<string>`

`PluginProbeRecord`:

```json
{
  "plugin_id": "example-plugin",
  "display_name": "Example Plugin",
  "version": "1.2.3",
  "source_kind": "local_marketplace",
  "availability": "installed"
}
```

Required fields:

- `plugin_id`: `string`
- `display_name`: `string | null`
- `version`: `string | null`
- `source_kind`: `"local_marketplace" | "remote_marketplace" | "installed_root" | "shared_remote" | "unknown"`
- `availability`: `"installed" | "available" | "unavailable" | "unknown"`

### `observed.skill_features`

Skill discovery and skill-config facts.

```json
{
  "list_status": "declared",
  "extra_roots_status": "declared",
  "config_write_status": "declared",
  "change_notification_status": "declared",
  "discovered_roots": [],
  "discovered_skills": [],
  "notes": []
}
```

Required fields:

- `list_status`: protocol-status
- `extra_roots_status`: protocol-status
- `config_write_status`: protocol-status
- `change_notification_status`: protocol-status
- `discovered_roots`: `array<string>`
- `discovered_skills`: `array<SkillProbeRecord>`
- `notes`: `array<string>`

`SkillProbeRecord`:

```json
{
  "skill_name": "frontend-ui-engineering",
  "display_name": "frontend-ui-engineering",
  "source_kind": "local_skill_root",
  "owner_plugin_id": null,
  "enablement": "unknown"
}
```

Required fields:

- `skill_name`: `string`
- `display_name`: `string | null`
- `source_kind`: `"local_skill_root" | "plugin" | "project_root" | "remote_catalog" | "unknown"`
- `owner_plugin_id`: `string | null`
- `enablement`: `"enabled" | "disabled" | "unknown"`

## Inferred Section

This section converts observations into product judgements. These fields must never be copied directly from upstream raw output without interpretation.

```json
{
  "compatibility_status": "probed",
  "compatibility_summary": "Binary resolution and baseline version are known, but app-server, plugin, and skill behavior are only partially checked.",
  "kernel_upgrade_readiness": "partial",
  "plugin_integration_readiness": "blocked_by_app_config",
  "skill_integration_readiness": "declared_not_probed",
  "risk_flags": [
    "app_server_flags_fragile",
    "plugin_features_disabled_in_rendered_config"
  ],
  "required_follow_up_checks": [
    "binary_version_probe",
    "app_server_protocol_probe",
    "plugin_discovery_probe",
    "skill_discovery_probe"
  ]
}
```

Required fields:

- `compatibility_status`: `"verified" | "probed" | "partial" | "blocked" | "unknown"`
- `compatibility_summary`: `string | null`
- `kernel_upgrade_readiness`: `"ready" | "partial" | "blocked" | "unknown"`
- `plugin_integration_readiness`: `"ready" | "partial" | "blocked_by_app_config" | "declared_not_probed" | "unknown"`
- `skill_integration_readiness`: `"ready" | "partial" | "declared_not_probed" | "unknown"`
- `risk_flags`: `array<string>`
- `required_follow_up_checks`: `array<string>`

## Warnings And Evidence

### `known_warnings`

Use this for high-signal warnings that should be rendered directly in UI or logs.

Examples:

- `"rendered_config_disables_plugins"`
- `"wsl_runtime_requires_linux_native_codex"`
- `"app_server_protocol_only_declared_not_probed"`

### `evidence`

`evidence` keeps a compact audit trail without storing secret-bearing output.

```json
{
  "sources": [
    "apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py",
    "apps/astrabridge-desktop/src/protocol/generated/ClientRequest.ts"
  ],
  "commands": [
    {
      "command": "codex --version",
      "status": "ok"
    }
  ],
  "artifacts": [
    "PRIVATE/demo-runs/codex-kernel-smoke-20260625-151203/probe.json"
  ]
}
```

Required fields:

- `sources`: `array<string>`
- `commands`: `array<CommandEvidence>`
- `artifacts`: `array<string>`

`CommandEvidence`:

- `command`: `string`
- `status`: `"ok" | "failed" | "skipped"`

Optional fields:

- `summary`: `string | null`

## Null And Partial Rules

- A probe may emit `null` for unknown path, version, platform, or timestamps.
- Unsupported plugin or skill commands must not fail the whole contract; they must be represented with status fields such as `unsupported`, `disabled_by_app`, or `unknown`.
- Missing runtime client state must not erase filesystem or generated-type observations collected in the same run.
- When no direct runtime check was performed, feature status should be `declared` or `not_checked`, not `supported`.

## Redaction Rules

The probe writer must redact or omit:

- provider secret values
- bearer tokens
- session tokens
- account names, emails, or IDs
- raw OAuth payloads
- raw MCP auth headers
- raw plugin install credentials

Allowed:

- environment variable names such as `CODEX_ROUTER_API_KEY`
- plugin IDs
- skill names
- MCP server names
- filesystem paths inside AstraBridge-managed roots
- CLI stderr/stdout summaries only after redaction and truncation

## Minimum Contract For Step 3

The first implementation slice only needs to populate these fields:

- `schema_version`
- `generated_at`
- `probe_run_id`
- `observed.binary`
- `observed.platform.execution_host`
- `observed.platform.wsl_distro`
- `observed.runtime_roots.isolated_codex_home`
- placeholder `observed.app_server`, `observed.mcp_features`, `observed.plugin_features`, and `observed.skill_features` with `not_checked` or `unknown`
- `inferred.compatibility_status`
- `known_warnings`
- `evidence.sources`

Later steps should fill the rest without breaking the shape.
