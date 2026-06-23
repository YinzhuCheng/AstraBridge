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

Projects use `.abproj` and workspace-local `.astrabridge/` state. Legacy LCR and codex-shell project files are not imported; recreate AstraBridge projects from your backups when needed.
## Private Credentials

AstraBridge supports provider keys as private operator-owned material. The repo includes `PRIVATE/README.md` to document local-only paths, while `PRIVATE/**` is ignored by git. Do not push real API keys or `Authorization` headers to a public remote.

## Current Operator Baseline

Use these docs as the current product path:

- [Demo Runbook](/D:/AstraBridge/docs/DEMO_RUNBOOK.md)
- [Security And Isolation](/D:/AstraBridge/docs/SECURITY_AND_ISOLATION.md)
- [Release Checklist](/D:/AstraBridge/docs/RELEASE_CHECKLIST.md)
- [Planning Baseline](/D:/AstraBridge/PLAN/30_NEAR_TERM_PRODUCT_FOCUS_AND_NON_TRIVIAL_PRIORITIES.md)
