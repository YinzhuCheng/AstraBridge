from __future__ import annotations

import html
import ipaddress
import json
import base64
import os
import re
import socket
import sys
import traceback
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, BinaryIO


SERVER_NAME = "lcr-web-tools"
SERVER_VERSION = "0.1.0"
DEFAULT_TIMEOUT_SEC = 20
DEFAULT_MAX_CHARS = 6000
DEFAULT_BATCH_MAX_QUERIES = 8
DEFAULT_RESEARCH_FETCH_TOP_N = 6
_OUTPUT_FRAMING = "header"
PREFERRED_GAME_DEV_DOMAINS = {
    "gamedev.stackexchange.com",
    "developer.mozilla.org",
    "docs.godotengine.org",
    "docs.unity3d.com",
    "www.mapeditor.org",
    "doc.mapeditor.org",
    "www.rpgmakerweb.com",
    "forum.godotengine.org",
}
LOW_SIGNAL_DOMAINS = {
    "merriam-webster.com",
    "www.merriam-webster.com",
    "britannica.com",
    "www.britannica.com",
    "dictionary.cambridge.org",
    "magic.wizards.com",
    "magic.gg",
    "mtg.wiki",
}
GAME_DEV_HINT_TOKENS = {
    "game",
    "games",
    "rpg",
    "jrpg",
    "tile",
    "tilemap",
    "tileset",
    "autotile",
    "sprite",
    "sprites",
    "animation",
    "gamedev",
    "level",
    "puzzle",
    "dungeon",
    "design",
}
MAGIC_TOWER_ALIASES = (
    "magic tower",
    "tower of the sorcerer",
    "魔塔",
)


def main() -> None:
    _debug("started", argv=sys.argv[:3])
    while True:
        message = _read_message(sys.stdin.buffer)
        if message is None:
            _debug("eof")
            break
        response = _handle_message(message)
        if response is not None:
            _write_message(sys.stdout.buffer, response)


def _handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = str(message.get("method") or "")
    params = message.get("params") or {}
    try:
        if method == "initialize":
            return _result(
                request_id,
                {
                    "protocolVersion": str(params.get("protocolVersion") or "2024-11-05"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": (
                        "Use AstraBridge web tools for batch source lookup and lightweight research briefs. "
                        "Return URLs with claims. Do not pass secrets, Authorization headers, cookies, or API keys."
                    ),
                },
            )
        if method in {"notifications/initialized", "initialized"}:
            return None
        if method == "tools/list":
            return _result(request_id, {"tools": _tools()})
        if method == "resources/list":
            return _result(request_id, {"resources": []})
        if method == "resources/templates/list":
            return _result(request_id, {"resourceTemplates": []})
        if method == "tools/call":
            return _result(request_id, _call_tool(params))
        if request_id is None:
            return None
        return _error(request_id, -32601, f"Unsupported method: {method}")
    except Exception as exc:  # noqa: BLE001
        details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        _debug("handler_error", method=method, error=details[:500])
        return _error(request_id, -32000, details)


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "lcr_web_search_batch",
            "description": (
                "Run one or more public web searches and return a deduplicated result set. A single basic "
                "search is represented as queries=[{query: ...}]. Use this before claiming current facts, "
                "design references, tool installation guidance, or source-backed recommendations."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": DEFAULT_BATCH_MAX_QUERIES,
                        "items": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query."},
                                "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                                "domains": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "maxItems": 6,
                                    "description": "Optional preferred domains. Each becomes a site: query variant and ranking boost.",
                                },
                                "exclude_domains": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "maxItems": 6,
                                    "description": "Optional domains to down-rank or avoid.",
                                },
                            },
                            "required": ["query"],
                            "additionalProperties": False,
                        },
                    },
                    "dedupe": {"type": "boolean", "default": True, "description": "Merge duplicate URLs across queries."},
                    "timeout_sec": {"type": "integer", "minimum": 5, "maximum": 60, "default": DEFAULT_TIMEOUT_SEC},
                    "tool_context": _tool_context_schema(),
                },
                "required": ["queries"],
                "additionalProperties": False,
            },
        },
        {
            "name": "lcr_web_research_brief",
            "description": (
                "Build a lightweight research brief from a goal: run multiple searches, fetch top public pages, "
                "redact/truncate page text, and return sources, excerpts, unresolved questions, and suggested "
                "follow-up queries. Use for multi-step web research instead of manual one-by-one searching."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "research_goal": {"type": "string", "description": "What to investigate and why."},
                    "queries": {
                        "type": "array",
                        "maxItems": DEFAULT_BATCH_MAX_QUERIES,
                        "items": {"type": "string"},
                        "description": "Optional explicit search queries. If omitted, the tool derives a small query plan from research_goal.",
                    },
                    "source_urls": {
                        "type": "array",
                        "maxItems": 10,
                        "items": {"type": "string"},
                        "description": "Optional known public URLs to fetch alongside search results.",
                    },
                    "search_top_k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                    "fetch_top_n": {"type": "integer", "minimum": 1, "maximum": 12, "default": DEFAULT_RESEARCH_FETCH_TOP_N},
                    "max_chars_per_source": {"type": "integer", "minimum": 500, "maximum": 10000, "default": 3000},
                    "timeout_sec": {"type": "integer", "minimum": 5, "maximum": 60, "default": DEFAULT_TIMEOUT_SEC},
                    "tool_context": _tool_context_schema(),
                },
                "required": ["research_goal"],
                "additionalProperties": False,
            },
        },
        {
            "name": "lcr_web_search",
            "description": "Compatibility alias for lcr_web_search_batch with one query. Prefer lcr_web_search_batch.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                    "timeout_sec": {"type": "integer", "minimum": 5, "maximum": 60, "default": DEFAULT_TIMEOUT_SEC},
                    "tool_context": _tool_context_schema(),
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "lcr_web_fetch",
            "description": "Compatibility low-level public HTTP(S) fetch. Prefer lcr_web_research_brief for agent research.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Public HTTP(S) URL to fetch."},
                    "max_chars": {"type": "integer", "minimum": 500, "maximum": 20000, "default": DEFAULT_MAX_CHARS},
                    "timeout_sec": {"type": "integer", "minimum": 5, "maximum": 60, "default": DEFAULT_TIMEOUT_SEC},
                    "tool_context": _tool_context_schema(),
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    ]


def _call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name") or "")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object.")
    if name == "lcr_web_search_batch":
        payload = _search_batch(
            args.get("queries"),
            dedupe=bool(args.get("dedupe", True)),
            timeout_sec=int(args.get("timeout_sec") or DEFAULT_TIMEOUT_SEC),
        )
        context = _sanitize_tool_context(args.get("tool_context"))
        if context:
            payload["tool_context"] = context
        return _tool_text(payload)
    if name == "lcr_web_research_brief":
        payload = _research_brief(
            research_goal=str(args.get("research_goal") or "").strip(),
            queries=args.get("queries"),
            source_urls=args.get("source_urls"),
            search_top_k=int(args.get("search_top_k") or 5),
            fetch_top_n=int(args.get("fetch_top_n") or DEFAULT_RESEARCH_FETCH_TOP_N),
            max_chars_per_source=int(args.get("max_chars_per_source") or 3000),
            timeout_sec=int(args.get("timeout_sec") or DEFAULT_TIMEOUT_SEC),
        )
        context = _sanitize_tool_context(args.get("tool_context"))
        if context:
            payload["tool_context"] = context
        return _tool_text(payload)
    if name == "lcr_web_search":
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required.")
        payload = _search_batch(
            [{"query": query, "max_results": int(args.get("max_results") or 5)}],
            dedupe=True,
            timeout_sec=int(args.get("timeout_sec") or DEFAULT_TIMEOUT_SEC),
        )
        payload["tool"] = "lcr_web_search"
        context = _sanitize_tool_context(args.get("tool_context"))
        if context:
            payload["tool_context"] = context
        return _tool_text(payload)
    if name == "lcr_web_fetch":
        url = str(args.get("url") or "").strip()
        if not url:
            raise ValueError("url is required.")
        payload = _fetch(url, max_chars=int(args.get("max_chars") or DEFAULT_MAX_CHARS), timeout_sec=int(args.get("timeout_sec") or DEFAULT_TIMEOUT_SEC))
        context = _sanitize_tool_context(args.get("tool_context"))
        if context:
            payload["tool_context"] = context
        return _tool_text(payload)
    raise ValueError(f"Unknown AstraBridge web tool: {name}")


def _tool_context_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "description": (
            "Optional AstraBridge Tool Context Envelope. Pass only task goal, current plan step, workspace, "
            "project/asset context references, evidence requirements, forbidden inputs, and output contract."
        ),
        "properties": {
            "schema_version": {"type": "string", "maxLength": 80},
            "tool_name": {"type": "string", "maxLength": 120},
            "project_id": {"type": "string", "maxLength": 160},
            "task_id": {"type": "string", "maxLength": 160},
            "task_title": {"type": "string", "maxLength": 220},
            "task_goal": {"type": "string", "maxLength": 800},
            "current_plan_step": {"type": "string", "maxLength": 800},
            "workspace_root": {"type": "string", "maxLength": 400},
            "selected_provider": {"type": "string", "maxLength": 120},
            "selected_model": {"type": "string", "maxLength": 160},
            "selected_effort": {"type": "string", "maxLength": 80},
            "permission_mode": {"type": "string", "maxLength": 80},
            "project_context_ref": {"type": "string", "maxLength": 400},
            "asset_context_ref": {"type": "string", "maxLength": 400},
            "context_refs": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 400}},
            "asset_context_refs": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 400}},
            "checkpoint_refs": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 260}},
            "evidence_requirements": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 240}},
            "forbidden_inputs": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 240}},
            "output_contract": {"type": "string", "maxLength": 800},
        },
        "additionalProperties": False,
    }


def _sanitize_tool_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed_string_fields = {
        "schema_version": 80,
        "tool_name": 120,
        "project_id": 160,
        "task_id": 160,
        "task_title": 220,
        "task_goal": 800,
        "current_plan_step": 800,
        "workspace_root": 400,
        "selected_provider": 120,
        "selected_model": 160,
        "selected_effort": 80,
        "permission_mode": 80,
        "project_context_ref": 400,
        "asset_context_ref": 400,
        "output_contract": 800,
    }
    sanitized: dict[str, Any] = {}
    for key, limit in allowed_string_fields.items():
        text = _safe_context_text(value.get(key), limit)
        if text:
            sanitized[key] = text
    list_fields = {
        "evidence_requirements": (12, 240),
        "forbidden_inputs": (12, 240),
        "context_refs": (8, 400),
        "asset_context_refs": (6, 400),
        "checkpoint_refs": (6, 260),
    }
    for key, (max_items, limit) in list_fields.items():
        raw_items = value.get(key)
        if not isinstance(raw_items, list):
            continue
        items = [_safe_context_text(item, limit) for item in raw_items[:max_items]]
        items = [item for item in items if item]
        if items:
            sanitized[key] = items[:max_items]
    return sanitized


def _safe_context_text(value: Any, limit: int) -> str:
    if not isinstance(value, (str, int, float, bool)):
        return ""
    text = _redact_sensitive_text(str(value))
    if re.search(r"(?i)(authorization|bearer|api[_-]?key|secret|cookie|token|raw[_-]?messages|base64|data:image)", text):
        text = re.sub(r"(?i)(authorization|bearer|api[_-]?key|secret|cookie|token|raw[_-]?messages|base64|data:image)", "[REDACTED]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    return text[:limit]


def _search_batch(queries: Any, *, dedupe: bool, timeout_sec: int) -> dict[str, Any]:
    query_specs = _normalize_query_specs(queries)
    results_by_query = []
    merged: list[dict[str, str]] = []
    warnings: list[str] = []
    for spec in query_specs:
        query = spec["query"]
        raw_results: list[dict[str, str]] = []
        warnings_for_query: list[str] = []
        variants = _expand_query_variants(
            query,
            domains=spec.get("domains") or [],
            exclude_domains=spec.get("exclude_domains") or [],
        )
        for variant in variants:
            result = _search(variant, max_results=spec["max_results"], timeout_sec=timeout_sec)
            results = [dict(item) for item in list(result.get("results") or []) if isinstance(item, dict)]
            for item in results:
                item["query_variant"] = variant
            raw_results.extend(results)
            if result.get("warning"):
                warnings_for_query.append(f"{variant}: {result.get('warning')}")
        results = _rank_results_for_query(
            query,
            raw_results,
            prefer_domains=spec.get("domains") or [],
            exclude_domains=spec.get("exclude_domains") or [],
        )[: spec["max_results"]]
        results_by_query.append(
            {
                "query": query,
                "variant_count": len(variants),
                "result_count": len(results),
                "results": results,
                "warning": "; ".join(warnings_for_query[:6]),
            }
        )
        warnings.extend(warnings_for_query[:6])
        merged.extend({**item, "query": query} for item in results)
    if dedupe:
        merged = _dedupe_results(merged)
        merged = _rank_results_for_query(
            " ".join(spec["query"] for spec in query_specs),
            merged,
            prefer_domains=[domain for spec in query_specs for domain in spec.get("domains") or []],
            exclude_domains=[domain for spec in query_specs for domain in spec.get("exclude_domains") or []],
        )
    return {
        "tool": "lcr_web_search_batch",
        "source": "duckduckgo_html_with_ranked_variants",
        "query_count": len(query_specs),
        "result_count": len(merged),
        "results_by_query": results_by_query,
        "merged_results": merged,
        "warnings": warnings,
        "note": "Basic search is queries=[{query: ...}]. Queries may be expanded with domain hints and ambiguity repairs. Use lcr_web_research_brief when page fetching and a source pack are needed.",
    }


def _research_brief(
    *,
    research_goal: str,
    queries: Any,
    source_urls: Any,
    search_top_k: int,
    fetch_top_n: int,
    max_chars_per_source: int,
    timeout_sec: int,
) -> dict[str, Any]:
    if not research_goal:
        raise ValueError("research_goal is required.")
    explicit_queries = _string_list(queries)
    query_texts = explicit_queries or _derive_research_queries(research_goal)
    query_specs = [{"query": query, "max_results": max(1, min(10, search_top_k))} for query in query_texts[:DEFAULT_BATCH_MAX_QUERIES]]
    search_payload = _search_batch(query_specs, dedupe=True, timeout_sec=timeout_sec)
    candidates: list[dict[str, str]] = []
    for url in _string_list(source_urls)[:10]:
        candidates.append({"title": "", "url": url, "snippet": "User-provided source URL.", "query": "source_urls"})
    for url in _hint_source_urls_for_goal(research_goal):
        candidates.append({"title": "", "url": url, "snippet": "AstraBridge hinted technical source.", "query": "hinted_sources"})
    candidates.extend([dict(item) for item in list(search_payload.get("merged_results") or []) if isinstance(item, dict)])
    candidates = _dedupe_results(candidates)
    fetch_top_n = max(1, min(12, int(fetch_top_n or DEFAULT_RESEARCH_FETCH_TOP_N)))
    max_chars_per_source = max(500, min(10000, int(max_chars_per_source or 3000)))
    sources = []
    failures = []
    for candidate in candidates[:fetch_top_n]:
        url = str(candidate.get("url") or "").strip()
        if not url:
            continue
        source = {
            "title": str(candidate.get("title") or ""),
            "url": url,
            "query": str(candidate.get("query") or ""),
            "snippet": str(candidate.get("snippet") or "")[:500],
            "fetch_ok": False,
            "excerpt": "",
            "truncated": False,
            "content_type": "",
        }
        try:
            fetched = _fetch(url, max_chars=max_chars_per_source, timeout_sec=timeout_sec)
            excerpt = _redact_sensitive_text(str(fetched.get("text") or ""))
            source.update(
                {
                    "url": str(fetched.get("url") or url),
                    "content_type": str(fetched.get("content_type") or ""),
                    "excerpt": excerpt[:max_chars_per_source],
                    "truncated": bool(fetched.get("truncated")),
                    "fetch_ok": True,
                }
            )
        except Exception as exc:  # noqa: BLE001
            source["warning"] = f"{type(exc).__name__}: {exc}"
            failures.append({"url": url, "warning": source["warning"]})
        sources.append(source)
    fetched_sources = [item for item in sources if item.get("fetch_ok")]
    unresolved = []
    if not fetched_sources:
        unresolved.append("No pages were fetched successfully; try explicit source_urls or narrower queries.")
    if len(fetched_sources) < min(3, fetch_top_n):
        unresolved.append("Source coverage is thin; treat claims as provisional and run another brief with targeted queries.")
    return {
        "tool": "lcr_web_research_brief",
        "research_goal": research_goal,
        "query_plan": query_texts[:DEFAULT_BATCH_MAX_QUERIES],
        "search": {
            "query_count": search_payload.get("query_count"),
            "result_count": search_payload.get("result_count"),
            "warnings": search_payload.get("warnings") or [],
        },
        "sources": sources,
        "source_count": len(sources),
        "fetched_source_count": len(fetched_sources),
        "failures": failures[:10],
        "brief": _compose_extract_brief(research_goal, fetched_sources),
        "unresolved_questions": unresolved,
        "suggested_followup_queries": _suggest_followup_queries(research_goal, query_texts, fetched_sources),
        "citation_rule": "Use only URLs in sources for citations. Mark unfetched search snippets as unverified.",
    }


def _hint_source_urls_for_goal(goal: str) -> list[str]:
    lowered = str(goal or "").lower()
    urls: list[str] = []
    if any(token in lowered for token in ("tilemap", "autotile", "tileset", "terrain", "automap", "html5", "canvas")):
        urls.extend(
            [
                "https://developer.mozilla.org/en-US/docs/Games/Techniques/Tilemaps",
                "https://doc.mapeditor.org/en/stable/manual/terrain/",
                "https://doc.mapeditor.org/en/stable/manual/automapping/",
                "https://docs.godotengine.org/en/stable/tutorials/2d/using_tilemaps.html",
            ]
        )
    return list(dict.fromkeys(urls))[:8]


def _search(query: str, *, max_results: int, timeout_sec: int) -> dict[str, Any]:
    max_results = max(1, min(10, int(max_results or 5)))
    search_url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        body, final_url, content_type = _download_text(search_url, timeout_sec=timeout_sec)
        parser = _DuckDuckGoParser()
        parser.feed(body)
        results = parser.results[:max_results]
        if not results:
            bing = _search_bing(query, max_results=max_results, timeout_sec=timeout_sec)
            bing["fallback_from"] = "duckduckgo_html"
            return bing
        return {
            "tool": "lcr_web_search",
            "query": query,
            "source": "duckduckgo_html",
            "url": final_url,
            "content_type": content_type,
            "results": results,
            "result_count": len(results),
            "warning": "" if results else "No parsed results; try a more specific query or fetch a known URL.",
        }
    except Exception as exc:  # noqa: BLE001
        try:
            bing = _search_bing(query, max_results=max_results, timeout_sec=timeout_sec)
            bing["fallback_from"] = f"duckduckgo_html_error:{type(exc).__name__}"
            warning = str(bing.get("warning") or "").strip()
            bing["warning"] = "; ".join(
                part for part in [f"DuckDuckGo failed: {type(exc).__name__}: {exc}", warning] if part
            )
            return bing
        except Exception:
            return {
                "tool": "lcr_web_search",
                "query": query,
                "source": "duckduckgo_html",
                "results": [],
                "result_count": 0,
                "warning": f"Search failed: {type(exc).__name__}: {exc}",
            }


def _search_bing(query: str, *, max_results: int, timeout_sec: int) -> dict[str, Any]:
    search_url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
    try:
        body, final_url, content_type = _download_text(search_url, timeout_sec=timeout_sec)
        parser = _BingParser()
        parser.feed(body)
        results = parser.results[:max_results]
        return {
            "tool": "lcr_web_search",
            "query": query,
            "source": "bing_html",
            "url": final_url,
            "content_type": content_type,
            "results": results,
            "result_count": len(results),
            "warning": "" if results else "No parsed results from DuckDuckGo or Bing; try explicit source_urls or a more specific query.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "tool": "lcr_web_search",
            "query": query,
            "source": "bing_html",
            "results": [],
            "result_count": 0,
            "warning": f"Search failed: {type(exc).__name__}: {exc}",
        }


def _normalize_query_specs(queries: Any) -> list[dict[str, Any]]:
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty array.")
    specs: list[dict[str, Any]] = []
    for item in queries[:DEFAULT_BATCH_MAX_QUERIES]:
        if isinstance(item, str):
            query = item.strip()
            max_results = 5
            domains = []
            exclude_domains = []
        elif isinstance(item, dict):
            query = str(item.get("query") or "").strip()
            max_results = int(item.get("max_results") or 5)
            domains = _string_list(item.get("domains"))[:6]
            exclude_domains = _string_list(item.get("exclude_domains"))[:6]
        else:
            continue
        if not query:
            continue
        specs.append(
            {
                "query": query[:300],
                "max_results": max(1, min(10, max_results)),
                "domains": domains,
                "exclude_domains": exclude_domains,
            }
        )
    if not specs:
        raise ValueError("At least one non-empty query is required.")
    return specs


def _expand_query_variants(query: str, *, domains: list[str], exclude_domains: list[str]) -> list[str]:
    del exclude_domains
    normalized_query = re.sub(r"\s+", " ", query).strip()
    lowered = normalized_query.lower()
    variants = [normalized_query]
    if _looks_magic_tower_query(lowered):
        variants.extend(
            [
                normalized_query.replace("magic tower", "Tower of the Sorcerer"),
                normalized_query.replace("Magic Tower", "Tower of the Sorcerer"),
                "Tower of the Sorcerer game design deterministic resource planning",
                "deterministic key door resource-planning dungeon game design",
            ]
        )
    if any(token in lowered for token in ("autotile", "tilemap", "tileset", "sprite", "walk frame", "animation")):
        variants.extend(
            [
                f"{normalized_query} gamedev",
                f"{normalized_query} top down rpg",
                f"{normalized_query} html5 canvas",
            ]
        )
    for domain in domains[:4]:
        clean = str(domain or "").strip()
        if clean:
            variants.append(f"site:{clean} {normalized_query}")
    cleaned = []
    for item in variants:
        compact = re.sub(r"\s+", " ", str(item or "")).strip()
        if compact:
            cleaned.append(compact[:300])
    return list(dict.fromkeys(cleaned))[:8]


def _looks_magic_tower_query(lowered_query: str) -> bool:
    return any(alias in lowered_query for alias in MAGIC_TOWER_ALIASES)


def _rank_results_for_query(
    query: str,
    results: list[dict[str, str]],
    *,
    prefer_domains: list[str],
    exclude_domains: list[str],
) -> list[dict[str, str]]:
    game_dev_query = _looks_magic_tower_query(query.lower()) or any(token in query.lower() for token in GAME_DEV_HINT_TOKENS)
    scored: list[tuple[float, int, dict[str, str]]] = []
    for index, item in enumerate(results):
        score = _score_result_for_query(query, item, prefer_domains=prefer_domains, exclude_domains=exclude_domains)
        enriched = dict(item)
        enriched["relevance_score"] = round(score, 3)
        scored.append((score, index, enriched))
    scored.sort(key=lambda row: (-row[0], row[1]))
    min_score = 0.5 if game_dev_query else -8.0
    deduped = _dedupe_results([item for _, _, item in scored if item.get("relevance_score", 0) > min_score])
    return deduped


def _score_result_for_query(
    query: str,
    item: dict[str, str],
    *,
    prefer_domains: list[str],
    exclude_domains: list[str],
) -> float:
    text = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("snippet") or ""),
            str(item.get("url") or ""),
        ]
    ).lower()
    domain = urllib.parse.urlparse(str(item.get("url") or "")).netloc.lower()
    preferred = {str(domain_name).strip().lower() for domain_name in prefer_domains if str(domain_name).strip()}
    excluded = {str(domain_name).strip().lower() for domain_name in exclude_domains if str(domain_name).strip()}
    score = 0.0
    game_dev_query = _looks_magic_tower_query(query.lower()) or any(token in query.lower() for token in GAME_DEV_HINT_TOKENS)
    query_tokens = _meaningful_tokens(query.lower())
    overlap = sum(1 for token in query_tokens if token in text)
    score += min(8.0, overlap * 1.4)
    if domain in preferred:
        score += 5.0
    if domain in PREFERRED_GAME_DEV_DOMAINS and any(token in query.lower() for token in GAME_DEV_HINT_TOKENS | set(MAGIC_TOWER_ALIASES)):
        score += 3.0
    if domain in LOW_SIGNAL_DOMAINS:
        score -= 6.0
    if domain in excluded:
        score -= 8.0
    if _looks_magic_tower_query(query.lower()):
        if any(alias in text for alias in MAGIC_TOWER_ALIASES):
            score += 5.0
        if "magic: the gathering" in text or "mtg" in text:
            score -= 10.0
    signal_hits = sum(1 for token in GAME_DEV_HINT_TOKENS if token in text)
    if any(token in query.lower() for token in ("tile", "autotile", "tilemap", "sprite", "animation", "rpg", "gamedev")):
        score += min(5.0, signal_hits * 0.8)
    if game_dev_query and signal_hits == 0 and not any(alias in text for alias in MAGIC_TOWER_ALIASES):
        score -= 6.0
    elif game_dev_query and signal_hits == 1 and domain not in PREFERRED_GAME_DEV_DOMAINS:
        score -= 2.5
    if "wikipedia.org" in domain and game_dev_query and signal_hits < 2:
        score -= 3.0
    if any(noise in text for noise in ("dictionary", "supernatural phenomenon", "trading card game")):
        score -= 7.0
    return score


def _meaningful_tokens(text: str) -> list[str]:
    stop = {
        "a",
        "an",
        "and",
        "the",
        "for",
        "with",
        "from",
        "into",
        "game",
        "games",
        "what",
        "how",
        "best",
        "guide",
    }
    return [token for token in re.findall(r"[a-z0-9_+-]{3,}", text) if token not in stop]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    result = []
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        if _looks_secret_like(text):
            raise ValueError("Web research arguments cannot contain secret-like values.")
        result.append(text[:500])
    return result


def _dedupe_results(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped = []
    for item in results:
        url = str(item.get("url") or "").strip()
        key = _canonical_url(url)
        if not url or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _canonical_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [(key, value) for key, value in query if not key.lower().startswith("utm_")]
    return urllib.parse.urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", urllib.parse.urlencode(filtered), ""))


def _derive_research_queries(goal: str) -> list[str]:
    compact = re.sub(r"\s+", " ", goal).strip()
    queries = [compact]
    lowered = compact.lower()
    if _looks_magic_tower_query(lowered):
        queries.extend(
            [
                "\"Tower of the Sorcerer\" deterministic resource-planning game design",
                "deterministic key door resource-planning dungeon game design",
            ]
        )
    if any(token in lowered for token in ["autotile", "tilemap", "tileset", "sprite", "animation", "html5", "canvas"]):
        queries.extend(
            [
                "site:developer.mozilla.org tilemap top down game rendering",
                "site:doc.mapeditor.org terrain set automapping tilemap",
                "site:gamedev.stackexchange.com autotile edge corner transition tilemap",
                "site:docs.godotengine.org tilemap autotile terrain set",
            ]
        )
    if any(token in lowered for token in ["魔塔", "tower", "rpg", "game", "autotile", "sprite"]):
        queries.extend(
            [
                f"{compact} best practices",
                f"{compact} implementation guide",
                f"{compact} examples",
                "RPG autotile rules tilemap edge corner transition",
                "magic tower game design deterministic resource planning",
            ]
        )
    else:
        queries.extend([f"{compact} official documentation", f"{compact} guide", f"{compact} best practices"])
    return list(dict.fromkeys(query[:300] for query in queries if query))[:DEFAULT_BATCH_MAX_QUERIES]


def _compose_extract_brief(goal: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    bullets = []
    for index, source in enumerate(sources[:6], start=1):
        excerpt = re.sub(r"\s+", " ", str(source.get("excerpt") or source.get("snippet") or "")).strip()
        if not excerpt:
            continue
        bullets.append(
            {
                "source_index": index,
                "url": source.get("url"),
                "extract": excerpt[:500],
            }
        )
    return {
        "summary": (
            "Extractive source pack generated for the research goal. The model should synthesize conclusions "
            "from these excerpts and cite source URLs explicitly."
        ),
        "goal": goal,
        "source_extracts": bullets,
    }


def _suggest_followup_queries(goal: str, queries: list[str], sources: list[dict[str, Any]]) -> list[str]:
    suggestions = []
    if len(sources) < 3:
        suggestions.append(f"{goal} official documentation")
    suggestions.append(f"{goal} case study")
    suggestions.append(f"{goal} pitfalls")
    for query in queries:
        if "official" not in query.lower():
            suggestions.append(f"{query} official")
            break
    return list(dict.fromkeys(suggestions))[:5]


def _looks_secret_like(value: str) -> bool:
    if re.search(r"(?i)(authorization|bearer\s+|api[_-]?key|secret|cookie|token)", value):
        return True
    return bool(re.search(r"sk-[A-Za-z0-9_-]{8,}", value))


def _fetch(url: str, *, max_chars: int, timeout_sec: int) -> dict[str, Any]:
    _validate_public_url(url)
    body, final_url, content_type = _download_text(url, timeout_sec=timeout_sec)
    text = _html_to_text(body) if "html" in content_type.lower() or "<html" in body[:500].lower() else body
    text = _redact_sensitive_text(text)
    max_chars = max(500, min(20000, int(max_chars or DEFAULT_MAX_CHARS)))
    truncated = len(text) > max_chars
    return {
        "tool": "lcr_web_fetch",
        "url": final_url,
        "content_type": content_type,
        "text": text[:max_chars],
        "truncated": truncated,
        "char_count": len(text),
    }


def _download_text(url: str, *, timeout_sec: int) -> tuple[str, str, str]:
    _validate_public_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AstraBridge/0.1 (+https://astrabridge.invalid)",
            "Accept": "text/html, text/plain, application/json;q=0.8, */*;q=0.5",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=max(5, min(60, int(timeout_sec or DEFAULT_TIMEOUT_SEC)))) as response:  # noqa: S310
        content_type = str(response.headers.get("Content-Type") or "text/plain")
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read(1_000_000)
        text = raw.decode(charset, errors="replace")
        return text, str(response.geturl() or url), content_type


def _validate_public_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only public HTTP(S) URLs are supported.")
    host = parsed.hostname or ""
    if not host:
        raise ValueError("URL host is required.")
    if host.lower() in {"localhost"} or host.endswith(".local"):
        raise ValueError("Localhost and .local URLs are blocked for web research tools.")
    try:
        addresses = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve host: {host}") from exc
    for entry in addresses:
        ip_text = entry[4][0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError("Private, loopback, link-local, multicast, and reserved addresses are blocked.")


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._active: dict[str, str] | None = None
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = attr.get("class", "")
        if tag == "a" and "result__a" in classes:
            self._active = {"title": "", "url": _clean_ddg_url(attr.get("href", "")), "snippet": ""}
            self._capture_title = True
        elif self._active is not None and tag in {"a", "div"} and ("result__snippet" in classes or "result__body" in classes):
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            self._capture_title = False
            if self._active is not None and self._active.get("url"):
                self.results.append({key: value.strip() for key, value in self._active.items()})
                self._active = None
        if tag in {"a", "div"}:
            self._capture_snippet = False

    def handle_data(self, data: str) -> None:
        if self._active is None:
            return
        text = html.unescape(data).strip()
        if not text:
            return
        if self._capture_title:
            self._active["title"] = (self._active.get("title", "") + " " + text).strip()
        elif self._capture_snippet:
            self._active["snippet"] = (self._active.get("snippet", "") + " " + text).strip()


def _clean_ddg_url(url: str) -> str:
    text = html.unescape(url or "")
    parsed = urllib.parse.urlparse(text)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return str(query["uddg"][0])
    return text


class _BingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._active: dict[str, str] | None = None
        self._depth = 0
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = attr.get("class", "")
        if self._active is None and tag == "li" and "b_algo" in classes:
            self._active = {"title": "", "url": "", "snippet": ""}
            self._depth = 1
            return
        if self._active is None:
            return
        self._depth += 1
        if tag == "a" and not self._active.get("url"):
            href = attr.get("href", "")
            if href.startswith(("http://", "https://")):
                self._active["url"] = _clean_bing_url(href)
                self._capture_title = True
        elif tag == "p":
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if self._active is None:
            return
        if tag == "a":
            self._capture_title = False
        elif tag == "p":
            self._capture_snippet = False
        self._depth -= 1
        if self._depth <= 0:
            if self._active.get("url") and self._active.get("title"):
                self.results.append({key: value.strip() for key, value in self._active.items()})
            self._active = None
            self._capture_title = False
            self._capture_snippet = False

    def handle_data(self, data: str) -> None:
        if self._active is None:
            return
        text = html.unescape(data).strip()
        if not text:
            return
        if self._capture_title:
            self._active["title"] = (self._active.get("title", "") + " " + text).strip()
        elif self._capture_snippet:
            self._active["snippet"] = (self._active.get("snippet", "") + " " + text).strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in {"p", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = html.unescape(data).strip()
        if text:
            self.parts.append(text)


def _html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    text = " ".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_bing_url(url: str) -> str:
    text = html.unescape(url or "")
    parsed = urllib.parse.urlparse(text)
    if "bing.com" not in parsed.netloc.lower():
        return text
    query = urllib.parse.parse_qs(parsed.query)
    raw = (query.get("u") or [""])[0]
    if not raw:
        return text
    if raw.startswith(("http://", "https://")):
        return raw
    candidate = raw[2:] if raw.startswith("a1") else raw
    try:
        padding = "=" * (-len(candidate) % 4)
        decoded = base64.urlsafe_b64decode((candidate + padding).encode("ascii")).decode("utf-8", errors="replace")
        if decoded.startswith(("http://", "https://")):
            return decoded
    except Exception:
        return text
    return text


def _redact_sensitive_text(text: str) -> str:
    patterns = [
        (re.compile(r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]+"), "Authorization: [REDACTED]"),
        (re.compile(r"(?i)(api[_-]?key|token|secret|cookie)\s*[:=]\s*[A-Za-z0-9._~+/=-]{8,}"), r"\1=[REDACTED]"),
        (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "sk-[REDACTED]"),
    ]
    redacted = text
    for pattern, replacement in patterns:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _tool_text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]}


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    global _OUTPUT_FRAMING
    first = _read_first_nonempty_byte(stream)
    if not first:
        return None
    if first == b"{":
        _OUTPUT_FRAMING = "raw"
        return json.loads(_read_json_object(stream, first).decode("utf-8"))
    _OUTPUT_FRAMING = "header"
    headers: dict[str, str] = {}
    line = first + stream.readline()
    while line and line.strip():
        text = line.decode("ascii", errors="replace")
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.lower()] = value.strip()
        line = stream.readline()
    length = int(headers.get("content-length") or 0)
    if length <= 0:
        return None
    return json.loads(stream.read(length).decode("utf-8"))


def _read_first_nonempty_byte(stream: BinaryIO) -> bytes:
    while True:
        chunk = stream.read(1)
        if not chunk:
            return b""
        if chunk in b" \t\r\n":
            continue
        return chunk


def _read_json_object(stream: BinaryIO, first: bytes) -> bytes:
    buffer = bytearray(first)
    depth = 1
    in_string = False
    escaped = False
    while depth > 0:
        chunk = stream.read(1)
        if not chunk:
            break
        char = chunk[0]
        buffer.extend(chunk)
        if in_string:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                in_string = False
            continue
        if char == 34:
            in_string = True
        elif char == 123:
            depth += 1
        elif char == 125:
            depth -= 1
    return bytes(buffer)


def _write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if _OUTPUT_FRAMING == "raw":
        stream.write(body + b"\n")
        stream.flush()
        return
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    stream.write(body)
    stream.flush()


def _debug(event: str, **fields: Any) -> None:
    try:
        raw_path = os.environ.get("LCR_MCP_DEBUG_LOG")
        if not raw_path:
            local_app_data = os.environ.get("LOCALAPPDATA")
            if not local_app_data:
                return
            raw_path = str(Path(local_app_data) / "AstraBridge" / "mcp" / "lcr_web_debug.jsonl")
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()

