# Architecture

AstraBridge has three layers:

1. Desktop UI: Tauri + React.
2. Sidecar: Python HTTP/JSON API for projects, providers, metadata, tools, checkpoints, and runtime supervision.
3. Runtime: Codex app-server compatible execution with app-owned isolated state.

## Project Model

- Project: workspace boundary.
- Task/Chat: user-visible objective in a project.
- Provider Thread: internal runtime thread for one provider/model handoff.
- Fork: branch exploration within a task.
- Save/Load: heavier file-state checkpoint.
