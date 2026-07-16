# Plugin Skill Surface Gap Report

Last updated: 2026-06-25

**Document status:** Completed historical snapshot. Do not resume this report as an implementation queue. Use the maintained extension guidance in [HANDOFF.md](/D:/AstraBridge/docs/HANDOFF.md) and the current registry-selected execution plan.

## Purpose

This report turns the current AstraBridge plugin and skill situation into an execution-ready gap inventory for the remaining plan steps.

The target is not "support every official surface immediately". The target is to make the missing pieces explicit enough that a future agent can implement them one step at a time without reopening product-boundary questions every round.

## Scope

This report compares:

- official or generated Codex plugin and skill surface hints already present in the repo
- current AstraBridge runtime probe, sidecar, MCP, capability, and automation surfaces
- the user workflows AstraBridge still needs in order to expose plugin and skill management as a first-class product capability

Inspected sources for this step included:

- `apps/astrabridge-sidecar/astrabridge_sidecar/codex_plugin_probe.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/codex_skill_probe.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_config_service.py`
- `apps/astrabridge-sidecar/astrabridge_sidecar/automations/specs.py`
- `apps/astrabridge-desktop/src/App.tsx`
- `apps/astrabridge-desktop/src/types.ts`
- `apps/astrabridge-desktop/src/api.ts`
- `apps/astrabridge-desktop/src/features/runtime/RuntimeKernelStatusPanel.tsx`
- `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.tsx`
- `apps/astrabridge-desktop/src/features/automations/AutomationsPanel.tsx`
- `apps/astrabridge-desktop/src/protocol/generated/v2/PluginSummary.ts`
- `apps/astrabridge-desktop/src/protocol/generated/v2/PluginDetail.ts`
- `apps/astrabridge-desktop/src/protocol/generated/v2/PluginInstallParams.ts`
- `apps/astrabridge-desktop/src/protocol/generated/v2/SkillsListEntry.ts`
- `apps/astrabridge-desktop/src/protocol/generated/v2/SkillsChangedNotification.ts`
- `apps/astrabridge-desktop/src/protocol/generated/v2/AppSummary.ts`
- `apps/astrabridge-desktop/src/protocol/generated/v2/HookMetadata.ts`

## Current State Summary

### What already exists

- AstraBridge already has read-only plugin probing and skill probing in the sidecar.
- The kernel probe snapshot already exposes `observed.plugin_features`, `observed.skill_features`, discovered plugin records, discovered skill records, and inferred readiness fields.
- The Runtime tab already shows plugin and skill readiness at a summary level.
- The desktop type surface already contains `CodexKernelPluginRecord`, `CodexKernelSkillRecord`, and probe readiness enums.
- Generated protocol types already indicate an upstream plugin and skill model richer than the current AstraBridge UI:
  - plugin summary/detail
  - install/uninstall/read params
  - plugin apps and hooks
  - skill list entries and change notifications
- MCP preset management already exists as a first-class AstraBridge product surface.
- Capability routing already knows how to surface app-owned MCP preset health.
- Automations already support `runtime.mcp_preset_ids`.

### What does not exist yet

- No canonical AstraBridge registry contract for plugins and skills.
- No first-class plugin inventory API or skill inventory API outside the kernel probe snapshot.
- No plugin/skill management UI for inventory, detail, install planning, update planning, enablement, or preset binding.
- No project-level plugin/skill preset storage.
- No automation plugin/skill preset fields.
- No capability dependency view for plugin-backed or skill-backed behavior.
- No icon provenance pipeline.
- No install/update execution flow.
- No trust review surface for plugin hooks, app integrations, MCP side effects, or remote assets.

### Important current constraint

Plugin features are still rendered as disabled in AstraBridge-managed runtime config:

- `plugins = false`
- `plugin_sharing = false`
- `remote_plugin = false`

That means current kernel probe support is mainly an observation surface, not a user-operable product lane. This is the most important backend reality for the next steps.

## Target User Workflows

The missing product work should be judged against these workflows:

1. Inspect kernel readiness for plugin and skill integration.
2. Browse all discoverable plugins and skills, with clear source and compatibility state.
3. Open a plugin detail view and understand:
   - version
   - source
   - install status
   - hooks
   - MCP side effects
   - apps exposed by the plugin
   - skills provided by the plugin
4. Open a skill detail view and understand:
   - owner plugin or local root
   - enablement state
   - trigger hints
   - project or automation exposure
5. Preview an install or update before mutation, including rollback scope and trust warnings.
6. Enable or disable skills without deleting files.
7. Attach approved plugin/skill presets to a project without writing official Codex project state.
8. Attach approved plugin/skill presets to an automation without breaking existing MCP preset behavior.
9. See when a capability route benefits from or depends on a plugin or skill, while keeping standalone web and app-owned capability routing separate.
10. Understand icon provenance and whether an icon is official, local, or AstraBridge-generated.

If a later implementation does not improve one of these workflows, it is probably solving the wrong problem.

## Metadata Requirements Inventory

### Plugin metadata needed

Current probe records only carry a small subset:

- `plugin_id`
- `display_name`
- `version`
- `source_kind`
- `availability`

The generated upstream type surface implies AstraBridge will also need to represent:

- install policy
- auth policy
- enabled state
- remote plugin id when applicable
- plugin apps
- plugin hooks
- MCP servers affected by the plugin
- description
- keywords
- source marketplace name/path
- share context

Additional AstraBridge-specific fields will be needed for management:

- registry source classification: official, curated, local, project-local, manual
- trust status
- compatibility warnings
- install root
- rollback snapshot id
- checksum or hash when available
- icon provenance
- last validated timestamp

### Skill metadata needed

Current probe records only carry:

- `skill_name`
- `display_name`
- `source_kind`
- `owner_plugin_id`
- `enablement`

The management surface will also need:

- description
- trigger hints or invocation hints
- local path or root identity
- content hash or version hint when safe
- duplicate-name status
- manifest status
- owning plugin version if any
- effective enablement source: global, inherited, project override
- compatibility warnings
- last validated timestamp

### MCP side-effect metadata needed

Plugin and skill management cannot be modeled as pure catalog data. Some plugins may add hooks, MCP servers, apps, auth requirements, or tool-side effects. AstraBridge will need normalized fields for:

- declared MCP servers added or required
- whether those servers are app-owned, plugin-owned, or external
- approval defaults and dangerous side effects
- whether installation changes rendered runtime config
- whether capability runtime or automation runtime must be refreshed after changes

## Current Surface Versus Needed Surface

### Runtime probe surface

Current value:

- good for compatibility inspection
- good for feature support detection
- good for unsupported-kernel messaging

Current limitation:

- summary-only
- not a registry
- not structured for install planning or enablement state
- not exposed as a user workflow beyond Runtime diagnostics

### MCP surface

Current value:

- already productized
- install/apply/reload flow exists for app-owned MCP presets
- capability and automation UI already understand MCP preset linkage

Current limitation:

- MCP preset management is not plugin management
- plugin/skill install state is not represented here
- mixing plugin/skill operations into this tab would blur the trust model

Conclusion:

- keep MCP as its own product lane
- show plugin-caused MCP effects from plugin detail views, but do not collapse plugin management into raw MCP server editing

### Capability surface

Current value:

- already shows route health, candidates, smoke, and app-owned MCP preset visibility

Current limitation:

- no plugin-backed dependency or recommendation model
- no skill-backed readiness indicators
- no handoff into plugin/skill detail

### Automation surface

Current value:

- already stores `runtime.mcp_preset_ids`
- already has a dense authoring UI and runtime permission model

Current limitation:

- no plugin preset selector
- no skill preset selector
- no trust summary for plugin-derived execution changes
- no validation for plugin or skill availability at run time

## Backend Gaps

1. No canonical plugin and skill registry contract.
   - Current probes are enough for diagnostics, not enough for management.
   - This is the direct entry point for step 15.

2. No read-only inventory API separate from kernel probe.
   - The desktop should not mine management data out of the probe snapshot forever.
   - This is the direct entry point for step 16.

3. No source normalization model.
   - Official marketplace, local marketplace, installed root, shared remote, project root, and manual additions are not unified yet.

4. No install/update plan generator.
   - There is no backend object that says what files, hooks, apps, skills, or MCP surfaces would change before mutation.

5. No controlled execution lane for plugin install/update.
   - There is no rollback snapshot contract or mutation audit record yet.

6. No skill enablement state model beyond probe output.
   - Global enable/disable and project overrides do not exist.

7. No project preset state for plugins and skills.
   - Current project/runtime state has no equivalent of `mcp_preset_ids` for these surfaces.

8. No automation binding contract for plugin or skill presets.
   - The automation runtime spec only carries `mcp_preset_ids`.

9. No capability dependency graph or annotation layer.
   - Capability routing does not know how to say "this capability benefits from plugin X" without changing routing semantics.

10. No icon ingestion or provenance service.
   - This will matter before the UI can safely render a rich extension inventory.

## Frontend Gaps

1. No first-class Plugins or Skills management surface.
   - Runtime only shows summary status.
   - MCP only shows server config, not extension catalog state.

2. No inventory browsing experience.
   - No search, filters, sort, source badges, status badges, compatibility badges, or detail pane.

3. No detail model.
   - There is nowhere to show plugin apps, hooks, skills, auth requirements, MCP effects, or rollback notes.

4. No install/update planning UI.
   - Users cannot preview changes before mutation.

5. No enablement controls.
   - Skills cannot be enabled or disabled through AstraBridge UI.

6. No project binding UI.
   - There is nowhere to bind plugin or skill presets to a project.

7. No automation binding UI.
   - Automations only understand MCP preset chips today.

8. No capability dependency messaging.
   - Capability operators cannot see when plugin or skill state is relevant.

9. No icon fallback behavior.
   - The product currently has no opinionated rendering path for plugin icons with provenance labeling.

## Security And Trust Gaps

1. Plugin execution is not yet exposed through AstraBridge's runtime trust model.
   - Hooks, apps, MCP additions, and local command execution need explicit trust boundaries.

2. Remote marketplace behavior is disabled at config level, but there is no product policy yet for when or how it becomes enabled.

3. There is no normalized trust warning surface for:
   - untrusted local manifests
   - remote catalogs
   - plugin-provided hooks
   - plugin-provided MCP servers
   - icon URLs or image payloads
   - skill prompt injection risk

4. There is no install-time secret scan or write audit path for plugin operations.

5. There is no rollback snapshot policy for plugin mutation.

6. There is no policy yet for durable storage of remote metadata, icon assets, or plugin app descriptions.

7. There is no user-facing distinction between:
   - app-owned built-in capability runtime
   - external MCP servers
   - plugin-owned assets or hooks
   - local user-authored skills

This distinction must stay visible or the product will become hard to reason about.

## Icon And Provenance Policy

The future icon pipeline should follow these rules:

1. Preferred sources, in order:
   - official packaged icon with clear license or product provenance
   - local plugin-bundled icon from a validated local path
   - AstraBridge-rendered fallback icon generated from plugin initials, category, or brand-safe replacement treatment

2. Do not fetch and persist arbitrary remote icon URLs by default.

3. Every rendered icon record should carry:
   - provenance kind: official, bundled_local, generated_fallback
   - source path or source URL when retained
   - validation status
   - hash when retained locally
   - replacement_reason when generated

4. Replacement icons must not imply official endorsement.

5. If licensing is unclear, prefer a generated fallback icon and show a provenance badge.

## Proposed Navigation Shape

The current tab set already has `mcp`, `runtime`, `capabilities`, and `automations`. The cleanest product shape is:

1. Keep `Runtime` as the kernel compatibility and runtime health surface.
   - Purpose: "Is the kernel/plugin/skill lane supported and healthy?"

2. Keep `MCP` as the raw server and preset management surface.
   - Purpose: "What tool servers are configured and visible?"

3. Add a first-class `Extensions` management area.
   - Internal views:
     - Overview
     - Plugins
     - Skills
     - Presets
   - Purpose: "What extension content exists, what does it do, and how is it enabled?"

4. Keep `Capabilities` focused on route selection and app-owned runtime status.
   - Add dependency badges and links into `Extensions`, but do not merge the panels.

5. Keep `Automations` focused on scheduled execution.
   - Add plugin/skill preset selectors beside the existing MCP preset selector rather than moving automation authoring into `Extensions`.

This navigation keeps operational boundaries clear:

- Runtime = support state
- MCP = tool server state
- Extensions = plugin/skill catalog and enablement
- Capabilities = model and runtime routing
- Automations = scheduled execution

## Recommended Step Mapping

This report suggests the remaining implementation sequence is still correct:

- step 15: define registry contracts
- step 16: expose read-only inventory API
- step 17: build inventory UI
- step 18: add icon provenance pipeline
- step 19: add install/update planning
- step 20: add controlled execution
- step 21: add skill enable/disable
- step 22: add project presets
- step 23: add automation preset binding
- step 24: add capability dependency visibility

The main dependency insight from this report is:

- step 18 should happen before rich inventory polish or install/update UX depends on icons
- step 19 must happen before step 20
- steps 22 through 24 should consume the registry contract rather than re-querying probe payloads ad hoc

## Acceptance Signal For This Step

Step 14 should be considered complete if a future agent can start step 15 without reopening product-scope questions about:

- whether plugin/skill management is separate from MCP management
- whether plugin/skill state belongs in Runtime versus Extensions
- whether automation linkage should reuse or replace `mcp_preset_ids`
- whether icon provenance is a real requirement
- whether project-level state should remain in `.abproj` or `.astrabridge/`

This report resolves those questions in favor of:

- separate but linked product lanes
- explicit registry contracts
- explicit trust metadata
- explicit project and automation bindings
- explicit icon provenance
