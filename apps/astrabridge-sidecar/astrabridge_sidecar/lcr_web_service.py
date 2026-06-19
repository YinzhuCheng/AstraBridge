from __future__ import annotations

from typing import Any

from .common import new_id, now_iso, write_json
from .lcr_web_mcp_server import _fetch, _research_brief, _sanitize_tool_context, _search_batch


class LcrWebService:
    """App-owned public web research entrypoint.

    The same implementation is exposed through MCP. This service gives the
    desktop/sidecar a deterministic fallback when an app-server provider thread
    can list MCP servers but does not mount their tools as model-callable tools.
    """

    def __init__(self, project_service) -> None:
        self._projects = project_service

    def search_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = _search_batch(
            payload.get("queries"),
            dedupe=bool(payload.get("dedupe", True)),
            timeout_sec=int(payload.get("timeout_sec") or 20),
        )
        return self._persist("search-batch", result, tool_context=payload.get("tool_context"))

    def research_brief(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = _research_brief(
            research_goal=str(payload.get("research_goal") or "").strip(),
            queries=payload.get("queries"),
            source_urls=payload.get("source_urls"),
            search_top_k=int(payload.get("search_top_k") or 5),
            fetch_top_n=int(payload.get("fetch_top_n") or 6),
            max_chars_per_source=int(payload.get("max_chars_per_source") or 3000),
            timeout_sec=int(payload.get("timeout_sec") or 20),
        )
        return self._persist("research-brief", result, tool_context=payload.get("tool_context"))

    def fetch(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = _fetch(
            str(payload.get("url") or "").strip(),
            max_chars=int(payload.get("max_chars") or 6000),
            timeout_sec=int(payload.get("timeout_sec") or 20),
        )
        return self._persist("fetch", result, tool_context=payload.get("tool_context"))

    def _persist(self, prefix: str, result: dict[str, Any], *, tool_context: Any | None = None) -> dict[str, Any]:
        record_id = new_id(prefix)
        sanitized_context = _sanitize_tool_context(tool_context)
        record = {
            "schema_version": "lcr-web-research-record-v1",
            "record_id": record_id,
            "created_at": now_iso(),
            "tool_event_verified": True,
            "tool_context": sanitized_context,
            "result": result,
        }
        path = self._projects.require_shell_state_root() / "research" / f"{record_id}.json"
        write_json(path, record)
        return {
            "ok": True,
            "record_id": record_id,
            "tool_event_verified": True,
            "tool_context": sanitized_context,
            "path": str(path),
            "result": result,
        }

