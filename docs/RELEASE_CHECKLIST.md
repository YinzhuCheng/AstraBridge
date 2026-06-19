# Release Checklist

## Build

- Sidecar unit tests pass.
- Desktop TypeScript/Vite build passes.
- PyInstaller builds `astrabridge-sidecar.exe`.
- Tauri NSIS bundle includes the sidecar resource.

## Functional Smoke

- Create project -> `.abproj` and `.astrabridge/` only.
- Configure provider with API key reference.
- Start a task, send a turn, switch provider, preserve visible task continuity.
- Save/load checkpoint without Git dependency.

## Isolation

- Official Codex config timestamp unchanged.
- No project `.codex*` is created.
- No secrets in repo/project state/reports/logs.
- OpenAI official account login is unavailable.
