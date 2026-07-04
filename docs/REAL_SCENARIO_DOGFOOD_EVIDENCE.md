# Real Scenario Dogfood Evidence Contract

This document defines the reusable evidence contract for:

- `PLAN/CAPABILITY_REAL_SCENARIO_DOGFOOD_PLAN.md`
- the five capability families: `automations`, `plugins`, `skills`, `multimodal-routes`, `web`
- any combined or cross-capability acceptance step that reuses the same artifact model

It is intentionally narrow: it standardizes where evidence lives, how files are named, and what each structured report must contain. It does not change product runtime behavior.

## Canonical roots

Use these roots consistently unless the active plan explicitly records a justified exception:

- UI screenshots:
  - `apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/`
- Structured dogfood reports:
  - `apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/`
- Workspace-local capability or research artifacts:
  - `.astrabridge/`
- Preserved demo-run evidence when a smoke script or sidecar flow already writes there:
  - `PRIVATE/demo-runs/`

Path rules:

- Prefer repo-relative paths for tracked files under the repository root.
- Use absolute Windows paths only for workspace-local or runtime-owned artifacts that are not stable git-tracked files.
- Do not point evidence paths outside the intended workspace or approved AstraBridge runtime roots.

## Naming contract

### Screenshot and JSON file prefix

Use:

`stepNN-<capability>-<scenario>-<status>`

Examples:

- `step04-cross-capability-schema-reference.png`
- `step08-plugins-fixture-install-pass.png`
- `step20-web-deep-search-fail.png`
- `step15-automations-project-health-report.json`

### Capability segment

Use one of:

- `automations`
- `plugins`
- `skills`
- `multimodal-routes`
- `web`
- `cross-capability`

### Status segment

Use one of:

- `entry`
- `running`
- `pass`
- `partial`
- `fail`
- `timeout`
- `skipped`
- `reference`

### Multi-capture suffix

If one step needs multiple screenshots of the same phase, append `-01`, `-02`, and so on after the status segment.

Example:

- `step20-web-deep-search-running-01.png`
- `step20-web-deep-search-running-02.png`

## Structured report contract

Every structured dogfood report must validate against:

- [REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA.json](/D:/AstraBridge/docs/REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA.json)

Required top-level semantics:

- `schema_version`: fixed report schema id
- `plan_id`: fixed plan id for this execution track
- `step_id`: step such as `step_08`
- `capability`: capability family
- `scenario_id`: stable short id for the scenario
- `trigger_path`: the UI/API path used to run the scenario
- `status`: `pass`, `fail`, `partial`, `timeout`, or `skipped`
- `started_at` and `completed_at`: ISO-8601 timestamps
- `screenshots`: one or more screenshot references
- `artifacts`: referenced outputs, logs, manifests, research records, or saved results
- `verification_commands`: exact commands used to verify the result

Conditionally required semantics:

- `failure_reason` is required when `status` is `fail` or `timeout`.
- `skip_reason` is required when `status` is `skipped`.
- At least one screenshot with `kind="failure"` is required for failed or timed-out runs.
- `record_id` or `run_id` should be present when the product creates a stable persisted identifier.

## Screenshot rules

- Never capture secrets, plaintext keys, vault passwords, cookies, or authorization headers.
- Prefer Chinese-mode UI when the scenario is primarily user-facing.
- Capture enough context to prove the claim:
  - entry state if setup matters
  - running state when async execution matters
  - final success or failure state
- For layout bugs, keep the screenshot wide enough to show the broken or fixed region in context.

Recommended screenshot `kind` values:

- `entry`
- `running`
- `success`
- `failure`
- `detail`
- `reference`

## Artifact rules

Each `artifacts[]` item should identify what the file proves, not just where it is:

- `kind`: `report`, `record`, `manifest`, `log`, `image`, `audio`, `document`, `json`, `other`
- `role`: why the artifact matters, such as `plugin-manifest`, `research-record`, `skill-output`, `automation-run-log`
- `path`: absolute or repo-relative path
- `sensitive`: must stay `false` for persisted dogfood evidence

If an artifact is secret-bearing or suspected to be secret-bearing, do not include it in persisted evidence. Replace it with a redacted derivative or a summary note.

## Verification command rules

Each verification command entry should preserve:

- `command`: exact command text
- `cwd`: working directory
- `exit_code`: numeric result when known
- `summary`: brief human-readable outcome

If a step has no shell command and is verified entirely through UI inspection, still include an empty array in JSON and record the UI-only evidence in `notes`.

## Minimal pass criteria by status

- `pass`
  - at least one success screenshot
  - at least one verification command or explicit UI-only note
  - artifact or identifier proving the result exists

- `partial`
  - evidence proving the completed part
  - `notes` describing the missing part
  - if there was a product failure, include `failure_reason`

- `fail`
  - at least one failure screenshot
  - `failure_reason`
  - any surviving artifacts or logs that explain the failure

- `timeout`
  - at least one failure screenshot
  - `failure_reason`
  - timeout should not be reported as generic failure without saying it timed out

- `skipped`
  - `skip_reason`
  - usually used for not-authorized paid-provider checks or intentionally deferred unsafe actions

## Example scenario ids

- `plugins_fixture_install_cycle`
- `skills_plugin_creator_fixture_scaffold`
- `automations_project_health_check`
- `multimodal_routes_voice_dry_run`
- `web_deep_search_public_docs`

## Example report skeleton

```json
{
  "schema_version": "astrabridge-real-scenario-dogfood-report-v1",
  "plan_id": "capability_real_scenario_dogfood",
  "step_id": "step_08",
  "capability": "plugins",
  "scenario_id": "plugins_fixture_install_cycle",
  "trigger_path": "sidebar -> 插件 -> fixture plugin detail",
  "status": "pass",
  "started_at": "2026-06-26T10:00:00Z",
  "completed_at": "2026-06-26T10:04:00Z",
  "record_id": "fixture-plugin-install-001",
  "screenshots": [
    {
      "kind": "success",
      "path": "apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step08-plugins-fixture-install-pass.png",
      "note": "Installed plugin visible in plugin inventory."
    }
  ],
  "artifacts": [
    {
      "kind": "manifest",
      "role": "plugin-manifest",
      "path": "fixtures/plugins/example/.codex-plugin/plugin.json",
      "sensitive": false
    }
  ],
  "verification_commands": [
    {
      "command": "npm.cmd test -- src/features/extensions/PluginSkillInventoryPanel.test.tsx",
      "cwd": "D:/AstraBridge/apps/astrabridge-desktop",
      "exit_code": 0,
      "summary": "Plugin inventory panel tests passed."
    }
  ],
  "notes": [
    "No external plugin marketplace used.",
    "No secrets persisted in evidence."
  ]
}
```

## Use in later steps

Later agents should not invent a new report shape. Use this document plus the JSON schema as the canonical contract for:

- step 8 plugin acceptance
- step 12 skill acceptance
- step 15 automation acceptance
- step 18 multimodal acceptance
- step 20 web acceptance
- step 21 combined acceptance
- step 22 dogfood ledger registration
