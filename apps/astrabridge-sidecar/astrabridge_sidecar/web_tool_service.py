from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .astrabridge_web_mcp_server import _fetch, _research_brief, _sanitize_tool_context, _search_batch
from .common import new_id, now_iso, write_json
from .multimodal_result_envelope import enrich_web_result
from .usage_signal import usage_not_available


@dataclass(frozen=True)
class WebLaneToolDescriptor:
    tool_name: str
    operation: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "tool_name": self.tool_name,
            "operation": self.operation,
            "description": self.description,
        }


def web_lane_descriptor() -> dict[str, Any]:
    tools = [
        WebLaneToolDescriptor(
            tool_name="astrabridge_web_search_batch",
            operation="search_batch",
            description="Run one or more public web searches and return structured results.",
        ),
        WebLaneToolDescriptor(
            tool_name="astrabridge_web_research_brief",
            operation="research_brief",
            description="Search, fetch, and assemble a structured research brief with source packs.",
        ),
        WebLaneToolDescriptor(
            tool_name="astrabridge_web_search",
            operation="search",
            description="Run a single-query public web search.",
        ),
        WebLaneToolDescriptor(
            tool_name="astrabridge_web_fetch",
            operation="fetch",
            description="Fetch one public HTTP(S) page into a structured result envelope.",
        ),
    ]
    return {
        "lane_id": "astrabridge.web",
        "lane_type": "web_standalone",
        "capability_id": "web.search",
        "model_routing_enabled": False,
        "llm_interprets_results": True,
        "notes": [
            "Web lane tools are not selected through provider/model routing.",
            "Search and fetch results are produced by the tool service; the caller LLM decides how to interpret them.",
            "research_brief may aggregate fetches, but it remains part of the standalone web lane rather than a model-backed capability.",
        ],
        "tools": [tool.to_dict() for tool in tools],
    }


class AstraBridgeWebService:
    """App-owned public web research entrypoint.

    The same implementation is exposed through MCP. This service gives the
    desktop/sidecar a deterministic fallback when an app-server provider thread
    can list MCP servers but does not mount their tools as model-callable tools.
    """

    def __init__(self, project_service) -> None:
        self._projects = project_service
        self._mcp_broker = None

    def set_mcp_broker(self, broker: Any | None) -> None:
        self._mcp_broker = broker

    def lane_descriptor(self) -> dict[str, Any]:
        return web_lane_descriptor()

    def search_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        broker_result = self._invoke_via_broker("astrabridge_web_search_batch", payload, operation_prefix="search-batch")
        return self._persist("search-batch", broker_result["result"], tool_context=payload.get("tool_context"), mcp=broker_result["mcp"])

    def research_brief(self, payload: dict[str, Any]) -> dict[str, Any]:
        broker_result = self._invoke_via_broker("astrabridge_web_research_brief", payload, operation_prefix="research-brief")
        return self._persist("research-brief", broker_result["result"], tool_context=payload.get("tool_context"), mcp=broker_result["mcp"])

    def fetch(self, payload: dict[str, Any]) -> dict[str, Any]:
        broker_result = self._invoke_via_broker("astrabridge_web_fetch", payload, operation_prefix="fetch")
        return self._persist("fetch", broker_result["result"], tool_context=payload.get("tool_context"), mcp=broker_result["mcp"])

    def _invoke_via_broker(self, tool_name: str, payload: dict[str, Any], *, operation_prefix: str) -> dict[str, Any]:
        if self._mcp_broker is None:
            if tool_name == "astrabridge_web_search_batch":
                return {
                    "result": _search_batch(
                        payload.get("queries"),
                        dedupe=bool(payload.get("dedupe", True)),
                        timeout_sec=int(payload.get("timeout_sec") or 20),
                    ),
                    "mcp": {},
                }
            if tool_name == "astrabridge_web_research_brief":
                return {
                    "result": _research_brief(
                        research_goal=str(payload.get("research_goal") or "").strip(),
                        queries=payload.get("queries"),
                        source_urls=payload.get("source_urls"),
                        search_top_k=int(payload.get("search_top_k") or 5),
                        fetch_top_n=int(payload.get("fetch_top_n") or 6),
                        max_chars_per_source=int(payload.get("max_chars_per_source") or 3000),
                        timeout_sec=int(payload.get("timeout_sec") or 20),
                    ),
                    "mcp": {},
                }
            return {
                "result": _fetch(
                    str(payload.get("url") or "").strip(),
                    max_chars=int(payload.get("max_chars") or 6000),
                    timeout_sec=int(payload.get("timeout_sec") or 20),
                ),
                "mcp": {},
            }
        return self._mcp_broker.invoke_tool(
            "astrabridge_web",
            tool_name,
            payload,
            caller="web_lane",
            operation_id=new_id(f"web-{operation_prefix}"),
        )

    def _persist(self, prefix: str, result: dict[str, Any], *, tool_context: Any | None = None, mcp: dict[str, Any] | None = None) -> dict[str, Any]:
        record_id = new_id(prefix)
        sanitized_context = _sanitize_tool_context(tool_context)
        usage_signal = usage_not_available(
            source="web_lane",
            reason="standalone_web_lane_no_provider_tokens",
            request_kind=prefix,
        )
        path = self._projects.require_shell_state_root() / "research" / f"{record_id}.json"
        record = {
            "schema_version": "astrabridge-web-research-record-v1",
            "record_id": record_id,
            "created_at": now_iso(),
            "tool_event_verified": True,
            "tool_context": sanitized_context,
            "mcp": dict(mcp or {}),
            "usage_signal": usage_signal,
            "result": dict(result),
        }
        write_json(path, record)
        enriched_result = enrich_web_result(
            str(result.get("tool") or "").strip() or f"astrabridge_web_{prefix.replace('-', '_')}",
            dict(result),
            workspace_root=self._projects.require_workspace_root(),
            record_path=path,
            request_id=record_id,
        )
        record["result"] = enriched_result
        write_json(path, record)
        return {
            "ok": True,
            "record_id": record_id,
            "tool_event_verified": True,
            "tool_context": sanitized_context,
            "mcp": dict(mcp or {}),
            "path": str(path),
            "usage_signal": usage_signal,
            "result": enriched_result,
        }


# Internal compatibility alias while older private imports are cleaned up.
LcrWebService = AstraBridgeWebService
