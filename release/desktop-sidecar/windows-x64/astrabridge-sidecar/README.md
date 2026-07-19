This directory is the formal Desktop-sidecar bundle contract root.

The canonical staged release flow populates it with:

- `python-runtime/python.exe`
- bundled Python stdlib and dependencies
- `astrabridge_sidecar/`
- `skills/`
- `bundle-manifest.json`

Desktop formal packages must launch only this bundled runtime and must not
fall back to repository source, `sidecar_server.py`, or system Python.
