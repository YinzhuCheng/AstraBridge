from __future__ import annotations

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
