from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from astrabridge_sidecar import astrabridge_web_mcp_server as _canonical
else:
    from . import astrabridge_web_mcp_server as _canonical

# Legacy compatibility shim only. The implementation lives in
# astrabridge_web_mcp_server so old imports cannot become the source of truth.
sys.modules[__name__] = _canonical

if __name__ == "__main__":
    _canonical.main()
