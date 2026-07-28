from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urldefrag, urljoin, urlsplit

from ..common import now_iso, write_json
from ..model_catalog import default_catalog_sources, normalize_provider_source_record
from ..security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, SECRET_RE
from .artifacts import ensure_agentic_update_run_layout
from .contracts import assert_secret_free_agentic_update_payload, normalize_update_scope_contract


AGENTIC_UPDATE_DISCOVERY_SCHEMA_VERSION = "astrabridge-agentic-update-discovery-run-v1"
DEFAULT_DISCOVERY_MAX_SOURCES = 20
DEFAULT_DISCOVERY_TIMEOUT_SEC = 6
DEFAULT_DISCOVERY_MAX_BYTES_PER_SOURCE = 120_000
DEFAULT_DISCOVERY_MAX_EXCERPT_CHARS = 1_200
DEFAULT_DISCOVERY_MAX_PARSER_EXCERPT_CHARS = 20_000
ALLOWED_DISCOVERY_SCHEMES = frozenset({"http", "https"})
ALLOWED_DISCOVERY_TEXT_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/problem+json",
    "application/ld+json",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
    "application/yaml",
    "text/yaml",
    "application/x-yaml",
    "application/openapi+json",
    "application/openapi+xml",
)
DOCUMENT_INDEX_PARSER_STRATEGY = "llms_index"
DOCUMENT_INDEX_MAX_DEPTH = 1
_MARKDOWN_LINK_RE = re.compile(r"\[(?P<title>[^\]\r\n]{1,240})\]\((?P<href>[^)\s]+)\)")
_PROVIDER_DOCUMENT_ALIASES = {
    "deepseek": ("deepseek",),
    "glm": ("glm", "z.ai", "zhipu"),
    "kimi": ("kimi", "moonshot"),
    "qwen": ("qwen", "dashscope"),
}
FetchResult = dict[str, Any]
FetchFunction = Callable[[str, int, int], FetchResult]


def run_agentic_update_discovery(
    *,
    workspace_root: str | Path,
    run_id: str,
    run_contract: dict[str, Any],
    provider_sources: list[dict[str, Any]] | None = None,
    fixture_sources: dict[str, Any] | None = None,
    fetcher: FetchFunction | None = None,
    max_sources: int = DEFAULT_DISCOVERY_MAX_SOURCES,
    timeout_sec: int = DEFAULT_DISCOVERY_TIMEOUT_SEC,
    max_bytes_per_source: int = DEFAULT_DISCOVERY_MAX_BYTES_PER_SOURCE,
    max_excerpt_chars: int = DEFAULT_DISCOVERY_MAX_EXCERPT_CHARS,
    max_parser_excerpt_chars: int = DEFAULT_DISCOVERY_MAX_PARSER_EXCERPT_CHARS,
) -> dict[str, Any]:
    contract = normalize_update_scope_contract(run_contract)
    layout = ensure_agentic_update_run_layout(workspace_root, run_id)
    limits = _normalize_limits(
        max_sources=max_sources,
        timeout_sec=timeout_sec,
        max_bytes_per_source=max_bytes_per_source,
        max_excerpt_chars=max_excerpt_chars,
        max_parser_excerpt_chars=max_parser_excerpt_chars,
    )
    source_records, limit_warning = _select_source_records(
        provider_sources or default_catalog_sources(),
        providers=set(contract.get("providers") or []),
        max_sources=limits["max_sources"],
    )
    mode = "fixture" if fixture_sources is not None or not contract["allow_network"] else "network"
    pack_records: list[dict[str, Any]] = []
    warnings: list[str] = []
    if limit_warning:
        warnings.append(limit_warning)
    source_queue = list(source_records)
    known_urls = {str(source.get("url") or "").strip() for source in source_queue if str(source.get("url") or "").strip()}
    seen_urls: set[str] = set()
    seen_source_identity_hashes: set[str] = set()
    active_fetcher = fetcher or _default_fetch
    while source_queue and len(pack_records) < limits["max_sources"]:
        source = source_queue.pop(0)
        url = str(source.get("url") or "").strip()
        if url in seen_urls:
            pack_records.append(_discovery_skip_record(source, classification="duplicate", reason="Duplicate source URL in run."))
            continue
        seen_urls.add(url)
        blocked = _blocked_source_url_record(source)
        if blocked is not None:
            pack_records.append(blocked)
            continue
        if str(source.get("trust_level") or "") != "official":
            pack_records.append(
                _discovery_skip_record(
                    source,
                    classification="untrusted_source",
                    reason="Source is non-promotable until manual review.",
                )
            )
            continue
        if mode == "fixture":
            fixture = _fixture_for_source(fixture_sources or {}, source)
            if fixture is None:
                pack_records.append(_discovery_skip_record(source, classification="fixture_missing", reason="No fixture was provided for this source."))
                continue
            record = _result_record_from_fetch(
                source,
                _coerce_fixture_fetch_result(fixture, source),
                mode=mode,
                limits=limits,
            )
            record = _dedupe_source_identity(record, seen_source_identity_hashes)
        else:
            try:
                fetched = active_fetcher(url, limits["timeout_sec"], limits["max_bytes_per_source"])
                record = _result_record_from_fetch(source, fetched, mode=mode, limits=limits)
                record = _dedupe_source_identity(record, seen_source_identity_hashes)
            except Exception as exc:  # noqa: BLE001
                record = _discovery_error_record(source, exc)
        pack_records.append(record)
        if bool(record.get("ok")) and str(source.get("parser_strategy") or "") == DOCUMENT_INDEX_PARSER_STRATEGY:
            remaining = max(0, limits["max_sources"] - len(pack_records) - len(source_queue))
            discovered, truncated = _discover_document_index_sources(source, record, limit=remaining, excluded_urls=known_urls)
            for discovered_source in discovered:
                discovered_url = str(discovered_source.get("url") or "").strip()
                if not discovered_url or discovered_url in known_urls:
                    continue
                source_queue.append(discovered_source)
                known_urls.add(discovered_url)
            if truncated:
                warnings.append(f"document_index_source_limit_reached:{source.get('source_id') or 'unknown_source'}")
    summary = _discovery_summary(pack_records)
    generated_at = now_iso()
    index_payload = {
        "schema_version": AGENTIC_UPDATE_DISCOVERY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "run_id": run_id,
        "mode": mode,
        "run_contract": contract,
        "limits": limits,
        "summary": summary,
        "sources": [_index_record(record) for record in pack_records],
        "warnings": warnings,
        "artifact_paths": {
            "source_index": layout["files"]["source_index"],
            "source_pack": layout["files"]["source_pack"],
        },
    }
    assert_secret_free_agentic_update_payload(index_payload, label="agentic_update_discovery_index")
    assert_secret_free_agentic_update_payload(pack_records, label="agentic_update_discovery_pack")
    write_json(Path(layout["files"]["source_index"]), index_payload)
    _write_jsonl(Path(layout["files"]["source_pack"]), pack_records)
    return {
        "schema_version": AGENTIC_UPDATE_DISCOVERY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "run_id": run_id,
        "mode": mode,
        "status": summary["status"],
        "summary": summary,
        "artifact_paths": index_payload["artifact_paths"],
        "sources": index_payload["sources"],
        "warnings": warnings,
    }


def _select_source_records(
    provider_sources: list[dict[str, Any]],
    *,
    providers: set[str],
    max_sources: int,
) -> tuple[list[dict[str, Any]], str | None]:
    selected: list[dict[str, Any]] = []
    truncated = False
    for provider in provider_sources:
        normalized = normalize_provider_source_record(dict(provider))
        provider_id = str(normalized.get("provider_id") or "")
        if providers and provider_id not in providers:
            continue
        for record in normalized["source_records"]:
            if len(selected) >= max_sources:
                truncated = True
                break
            selected.append(
                {
                    **record,
                    "provider_id": provider_id,
                    "display_name": normalized.get("display_name"),
                    "provider_trust_level": normalized.get("trust_level"),
                    "provider_promotion_policy": dict(normalized.get("promotion_policy") or {}),
                }
            )
        if truncated:
            break
    warning = "source_limit_reached" if truncated else None
    return selected, warning


def _discover_document_index_sources(
    source: dict[str, Any],
    record: dict[str, Any],
    *,
    limit: int,
    excluded_urls: set[str] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    if int(source.get("discovery_depth") or 0) >= DOCUMENT_INDEX_MAX_DEPTH:
        return [], False
    text = str(record.get("parser_excerpt") or "")
    base_url = str(record.get("final_url") or source.get("url") or "").strip()
    if not text or not base_url:
        return [], False
    provider_id = str(source.get("provider_id") or "").strip().lower()
    candidates: dict[str, tuple[int, dict[str, Any]]] = {}
    for match in _MARKDOWN_LINK_RE.finditer(text):
        title = " ".join(match.group("title").split())
        href = match.group("href").strip().strip("<>")
        candidate_url = urldefrag(urljoin(base_url, href))[0]
        if candidate_url in (excluded_urls or set()):
            continue
        if not _same_origin_document_url(base_url, candidate_url):
            continue
        metadata = _document_index_link_metadata(provider_id, title=title, url=candidate_url)
        if metadata is None:
            continue
        score, source_type, channel, parser_strategy, capability_categories, source_stability = metadata
        discovered = {
            "source_id": _document_index_source_id(str(source.get("source_id") or provider_id or "provider"), candidate_url),
            "url": candidate_url,
            "provider_id": provider_id,
            "platform_id": source.get("platform_id"),
            "display_name": source.get("display_name"),
            "source_type": source_type,
            "trust_level": source.get("trust_level"),
            "channel": channel,
            "parser_strategy": parser_strategy,
            "stale_after_days": int(source.get("stale_after_days") or 7),
            "capability_categories": capability_categories,
            "source_stability": source_stability,
            "source_role": source.get("source_role"),
            "retrieved_on": source.get("retrieved_on"),
            "promotable": bool(source.get("promotable", False)),
            "requires_manual_review": bool(source.get("requires_manual_review", False)),
            "provider_trust_level": source.get("provider_trust_level"),
            "provider_promotion_policy": dict(source.get("provider_promotion_policy") or {}),
            "discovered_from_source_id": source.get("source_id"),
            "discovery_depth": int(source.get("discovery_depth") or 0) + 1,
            "document_link_title": title,
        }
        current = candidates.get(candidate_url)
        if current is None or score > current[0]:
            candidates[candidate_url] = (score, discovered)
    ordered = [item for _, item in sorted(candidates.values(), key=lambda pair: (-pair[0], str(pair[1].get("url") or "")))]
    bounded_limit = max(0, int(limit))
    return ordered[:bounded_limit], len(ordered) > bounded_limit


def _same_origin_document_url(base_url: str, candidate_url: str) -> bool:
    try:
        base = urlsplit(base_url)
        candidate = urlsplit(candidate_url)
    except ValueError:
        return False
    if base.scheme.lower() not in ALLOWED_DISCOVERY_SCHEMES or candidate.scheme.lower() != base.scheme.lower():
        return False
    if candidate.username or candidate.password or candidate.query:
        return False
    if not base.hostname or not candidate.hostname or base.hostname.lower() != candidate.hostname.lower():
        return False
    if base.port != candidate.port or _is_private_or_local_host(candidate.hostname):
        return False
    path = candidate.path.lower()
    return path.endswith(".md") and not path.endswith("/llms.md")


def _document_index_link_metadata(
    provider_id: str,
    *,
    title: str,
    url: str,
) -> tuple[int, str, str, str, list[str], str] | None:
    path = urlsplit(url).path.lower()
    text = f"{title} {path}".lower()
    aliases = _PROVIDER_DOCUMENT_ALIASES.get(provider_id, (provider_id,))
    provider_specific = any(alias and alias in text for alias in aliases)
    version_specific = bool(re.search(r"(?:^|[-_/])(?:k|v)\d(?:[.\d-]*)(?:[-_/]|\.md|$)", text))
    modelish = provider_specific or version_specific

    if path.endswith("/models.md") or "list-models" in path or "models-overview" in path or "model list" in text:
        return (1000, "models_catalog", "stable_docs", "markdown_table", ["models_catalog", "context_window", "reasoning"], "stable")
    if provider_specific and "/guides/llm/" in path and path.endswith(".md"):
        return (
            1000,
            "models_catalog",
            "stable_docs",
            "markdown_document",
            ["models_catalog", "context_window", "reasoning", "tool_calling", "image_input", "video_input"],
            "versioned",
        )
    if ("/pricing/chat" in path or ("model" in text and "pricing" in text)) and (modelish or path.endswith("/pricing/chat.md")):
        return (800 + (100 if version_specific else 0), "pricing", "pricing", "markdown_table", ["pricing", "models_catalog", "context_window"], "likely_to_change")
    if ("quickstart" in text or "model guide" in text) and modelish:
        return (
            900 + (100 if version_specific else 0),
            "guide",
            "stable_docs",
            "markdown_document",
            ["models_catalog", "context_window", "reasoning", "tool_calling", "image_input", "video_input"],
            "versioned",
        )
    if "reasoning" in text or "thinking" in text:
        return (750, "guide", "stable_docs", "markdown_document", ["reasoning", "tool_calling"], "likely_to_change")
    if path.endswith("/pricing.md"):
        return (700, "pricing", "pricing", "markdown_table", ["pricing", "models_catalog"], "likely_to_change")
    if ("tool" in text or "function-calling" in text) and modelish:
        return (650 + (100 if version_specific else 0), "guide", "stable_docs", "markdown_document", ["tool_calling", "reasoning"], "likely_to_change")
    if "changelog" in text or "release" in text:
        return (600, "release_notes", "release_notes", "markdown_document", ["release_notes", "models_catalog"], "likely_to_change")
    if any(term in text for term in ("vision", "image", "video", "multimodal")) and (modelish or "vision" in text):
        return (550, "guide", "stable_docs", "markdown_document", ["image_input", "video_input", "models_catalog"], "likely_to_change")
    if path.endswith("/api/chat.md") or "chat completion" in text:
        return (450, "api_reference", "api_reference", "markdown_document", ["protocol_reference", "tool_calling", "streaming", "reasoning"], "stable")
    return None


def _document_index_source_id(parent_source_id: str, url: str) -> str:
    path = urlsplit(url).path.strip("/")
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or "document"
    prefix = re.sub(r"[^a-z0-9]+", "-", parent_source_id.lower()).strip("-") or "provider-index"
    return f"{prefix}-linked-{slug}"[:120].rstrip("-")


def _default_fetch(url: str, timeout_sec: int, max_bytes: int) -> FetchResult:
    started = now_iso()
    started_monotonic = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "AstraBridge-agentic-update-discovery/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            body = response.read(max_bytes + 1)
            duration_ms = int(max(0.0, time.monotonic() - started_monotonic) * 1000)
            return {
                "url": str(getattr(response, "url", url) or url),
                "status_code": getattr(response, "status", None),
                "content_type": str(response.headers.get("Content-Type") or ""),
                "content_encoding": str(response.headers.get("Content-Encoding") or ""),
                "content_length": _optional_int(response.headers.get("Content-Length")),
                "body": body[:max_bytes],
                "body_truncated": len(body) > max_bytes,
                "started_at": started,
                "finished_at": now_iso(),
                "duration_ms": duration_ms,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(max_bytes + 1)
        duration_ms = int(max(0.0, time.monotonic() - started_monotonic) * 1000)
        return {
            "url": url,
            "status_code": exc.code,
            "content_type": str(exc.headers.get("Content-Type") if exc.headers else ""),
            "content_encoding": str(exc.headers.get("Content-Encoding") if exc.headers else ""),
            "content_length": _optional_int(exc.headers.get("Content-Length")) if exc.headers else None,
            "body": body[:max_bytes],
            "body_truncated": len(body) > max_bytes,
            "started_at": started,
            "finished_at": now_iso(),
            "duration_ms": duration_ms,
            "http_error": True,
            "error_summary": str(exc.reason or exc)[:240],
        }


def _result_record_from_fetch(source: dict[str, Any], fetched: FetchResult, *, mode: str, limits: dict[str, int]) -> dict[str, Any]:
    body = _coerce_body(fetched.get("body"))
    text = _decode_body(body, str(fetched.get("content_type") or ""))
    excerpt = _safe_excerpt(text, limits["max_excerpt_chars"])
    parser_excerpt = _safe_parser_excerpt(
        text,
        limits["max_parser_excerpt_chars"],
        preserve_document=str(source.get("parser_strategy") or "") in {"llms_index", "markdown_document", "markdown_table", "html_table"},
    )
    status_code = _optional_int(fetched.get("status_code"))
    ok = bool(status_code is None or 200 <= status_code < 400) and not bool(fetched.get("http_error"))
    classification = "ok" if ok else "http_error"
    record = {
        "schema_version": AGENTIC_UPDATE_DISCOVERY_SCHEMA_VERSION,
        "provider_id": source.get("provider_id"),
        "platform_id": source.get("platform_id"),
        "source_id": source.get("source_id"),
        "url": source.get("url"),
        "final_url": _safe_url(str(fetched.get("url") or source.get("url") or "")),
        "mode": mode,
        "ok": ok,
        "classification": classification,
        "status_label": classification,
        "status_code": status_code,
        "content_type": str(fetched.get("content_type") or ""),
        "content_encoding": str(fetched.get("content_encoding") or ""),
        "content_length": _optional_int(fetched.get("content_length")),
        "content_hash": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "source_identity_hash": _source_identity_hash(source, fetched, body),
        "content_bytes": len(body),
        "body_truncated": bool(fetched.get("body_truncated", False)),
        "excerpt": excerpt,
        "excerpt_chars": len(excerpt),
        "parser_excerpt": parser_excerpt,
        "parser_excerpt_chars": len(parser_excerpt),
        "started_at": fetched.get("started_at") or now_iso(),
        "finished_at": fetched.get("finished_at") or now_iso(),
        "duration_ms": _optional_int(fetched.get("duration_ms")),
        "source_type": source.get("source_type"),
        "trust_level": source.get("trust_level"),
        "channel": source.get("channel"),
        "parser_strategy": source.get("parser_strategy"),
        "capability_categories": list(source.get("capability_categories") or []),
        "source_stability": source.get("source_stability"),
        "source_role": source.get("source_role"),
        "retrieved_on": source.get("retrieved_on"),
        "discovered_from_source_id": source.get("discovered_from_source_id"),
        "discovery_depth": int(source.get("discovery_depth") or 0),
        "document_link_title": source.get("document_link_title"),
        "promotable": bool(source.get("promotable", False)),
        "requires_manual_review": bool(source.get("requires_manual_review", False)),
        "warnings": [],
    }
    if fetched.get("error_summary"):
        record["warnings"].append(str(fetched.get("error_summary"))[:240])
    boundary_issue = _boundary_issue(source, fetched, record, limits=limits)
    if boundary_issue is None:
        return record
    classification, reason = boundary_issue
    return _mark_record_blocked(record, classification=classification, reason=reason)


def _discovery_skip_record(source: dict[str, Any], *, classification: str, reason: str) -> dict[str, Any]:
    now = now_iso()
    return {
        "schema_version": AGENTIC_UPDATE_DISCOVERY_SCHEMA_VERSION,
        "provider_id": source.get("provider_id"),
        "platform_id": source.get("platform_id"),
        "source_id": source.get("source_id"),
        "url": source.get("url"),
        "final_url": source.get("url"),
        "mode": "skipped",
        "ok": False,
        "classification": classification,
        "status_label": classification,
        "status_code": None,
        "content_type": None,
        "content_encoding": None,
        "content_length": None,
        "content_hash": None,
        "source_identity_hash": None,
        "content_bytes": 0,
        "body_truncated": False,
        "excerpt": "",
        "excerpt_chars": 0,
        "parser_excerpt": "",
        "parser_excerpt_chars": 0,
        "started_at": now,
        "finished_at": now,
        "duration_ms": 0,
        "source_type": source.get("source_type"),
        "trust_level": source.get("trust_level"),
        "channel": source.get("channel"),
        "parser_strategy": source.get("parser_strategy"),
        "capability_categories": list(source.get("capability_categories") or []),
        "source_stability": source.get("source_stability"),
        "source_role": source.get("source_role"),
        "retrieved_on": source.get("retrieved_on"),
        "discovered_from_source_id": source.get("discovered_from_source_id"),
        "discovery_depth": int(source.get("discovery_depth") or 0),
        "document_link_title": source.get("document_link_title"),
        "promotable": False,
        "requires_manual_review": True,
        "warnings": [reason],
    }


def _discovery_error_record(source: dict[str, Any], exc: Exception) -> dict[str, Any]:
    classification = _classify_fetch_exception(exc)
    record = _discovery_skip_record(source, classification=classification, reason=f"{type(exc).__name__}: {exc}")
    record["mode"] = "network"
    record["requires_manual_review"] = bool(source.get("requires_manual_review", False))
    return record


def _blocked_source_url_record(source: dict[str, Any]) -> dict[str, Any] | None:
    url = str(source.get("url") or "").strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        return _discovery_skip_record(source, classification="invalid_source_url", reason="Source URL could not be parsed.")
    if parsed.scheme.lower() not in ALLOWED_DISCOVERY_SCHEMES:
        return _discovery_skip_record(source, classification="unsupported_scheme", reason="Discovery sources must use http or https URLs.")
    host = str(parsed.hostname or "").strip()
    if not host:
        return _discovery_skip_record(source, classification="invalid_source_url", reason="Source URL must include a hostname.")
    if _is_private_or_local_host(host):
        return _discovery_skip_record(source, classification="private_address_blocked", reason="Discovery source resolves to a private or local address.")
    return None


def _boundary_issue(
    source: dict[str, Any],
    fetched: FetchResult,
    record: dict[str, Any],
    *,
    limits: dict[str, int],
) -> tuple[str, str] | None:
    if not bool(record.get("ok")):
        return None
    requested_url = str(source.get("url") or "").strip()
    final_url = str(fetched.get("url") or requested_url or "").strip()
    try:
        requested = urlsplit(requested_url)
        final = urlsplit(final_url)
    except ValueError:
        return ("invalid_final_url", "Fetched response returned an invalid final URL.")
    requested_host = str(requested.hostname or "").strip()
    final_host = str(final.hostname or "").strip()
    if final_host and _is_private_or_local_host(final_host):
        return ("private_address_blocked", "Discovery response resolved to a private or local final address.")
    if requested_host and final_host and requested_host.lower() != final_host.lower():
        return ("wrong_host_response", "Discovery response host does not match the requested official source host.")
    if final_url and requested_url and _normalized_url_identity(final_url) != _normalized_url_identity(requested_url):
        return ("redirect_blocked", "Discovery responses must not redirect away from the requested source URL.")
    content_encoding = str(fetched.get("content_encoding") or "").strip().lower()
    if content_encoding and content_encoding not in {"identity", "none"}:
        return ("decompression_blocked", "Compressed discovery responses are rejected to avoid decompression abuse.")
    content_length = _optional_int(fetched.get("content_length"))
    if bool(fetched.get("body_truncated")) or (content_length is not None and content_length > limits["max_bytes_per_source"]):
        return ("oversized_response", "Discovery response exceeded the configured byte limit.")
    if not _content_type_allowed(str(record.get("content_type") or "")):
        return ("wrong_content_type", "Discovery response content type is not an allowed textual update source.")
    return None


def _mark_record_blocked(record: dict[str, Any], *, classification: str, reason: str) -> dict[str, Any]:
    blocked = dict(record)
    blocked["ok"] = False
    blocked["classification"] = classification
    blocked["status_label"] = classification
    blocked["promotable"] = False
    blocked["requires_manual_review"] = True
    warnings = list(blocked.get("warnings") or [])
    warnings.append(reason)
    blocked["warnings"] = warnings
    return blocked


def _dedupe_source_identity(record: dict[str, Any], seen_identities: set[str]) -> dict[str, Any]:
    identity_hash = str(record.get("source_identity_hash") or "").strip()
    if not bool(record.get("ok")) or not identity_hash:
        return record
    if identity_hash in seen_identities:
        return _mark_record_blocked(
            record,
            classification="replayed_source",
            reason="Source identity was already observed earlier in this discovery run.",
        )
    seen_identities.add(identity_hash)
    return record


def _classify_fetch_exception(exc: Exception) -> str:
    text = str(exc).lower()
    if isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in text or "timeout" in text:
        return "timeout"
    if isinstance(exc, urllib.error.URLError) and "timed out" in str(getattr(exc, "reason", "")).lower():
        return "timeout"
    return "fetch_failed"


def _fixture_for_source(fixture_sources: dict[str, Any], source: dict[str, Any]) -> Any | None:
    for key in (str(source.get("source_id") or ""), str(source.get("url") or "")):
        if key and key in fixture_sources:
            return fixture_sources[key]
    return None


def _coerce_fixture_fetch_result(fixture: Any, source: dict[str, Any]) -> FetchResult:
    if isinstance(fixture, dict):
        payload = dict(fixture)
        body = payload.get("body", payload.get("text", ""))
        return {
            "url": payload.get("url") or source.get("url"),
            "status_code": payload.get("status_code", 200),
            "content_type": payload.get("content_type") or "text/plain; charset=utf-8",
            "content_encoding": payload.get("content_encoding") or "",
            "content_length": payload.get("content_length"),
            "body": body,
            "body_truncated": bool(payload.get("body_truncated", False)),
            "started_at": payload.get("started_at") or now_iso(),
            "finished_at": payload.get("finished_at") or now_iso(),
            "duration_ms": payload.get("duration_ms", 0),
        }
    return {
        "url": source.get("url"),
        "status_code": 200,
        "content_type": "text/plain; charset=utf-8",
        "content_encoding": "",
        "content_length": None,
        "body": fixture,
        "body_truncated": False,
        "started_at": now_iso(),
        "finished_at": now_iso(),
        "duration_ms": 0,
    }


def _coerce_body(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if value is None:
        return b""
    return str(value).encode("utf-8", errors="replace")


def _decode_body(body: bytes, content_type: str) -> str:
    encoding = "utf-8"
    for part in content_type.split(";"):
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value.strip():
            encoding = value.strip()
            break
    return body.decode(encoding, errors="replace")


def _safe_excerpt(text: str, max_chars: int) -> str:
    value = _sanitize_text_for_artifact(text)
    if len(value) > max_chars:
        return value[:max_chars].rstrip() + "\n[truncated]"
    return value


def _safe_parser_excerpt(text: str, max_chars: int, *, preserve_document: bool = False) -> str:
    value = _sanitize_text_for_artifact(text)
    stripped = value.lstrip()
    if preserve_document or stripped.startswith(("{", "[")):
        return value[:max_chars].rstrip() + ("\n[truncated]" if len(value) > max_chars else "")
    parser_signal = re.compile(
        r"(?i)(?:"
        r"\b(?:qwen|deepseek|kimi|moonshot|glm|gpt|o[0-9])[-a-z0-9._]*\b"
        r"|\breasoning[_ -]?effort\b"
        r"|\bcontext\s+(?:length|window)\b"
        r"|\b(?:cache\s+(?:hit|miss)|tool\s+calls?|input\s+modalit(?:y|ies))\b"
        r")"
    )
    snippets: list[str] = []
    seen: set[str] = set()
    for match in parser_signal.finditer(value):
        start = max(0, match.start() - 180)
        end = min(len(value), match.end() + 180)
        snippet = value[start:end].strip()
        if not snippet or snippet in seen:
            continue
        snippets.append(snippet)
        seen.add(snippet)
        if sum(len(item) + 12 for item in snippets) >= max_chars:
            break
    if not snippets:
        return value[:max_chars].rstrip() + ("\n[truncated]" if len(value) > max_chars else "")
    joined = "\n--- parser-context ---\n".join(snippets)
    if len(joined) > max_chars:
        return joined[:max_chars].rstrip() + "\n[truncated]"
    return joined


def _sanitize_text_for_artifact(text: str) -> str:
    value = text.replace("\x00", "")
    value = SECRET_QUERY_RE.sub(r"\1[REDACTED]", value)
    value = DESKTOP_KEY_PATH_RE.sub("[REDACTED_DESKTOP_SECRET_PATH]", value)
    value = SECRET_RE.sub("[REDACTED]", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in value.splitlines())


def _safe_url(url: str) -> str:
    return SECRET_QUERY_RE.sub(r"\1[REDACTED]", url)


def _content_type_allowed(content_type: str) -> bool:
    base = str(content_type or "").split(";", 1)[0].strip().lower()
    if not base:
        return False
    return any(base == allowed or base.startswith(allowed) for allowed in ALLOWED_DISCOVERY_TEXT_CONTENT_TYPES)


def _source_identity_hash(source: dict[str, Any], fetched: FetchResult, body: bytes) -> str:
    digest = hashlib.sha256(body).hexdigest()
    provider_id = str(source.get("provider_id") or "").strip().lower()
    source_type = str(source.get("source_type") or "").strip().lower()
    return hashlib.sha256(f"{provider_id}|{source_type}|{digest}".encode("utf-8")).hexdigest()


def _normalized_url_identity(url: str) -> str:
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return str(url or "").strip()
    scheme = parsed.scheme.lower()
    host = str(parsed.hostname or "").lower()
    port = parsed.port
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    query = parsed.query or ""
    return f"{scheme}://{netloc}{path}?{query}"


def _is_private_or_local_host(host: str) -> bool:
    lowered = str(host or "").strip().lower()
    if not lowered:
        return True
    if lowered in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return lowered.endswith(".local")
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


def _index_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "provider_id",
            "platform_id",
            "source_id",
            "url",
            "final_url",
            "mode",
            "ok",
            "classification",
            "status_code",
            "content_type",
            "content_encoding",
            "content_length",
            "content_hash",
            "source_identity_hash",
            "content_bytes",
            "body_truncated",
            "excerpt_chars",
            "parser_excerpt_chars",
            "duration_ms",
            "source_type",
            "trust_level",
            "channel",
            "parser_strategy",
            "capability_categories",
            "source_stability",
            "source_role",
            "retrieved_on",
            "discovered_from_source_id",
            "discovery_depth",
            "document_link_title",
            "promotable",
            "requires_manual_review",
            "warnings",
        )
    }


def _discovery_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for record in records:
        classification = str(record.get("classification") or "unknown")
        counts[classification] = counts.get(classification, 0) + 1
    ok_count = sum(1 for record in records if bool(record.get("ok")))
    failed_count = len(records) - ok_count
    status = "pass" if records and failed_count == 0 else "partial" if ok_count else "blocked"
    return {
        "status": status,
        "total_sources": len(records),
        "ok_sources": ok_count,
        "failed_or_skipped_sources": failed_count,
        "classifications": counts,
    }


def _normalize_limits(
    *,
    max_sources: int,
    timeout_sec: int,
    max_bytes_per_source: int,
    max_excerpt_chars: int,
    max_parser_excerpt_chars: int,
) -> dict[str, int]:
    return {
        "max_sources": max(1, min(100, int(max_sources or DEFAULT_DISCOVERY_MAX_SOURCES))),
        "timeout_sec": max(1, min(60, int(timeout_sec or DEFAULT_DISCOVERY_TIMEOUT_SEC))),
        "max_bytes_per_source": max(500, min(1_000_000, int(max_bytes_per_source or DEFAULT_DISCOVERY_MAX_BYTES_PER_SOURCE))),
        "max_excerpt_chars": max(120, min(10_000, int(max_excerpt_chars or DEFAULT_DISCOVERY_MAX_EXCERPT_CHARS))),
        "max_parser_excerpt_chars": max(500, min(60_000, int(max_parser_excerpt_chars or DEFAULT_DISCOVERY_MAX_PARSER_EXCERPT_CHARS))),
    }


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    path.write_text(text, encoding="utf-8", newline="\n")
