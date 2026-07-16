# AstraBridge Sidecar

Local Python runtime for the AstraBridge desktop app. It owns project files,
profile metadata, permissions, archives, and the guarded Codex adapter.

Run in development:

```powershell
python .\apps\astrabridge-sidecar\sidecar_server.py --serve --seed-root .
```

The sidecar uses the Python standard library for its core services. `Pillow` is
also required for generated-asset promotion when a source image must be
cropped or resized. Codex execution is optional at import time; when the Codex
Python SDK is unavailable, runtime endpoints report `codex_unavailable` instead
of silently pretending to run work.
