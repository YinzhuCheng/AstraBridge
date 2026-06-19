# AstraBridge 鏄熸ˉ

AstraBridge 鏄熸ˉ is a local desktop coding-agent workbench built on Codex CLI/app-server runtime patterns, with first-class support for multiple OpenAI-compatible and third-party providers.

It is not the official Codex App. AstraBridge treats OpenAI, DeepSeek, Kimi, Qwen, Yunwu, and other compatible providers as configurable API-key providers with model metadata, adapter policy, health checks, and local project state.

## Developer Quickstart

```powershell
cd D:\AstraBridge\apps\astrabridge-sidecar
python -m unittest discover -s tests

cd D:\AstraBridge\apps\astrabridge-desktop
npm install
npm run build
npm run tauri dev
```

New projects use `.abproj` and workspace-local `.astrabridge/` state. Legacy `.lcrproj/.lcr` projects should be imported explicitly and migrated once.
