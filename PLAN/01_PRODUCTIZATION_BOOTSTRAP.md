# Productization Bootstrap Plan

1. Install dependencies in `apps/astrabridge-desktop` and `apps/astrabridge-sidecar`.
2. Run sidecar tests and repair import/name fallout from the product split.
3. Run desktop TypeScript/Vite build and repair UI copy fallout.
4. Verify `.abproj/.astrabridge` creation and explicit rejection of legacy project/state formats.
5. Verify OpenAI API-key provider works and `openai_account` mode is absent.
6. Build PyInstaller sidecar and Tauri NSIS installer.
7. Run clean-user install/uninstall and official Codex non-interference checks.
8. Only then resume dogfood projects under AstraBridge-branded project state.
