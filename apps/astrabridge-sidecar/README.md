# Research OS Sidecar

Local Python runtime for the Research OS desktop app. It owns project files,
profile metadata, permissions, archives, and the guarded Codex adapter.

Run in development:

```powershell
python .\apps\research-os-sidecar\sidecar_server.py --serve --seed-root .
```

The sidecar uses only the Python standard library for its core services. Codex
execution is optional at import time; when the Codex Python SDK is unavailable,
runtime endpoints report `codex_unavailable` instead of silently pretending to
run work.

