from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from astrabridge_sidecar.lcr_web_mcp_server import *  # noqa: F403
    from astrabridge_sidecar.lcr_web_mcp_server import (
        _clean_bing_url,
        _fetch,
        _research_brief,
        _sanitize_tool_context,
        _search,
        _search_batch,
        _tools,
        main,
    )
else:
    from .lcr_web_mcp_server import *  # noqa: F403
    from .lcr_web_mcp_server import (
        _clean_bing_url,
        _fetch,
        _research_brief,
        _sanitize_tool_context,
        _search,
        _search_batch,
        _tools,
        main,
    )


if __name__ == "__main__":
    main()
