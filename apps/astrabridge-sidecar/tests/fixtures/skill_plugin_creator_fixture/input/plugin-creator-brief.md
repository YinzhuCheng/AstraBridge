# Plugin Creator Skills Dogfood Brief

Use the discovered `plugin-creator` skill to scaffold one local-only demo plugin for AstraBridge's skills dogfood flow.

## Fixed task inputs

- Plugin name: `astrabridge-skills-dogfood-sample`
- Parent plugin directory: `D:/AstraBridge/PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins`
- Marketplace path: `D:/AstraBridge/PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/.agents/plugins/marketplace.json`
- Required scaffold extras: `skills`, `scripts`, `assets`, `.mcp.json`, `.app.json`, and a marketplace entry

## Safety boundaries

- Only write inside `D:/AstraBridge/PRIVATE/demo-runs/skills-plugin-creator-scenario/`.
- Do not write `~/.codex`, project `.codex*`, product source directories, or any external marketplace location.
- Do not use network access, API keys, cookies, or remote installs.

## Required validation

- Run `${CODEX_HOME:-~/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py` against the generated plugin root.
- Preserve the generated plugin directory and marketplace file for later preview and evidence capture.

## Expected artifact roots

- Plugin root: `D:/AstraBridge/PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample`
- Manifest: `D:/AstraBridge/PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/.codex-plugin/plugin.json`
- Marketplace: `D:/AstraBridge/PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/.agents/plugins/marketplace.json`

## Minimum success criteria

- The generated plugin name remains `astrabridge-skills-dogfood-sample`.
- The scaffold includes `skills/`, `scripts/`, `assets/`, `.mcp.json`, and `.app.json`.
- `plugin.json` contains no `[TODO:` placeholders.
- The validation command exits with code `0`.
