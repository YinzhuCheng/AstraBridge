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
from urllib.parse import urlsplit

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
    seen_urls: set[str] = set()
    seen_source_identity_hashes: set[str] = set()
    active_fetcher = fetcher or _default_fetch
    for source in source_records:
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
            pack_records.append(_dedupe_source_identity(record, seen_source_identity_hashes))
            continue
        try:
            fetched = active_fetcher(url, limits["timeout_sec"], limits["max_bytes_per_source"])
            record = _result_record_from_fetch(source, fetched, mode=mode, limits=limits)
            pack_records.append(_dedupe_source_identity(record, seen_source_identity_hashes))
        except Exception as exc:  # noqa: BLE001
            pack_records.append(_discovery_error_record(source, exc))
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
    parser_excerpt = _safe_parser_excerpt(text, limits["max_parser_excerpt_chars"])
    status_code = _optional_int(fetched.get("status_code"))
    ok = bool(status_code is None or 200 <= status_code < 400) and not bool(fetched.get("http_error"))
    classification = "ok" if ok else "http_error"
    record = {
        "schema_version": AGENTIC_UPDATE_DISCOVERY_SCHEMA_VERSION,
        "provider_id": source.get("provider_id"),
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


def _safe_parser_excerpt(text: str, max_chars: int) -> str:
    value = _sanitize_text_for_artifact(text)
    stripped = value.lstrip()
    if stripped.startswith(("{", "[")):
        return value[:max_chars].rstrip() + ("\n[truncated]" if len(value) > max_chars else "")
    modelish = re.compile(
        r"(?i)\b(?:qwen|deepseek|kimi|moonshot|glm|gpt|o[0-9])[-a-z0-9._]*\b"
    )
    snippets: list[str] = []
    seen: set[str] = set()
    for match in modelish.finditer(value):
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
