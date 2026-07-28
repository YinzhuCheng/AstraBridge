from __future__ import annotations

from copy import deepcopy
from datetime import date
import re
from typing import Any

from ..security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, SecurityError


SOURCE_REGISTRY_SCHEMA_VERSION = "astrabridge-provider-source-registry-v2"
MANAGED_PROVIDER_IDS = ("yunwu", "openai", "deepseek", "kimi", "qwen", "glm")
REFERENCE_PROVIDER_IDS = ("openrouter",)
SOURCE_TYPES = (
    "documentation_index",
    "api_reference",
    "models_catalog",
    "pricing",
    "release_notes",
    "guide",
    "gateway_catalog",
    "screenshot_seed",
)
TRUST_LEVELS = ("official", "first_party_unverified", "screenshot_seed", "untrusted")
CHANNELS = (
    "stable_docs",
    "api_reference",
    "pricing",
    "release_notes",
    "aggregator_gateway",
    "manual_seed",
)
PARSER_STRATEGIES = (
    "llms_index",
    "markdown_document",
    "markdown_table",
    "html_document",
    "html_table",
    "json_api",
    "openapi_or_html",
    "manual_review",
    "manual_screenshot_seed",
)
SOURCE_CAPABILITY_CATEGORIES = (
    "models_catalog",
    "protocol_reference",
    "reasoning",
    "tool_calling",
    "streaming",
    "image_input",
    "image_output",
    "audio_input",
    "audio_output",
    "video_input",
    "context_window",
    "output_limit",
    "pricing",
    "errors_limits",
    "release_notes",
)
SOURCE_STABILITY_LEVELS = ("stable", "versioned", "likely_to_change")
SOURCE_ROLES = ("primary_source", "secondary_context", "mixed")
DEFAULT_SOURCE_RETRIEVED_ON = "2026-07-06"
NON_PROMOTABLE_TRUST_LEVELS = {"screenshot_seed", "untrusted", "first_party_unverified"}
_SECRET_VALUE_RE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+[a-z0-9._~+/=-]{12,}|api[_-]?key\s*[:=]\s*\S+|cookie\s*:|"
    r"token\s*[:=]\s*\S+|ssh-rsa|BEGIN\s+(RSA|OPENSSH|EC|DSA)\s+PRIVATE\s+KEY)"
)


def default_provider_source_registry() -> list[dict[str, Any]]:
    return [normalize_provider_source_record(record) for record in _DEFAULT_PROVIDER_SOURCE_REGISTRY]


def provider_source_registry_schema() -> dict[str, Any]:
    return {
        "schema_version": SOURCE_REGISTRY_SCHEMA_VERSION,
        "managed_provider_ids": list(MANAGED_PROVIDER_IDS),
        "reference_provider_ids": list(REFERENCE_PROVIDER_IDS),
        "source_types": list(SOURCE_TYPES),
        "trust_levels": list(TRUST_LEVELS),
        "channels": list(CHANNELS),
        "parser_strategies": list(PARSER_STRATEGIES),
        "capability_categories": list(SOURCE_CAPABILITY_CATEGORIES),
        "source_stability_levels": list(SOURCE_STABILITY_LEVELS),
        "source_roles": list(SOURCE_ROLES),
        "promotion_rules": {
            "official_sources_can_be_promoted_after_validation": True,
            "untrusted_sources_require_manual_review": True,
            "screenshot_seed_sources_are_non_promotable": True,
            "first_party_unverified_sources_are_non_promotable_until_fetchable": True,
            "secondary_context_sources_are_non_promotable": True,
        },
        "required_provider_fields": [
            "provider_id",
            "display_name",
            "urls",
            "source_status",
            "source_type",
            "trust_level",
            "channel",
            "parser_strategy",
            "stale_after_days",
            "promotion_policy",
            "capability_categories",
            "source_stability",
            "source_role",
            "retrieved_on",
            "source_records",
        ],
        "required_source_record_fields": [
            "source_id",
            "url",
            "source_type",
            "trust_level",
            "channel",
            "parser_strategy",
            "stale_after_days",
            "capability_categories",
            "source_stability",
            "source_role",
            "retrieved_on",
        ],
    }


def normalize_provider_source_record(
    record: dict[str, Any],
    *,
    default_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise TypeError("Provider source record must be a dict.")
    merged = {**(default_record or {}), **record}
    provider_id = _required_string(merged, "provider_id")
    display_name = _required_string(merged, "display_name", default=provider_id)
    source_records = _normalize_source_records(provider_id, merged)
    urls = _dedupe([str(item.get("url") or "").strip() for item in source_records if str(item.get("url") or "").strip()])
    if not urls:
        raise ValueError(f"Provider source registry entry has no URLs: {provider_id}")
    source_type = _enum_value(merged.get("source_type"), SOURCE_TYPES, source_records[0]["source_type"])
    trust_level = _enum_value(merged.get("trust_level"), TRUST_LEVELS, _provider_trust_level(source_records))
    channel = _enum_value(merged.get("channel"), CHANNELS, source_records[0]["channel"])
    parser_strategy = _enum_value(merged.get("parser_strategy"), PARSER_STRATEGIES, source_records[0]["parser_strategy"])
    source_status = str(merged.get("source_status") or _source_status_for_trust(trust_level)).strip() or "seeded"
    stale_after_days = _positive_int(merged.get("stale_after_days"), default=_provider_stale_after_days(source_records))
    promotion_policy = _promotion_policy(provider_id, trust_level, source_status, merged.get("promotion_policy"))
    capability_categories = _provider_capability_categories(source_records)
    source_stability = _provider_source_stability(source_records)
    source_role = _provider_source_role(source_records)
    retrieved_on = _provider_retrieved_on(source_records)
    normalized = {
        "provider_id": provider_id,
        "display_name": display_name,
        "urls": urls,
        "source_status": source_status,
        "source_type": source_type,
        "trust_level": trust_level,
        "channel": channel,
        "parser_strategy": parser_strategy,
        "stale_after_days": stale_after_days,
        "promotion_policy": promotion_policy,
        "capability_categories": capability_categories,
        "source_stability": source_stability,
        "source_role": source_role,
        "retrieved_on": retrieved_on,
        "source_registry_schema": SOURCE_REGISTRY_SCHEMA_VERSION,
        "source_records": source_records,
        "source_provenance": {
            "provider_id": provider_id,
            "source_status": source_status,
            "source_url": urls[0],
            "source_registry_schema": SOURCE_REGISTRY_SCHEMA_VERSION,
            "trust_level": trust_level,
            "channel": channel,
            "parser_strategy": parser_strategy,
            "promotable": bool(promotion_policy.get("promotable")),
            "capability_categories": capability_categories,
            "source_stability": source_stability,
            "source_role": source_role,
            "retrieved_on": retrieved_on,
        },
        "notes": str(merged.get("notes") or "").strip(),
    }
    _reject_secret_like(normalized, path=f"provider_source_registry.{provider_id}")
    return normalized


def normalize_provider_source_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    defaults = {str(item.get("provider_id") or ""): item for item in _DEFAULT_PROVIDER_SOURCE_REGISTRY}
    normalized = []
    seen: set[str] = set()
    for record in records:
        provider_id = str(record.get("provider_id") or "").strip()
        normalized.append(normalize_provider_source_record(record, default_record=defaults.get(provider_id)))
        if provider_id:
            seen.add(provider_id)
    for provider_id in MANAGED_PROVIDER_IDS:
        if provider_id not in seen:
            normalized.append(normalize_provider_source_record(defaults[provider_id]))
    return normalized


def assert_secret_free_provider_source_registry(payload: Any) -> None:
    _reject_secret_like(payload, path="provider_source_registry")


def source_provenance_for_provider_source(source: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_provider_source_record(source)
    return dict(normalized["source_provenance"])


def _normalize_source_records(provider_id: str, merged: dict[str, Any]) -> list[dict[str, Any]]:
    raw_records = list(merged.get("source_records") or [])
    records: list[dict[str, Any]] = []
    if raw_records:
        for index, item in enumerate(raw_records):
            if not isinstance(item, dict):
                raise TypeError(f"source_records[{index}] must be a dict.")
            records.append(_normalize_source_record(provider_id, item, index=index))
    else:
        for index, url in enumerate(list(merged.get("urls") or [])):
            records.append(
                _normalize_source_record(
                    provider_id,
                    {
                        "source_id": f"{provider_id}-manual-{index + 1}",
                        "url": url,
                        "source_type": merged.get("source_type") or "guide",
                        "trust_level": merged.get("trust_level") or "untrusted",
                        "channel": merged.get("channel") or "manual_seed",
                        "parser_strategy": merged.get("parser_strategy") or "manual_review",
                        "stale_after_days": merged.get("stale_after_days") or 30,
                        "notes": "Saved source URL without registry metadata; keep non-promotable until reviewed.",
                    },
                    index=index,
                )
            )
    return records


def _normalize_source_record(provider_id: str, item: dict[str, Any], *, index: int) -> dict[str, Any]:
    url = _required_string(item, "url")
    _validate_public_url(url)
    trust_level = _enum_value(item.get("trust_level"), TRUST_LEVELS, "untrusted")
    source_type = _enum_value(item.get("source_type"), SOURCE_TYPES, "guide")
    channel = _enum_value(item.get("channel"), CHANNELS, "manual_seed")
    parser_strategy = _enum_value(item.get("parser_strategy"), PARSER_STRATEGIES, "manual_review")
    stale_after_days = _positive_int(item.get("stale_after_days"), default=30)
    capability_categories = _normalize_capability_categories(item.get("capability_categories"), source_type=source_type)
    source_stability = _enum_value(item.get("source_stability"), SOURCE_STABILITY_LEVELS, "likely_to_change")
    source_role = _enum_value(item.get("source_role"), SOURCE_ROLES, _default_source_role(trust_level))
    retrieved_on = _iso_date_string(item.get("retrieved_on"), default=DEFAULT_SOURCE_RETRIEVED_ON)
    promotable = bool(item.get("promotable", trust_level == "official"))
    requires_manual_review = bool(item.get("requires_manual_review", trust_level in NON_PROMOTABLE_TRUST_LEVELS))
    platform_id = str(item.get("platform_id") or "").strip()
    if trust_level in NON_PROMOTABLE_TRUST_LEVELS:
        promotable = False
        requires_manual_review = True
    if source_role == "secondary_context":
        promotable = False
    normalized = {
        "source_id": str(item.get("source_id") or f"{provider_id}-source-{index + 1}").strip(),
        "url": url,
        "source_type": source_type,
        "trust_level": trust_level,
        "channel": channel,
        "parser_strategy": parser_strategy,
        "stale_after_days": stale_after_days,
        "capability_categories": capability_categories,
        "source_stability": source_stability,
        "source_role": source_role,
        "retrieved_on": retrieved_on,
        "promotable": promotable,
        "requires_manual_review": requires_manual_review,
        "notes": str(item.get("notes") or "").strip(),
    }
    if platform_id:
        normalized["platform_id"] = platform_id
    if not normalized["source_id"]:
        raise ValueError("source_id must not be empty.")
    _reject_secret_like(normalized, path=f"provider_source_registry.{provider_id}.source_records[{index}]")
    return normalized


def _promotion_policy(provider_id: str, trust_level: str, source_status: str, explicit: Any) -> dict[str, Any]:
    if isinstance(explicit, dict):
        policy = dict(explicit)
    else:
        policy = {}
    if trust_level in NON_PROMOTABLE_TRUST_LEVELS or source_status in {"screenshot_seed", "untrusted", "manual_seed"}:
        return {
            "promotable": False,
            "requires_manual_review": True,
            "reason": policy.get("reason")
            or f"{provider_id} source trust level is {trust_level}; use for discovery only until manually verified.",
        }
    return {
        "promotable": bool(policy.get("promotable", True)),
        "requires_manual_review": bool(policy.get("requires_manual_review", False)),
        "reason": str(policy.get("reason") or "Official source; promotion still requires parser and smoke validation.").strip(),
    }


def _provider_trust_level(source_records: list[dict[str, Any]]) -> str:
    levels = {str(item.get("trust_level") or "") for item in source_records}
    if levels == {"official"}:
        return "official"
    if "screenshot_seed" in levels:
        return "screenshot_seed"
    if "untrusted" in levels:
        return "untrusted"
    return "first_party_unverified"


def _provider_stale_after_days(source_records: list[dict[str, Any]]) -> int:
    values = [int(item.get("stale_after_days") or 0) for item in source_records if int(item.get("stale_after_days") or 0) > 0]
    return min(values) if values else 30


def _provider_capability_categories(source_records: list[dict[str, Any]]) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    for item in source_records:
        for category in list(item.get("capability_categories") or []):
            text = str(category or "").strip()
            if text and text not in seen:
                categories.append(text)
                seen.add(text)
    return categories


def _provider_source_stability(source_records: list[dict[str, Any]]) -> str:
    values = {str(item.get("source_stability") or "likely_to_change") for item in source_records}
    if "likely_to_change" in values:
        return "likely_to_change"
    if "versioned" in values:
        return "versioned"
    return "stable"


def _provider_source_role(source_records: list[dict[str, Any]]) -> str:
    roles = {str(item.get("source_role") or "") for item in source_records}
    if len(roles) == 1:
        return next(iter(roles))
    return "mixed"


def _provider_retrieved_on(source_records: list[dict[str, Any]]) -> str:
    values = [str(item.get("retrieved_on") or "").strip() for item in source_records if str(item.get("retrieved_on") or "").strip()]
    return max(values) if values else DEFAULT_SOURCE_RETRIEVED_ON


def _source_status_for_trust(trust_level: str) -> str:
    if trust_level == "official":
        return "official_docs"
    if trust_level == "screenshot_seed":
        return "screenshot_seed"
    if trust_level == "first_party_unverified":
        return "first_party_unverified"
    return "untrusted"


def _required_string(record: dict[str, Any], field: str, default: str | None = None) -> str:
    value = record.get(field)
    text = str(value if value is not None else default or "").strip()
    if not text:
        raise ValueError(f"Provider source registry entry is missing {field}.")
    return text


def _enum_value(value: Any, allowed: tuple[str, ...], default: str) -> str:
    text = str(value or default).strip()
    if text not in allowed:
        raise ValueError(f"Unsupported provider source registry value: {text}")
    return text


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    if parsed <= 0:
        raise ValueError("stale_after_days must be positive.")
    return parsed


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _normalize_capability_categories(value: Any, *, source_type: str) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    elif value is None:
        raw = []
    else:
        raw = [value]
    if not raw:
        raw = _default_capability_categories_for_source_type(source_type)
    categories = []
    seen: set[str] = set()
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        if text not in SOURCE_CAPABILITY_CATEGORIES:
            raise ValueError(f"Unsupported capability category: {text}")
        if text not in seen:
            categories.append(text)
            seen.add(text)
    if not categories:
        raise ValueError("capability_categories must not be empty.")
    return categories


def _default_capability_categories_for_source_type(source_type: str) -> list[str]:
    defaults = {
        "api_reference": ["protocol_reference"],
        "models_catalog": ["models_catalog"],
        "pricing": ["pricing"],
        "release_notes": ["release_notes"],
        "guide": ["protocol_reference"],
        "gateway_catalog": ["models_catalog", "protocol_reference"],
        "screenshot_seed": ["models_catalog"],
    }
    return list(defaults.get(source_type, ["protocol_reference"]))


def _default_source_role(trust_level: str) -> str:
    if trust_level == "official":
        return "primary_source"
    return "secondary_context"


def _iso_date_string(value: Any, *, default: str) -> str:
    text = str(value if value is not None else default).strip() or default
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"Invalid ISO date in provider source registry: {text}") from exc


def _validate_public_url(url: str) -> None:
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"Provider source URL must be HTTP(S): {url}")
    if DESKTOP_KEY_PATH_RE.search(url) or SECRET_QUERY_RE.search(url) or _SECRET_VALUE_RE.search(url):
        raise SecurityError("Provider source URL contains secret-like content.")


def _reject_secret_like(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("api_key", "apikey", "authorization", "cookie", "password", "secret", "token")):
                if item not in (None, "", "[redacted]"):
                    raise SecurityError(f"Forbidden secret-bearing field in provider source registry: {path}.{key}")
            _reject_secret_like(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_like(item, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if DESKTOP_KEY_PATH_RE.search(value) or SECRET_QUERY_RE.search(value) or _SECRET_VALUE_RE.search(value):
        raise SecurityError(f"Secret-like value is not allowed in provider source registry: {path}")


def _source_record(
    source_id: str,
    url: str,
    *,
    source_type: str,
    capability_categories: list[str],
    trust_level: str = "official",
    channel: str = "stable_docs",
    parser_strategy: str = "html_document",
    stale_after_days: int = 14,
    source_stability: str = "stable",
    source_role: str | None = None,
    retrieved_on: str = DEFAULT_SOURCE_RETRIEVED_ON,
    notes: str = "",
    platform_id: str | None = None,
) -> dict[str, Any]:
    record = {
        "source_id": source_id,
        "url": url,
        "source_type": source_type,
        "trust_level": trust_level,
        "channel": channel,
        "parser_strategy": parser_strategy,
        "stale_after_days": stale_after_days,
        "capability_categories": capability_categories,
        "source_stability": source_stability,
        "source_role": source_role or _default_source_role(trust_level),
        "retrieved_on": retrieved_on,
        "notes": notes,
    }
    if platform_id:
        record["platform_id"] = platform_id
    return record


_DEFAULT_PROVIDER_SOURCE_REGISTRY: list[dict[str, Any]] = [
    {
        "provider_id": "yunwu",
        "display_name": "Yunwu",
        "source_status": "screenshot_seed",
        "source_type": "gateway_catalog",
        "trust_level": "screenshot_seed",
        "channel": "aggregator_gateway",
        "parser_strategy": "manual_screenshot_seed",
        "stale_after_days": 14,
        "promotion_policy": {
            "promotable": False,
            "requires_manual_review": True,
            "reason": "Yunwu model availability remains a gateway source pack seeded from first-party and screenshot-observed pages; keep as secondary context until fetchable parser and provider-backed validation exist.",
        },
        "notes": "Use Yunwu sources as OpenAI-compatible gateway context only. Do not promote model or capability claims without separate runtime validation.",
        "source_records": [
            _source_record(
                "yunwu-home",
                "https://yunwu.ai/",
                source_type="guide",
                trust_level="first_party_unverified",
                channel="stable_docs",
                parser_strategy="manual_review",
                stale_after_days=14,
                capability_categories=["models_catalog", "protocol_reference"],
                source_stability="likely_to_change",
                source_role="secondary_context",
                notes="First-party product site; useful for gateway positioning but still secondary context for concrete API capability claims.",
            ),
            _source_record(
                "yunwu-codex-pricing",
                "https://yunwu.ai/pricing?group=Codex%E4%B8%93%E5%B1%9E",
                source_type="pricing",
                trust_level="first_party_unverified",
                channel="pricing",
                parser_strategy="manual_review",
                stale_after_days=7,
                capability_categories=["pricing"],
                source_stability="likely_to_change",
                source_role="secondary_context",
                notes="Gateway pricing surface only; not sufficient for capability promotion.",
            ),
            _source_record(
                "yunwu-apifox-models",
                "https://yunwu.apifox.cn/api-232421952",
                source_type="api_reference",
                trust_level="screenshot_seed",
                channel="manual_seed",
                parser_strategy="manual_screenshot_seed",
                stale_after_days=14,
                capability_categories=["models_catalog", "protocol_reference"],
                source_stability="likely_to_change",
                source_role="secondary_context",
                notes="Apifox model-list seed observed in prior screenshots.",
            ),
            _source_record(
                "yunwu-apifox-responses",
                "https://yunwu.apifox.cn/api-425475208",
                source_type="api_reference",
                trust_level="screenshot_seed",
                channel="manual_seed",
                parser_strategy="manual_screenshot_seed",
                stale_after_days=14,
                capability_categories=["protocol_reference", "tool_calling", "streaming", "reasoning"],
                source_stability="likely_to_change",
                source_role="secondary_context",
                notes="Responses-compatible API surface seed.",
            ),
            _source_record(
                "yunwu-apifox-images",
                "https://yunwu.apifox.cn/api-425481728",
                source_type="api_reference",
                trust_level="screenshot_seed",
                channel="manual_seed",
                parser_strategy="manual_screenshot_seed",
                stale_after_days=14,
                capability_categories=["image_output", "protocol_reference"],
                source_stability="likely_to_change",
                source_role="secondary_context",
                notes="Image-generation API surface seed.",
            ),
        ],
    },
    {
        "provider_id": "openai",
        "display_name": "OpenAI",
        "source_status": "official_docs",
        "source_type": "models_catalog",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": "html_document",
        "stale_after_days": 7,
        "notes": "OpenAI remains a normal API-key provider only. The registry uses official API docs as the primary protocol reference.",
        "source_records": [
            _source_record(
                "openai-models",
                "https://developers.openai.com/api/docs/models",
                source_type="models_catalog",
                capability_categories=["models_catalog", "context_window", "output_limit"],
                stale_after_days=7,
            ),
            _source_record(
                "openai-responses-overview",
                "https://developers.openai.com/api/reference/responses/overview/",
                source_type="api_reference",
                channel="api_reference",
                capability_categories=["protocol_reference", "tool_calling", "streaming", "image_input"],
            ),
            _source_record(
                "openai-function-calling",
                "https://developers.openai.com/api/docs/guides/function-calling",
                source_type="guide",
                capability_categories=["tool_calling", "protocol_reference"],
            ),
            _source_record(
                "openai-reasoning",
                "https://developers.openai.com/api/docs/guides/reasoning",
                source_type="guide",
                capability_categories=["reasoning", "output_limit"],
            ),
            _source_record(
                "openai-images-vision",
                "https://developers.openai.com/api/docs/guides/images-vision",
                source_type="guide",
                capability_categories=["image_input", "image_output"],
            ),
            _source_record(
                "openai-streaming-responses",
                "https://developers.openai.com/api/docs/guides/streaming-responses",
                source_type="guide",
                capability_categories=["streaming", "protocol_reference"],
            ),
            _source_record(
                "openai-rate-limits",
                "https://developers.openai.com/api/docs/guides/rate-limits",
                source_type="guide",
                capability_categories=["errors_limits", "output_limit"],
            ),
            _source_record(
                "openai-error-codes",
                "https://developers.openai.com/api/docs/guides/error-codes",
                source_type="guide",
                capability_categories=["errors_limits"],
            ),
            _source_record(
                "openai-pricing",
                "https://developers.openai.com/api/docs/pricing",
                source_type="pricing",
                channel="pricing",
                parser_strategy="html_table",
                stale_after_days=7,
                capability_categories=["pricing"],
            ),
        ],
    },
    {
        "provider_id": "deepseek",
        "display_name": "DeepSeek",
        "source_status": "official_docs",
        "source_type": "models_catalog",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": "html_document",
        "stale_after_days": 7,
        "notes": "Use DeepSeek official docs for models, tool calls, thinking mode, rate limits, and error behavior.",
        "source_records": [
            _source_record(
                "deepseek-list-models",
                "https://api-docs.deepseek.com/api/list-models/",
                source_type="models_catalog",
                channel="api_reference",
                capability_categories=["models_catalog"],
                stale_after_days=7,
            ),
            _source_record(
                "deepseek-models-pricing",
                "https://api-docs.deepseek.com/quick_start/pricing/",
                source_type="pricing",
                channel="pricing",
                parser_strategy="html_table",
                stale_after_days=7,
                capability_categories=["pricing", "models_catalog"],
            ),
            _source_record(
                "deepseek-chat-completion",
                "https://api-docs.deepseek.com/api/create-chat-completion/",
                source_type="api_reference",
                channel="api_reference",
                capability_categories=["protocol_reference", "streaming", "tool_calling"],
            ),
            _source_record(
                "deepseek-thinking-mode",
                "https://api-docs.deepseek.com/guides/thinking_mode/",
                source_type="guide",
                capability_categories=["reasoning", "tool_calling", "streaming"],
            ),
            _source_record(
                "deepseek-tool-calls",
                "https://api-docs.deepseek.com/guides/tool_calls/",
                source_type="guide",
                capability_categories=["tool_calling", "protocol_reference"],
            ),
            _source_record(
                "deepseek-rate-limit",
                "https://api-docs.deepseek.com/quick_start/rate_limit/",
                source_type="guide",
                capability_categories=["errors_limits", "output_limit"],
            ),
            _source_record(
                "deepseek-error-codes",
                "https://api-docs.deepseek.com/quick_start/error_codes/",
                source_type="guide",
                capability_categories=["errors_limits"],
            ),
        ],
    },
    {
        "provider_id": "kimi",
        "display_name": "Kimi",
        "source_status": "official_docs",
        "source_type": "models_catalog",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": "llms_index",
        "stale_after_days": 7,
        "notes": "Use both official Kimi platform documentation scopes. platform.kimi.com maps to api.moonshot.cn and platform.kimi.ai maps to api.moonshot.ai; credentials must never be moved across those independent scopes.",
        "source_records": [
            _source_record(
                "kimi-llms-index",
                "https://platform.kimi.com/docs/llms.txt",
                platform_id="platform.kimi.com",
                source_type="documentation_index",
                parser_strategy="llms_index",
                capability_categories=[
                    "models_catalog",
                    "context_window",
                    "reasoning",
                    "tool_calling",
                    "image_input",
                    "video_input",
                    "pricing",
                    "release_notes",
                ],
                stale_after_days=1,
                source_stability="likely_to_change",
                notes="Official machine-readable documentation index. Discovery may follow only bounded same-origin Markdown links selected by update relevance.",
            ),
            _source_record(
                "kimi-models-markdown",
                "https://platform.kimi.com/docs/models.md",
                platform_id="platform.kimi.com",
                source_type="models_catalog",
                parser_strategy="markdown_table",
                capability_categories=["models_catalog", "context_window", "image_input", "video_input", "reasoning"],
                stale_after_days=1,
            ),
            _source_record(
                "kimi-chat-api-markdown",
                "https://platform.kimi.com/docs/api/chat.md",
                platform_id="platform.kimi.com",
                source_type="api_reference",
                channel="api_reference",
                parser_strategy="markdown_document",
                capability_categories=["protocol_reference", "tool_calling", "streaming"],
            ),
            _source_record(
                "kimi-model-parameters-markdown",
                "https://platform.kimi.com/docs/api/models-overview.md",
                platform_id="platform.kimi.com",
                source_type="api_reference",
                channel="api_reference",
                parser_strategy="markdown_table",
                capability_categories=["models_catalog", "protocol_reference", "reasoning", "output_limit"],
            ),
            _source_record(
                "kimi-pricing-index-markdown",
                "https://platform.kimi.com/docs/pricing/chat.md",
                platform_id="platform.kimi.com",
                source_type="pricing",
                channel="pricing",
                parser_strategy="markdown_document",
                stale_after_days=7,
                capability_categories=["pricing", "models_catalog"],
            ),
            _source_record(
                "kimi-ai-llms-index",
                "https://platform.kimi.ai/docs/llms.txt",
                platform_id="platform.kimi.ai",
                source_type="documentation_index",
                parser_strategy="llms_index",
                capability_categories=[
                    "models_catalog",
                    "context_window",
                    "reasoning",
                    "tool_calling",
                    "image_input",
                    "video_input",
                    "pricing",
                    "release_notes",
                ],
                stale_after_days=1,
                source_stability="likely_to_change",
                notes="Official international-platform documentation index; credentials are scoped to platform.kimi.ai.",
            ),
            _source_record(
                "kimi-ai-models-markdown",
                "https://platform.kimi.ai/docs/models.md",
                platform_id="platform.kimi.ai",
                source_type="models_catalog",
                parser_strategy="markdown_table",
                capability_categories=["models_catalog", "context_window", "image_input", "video_input", "reasoning"],
                stale_after_days=1,
            ),
            _source_record(
                "kimi-ai-chat-api-markdown",
                "https://platform.kimi.ai/docs/api/chat.md",
                platform_id="platform.kimi.ai",
                source_type="api_reference",
                channel="api_reference",
                parser_strategy="markdown_document",
                capability_categories=["protocol_reference", "tool_calling", "streaming"],
            ),
            _source_record(
                "kimi-ai-model-parameters-markdown",
                "https://platform.kimi.ai/docs/api/models-overview.md",
                platform_id="platform.kimi.ai",
                source_type="api_reference",
                channel="api_reference",
                parser_strategy="markdown_table",
                capability_categories=["models_catalog", "protocol_reference", "reasoning", "output_limit"],
            ),
            _source_record(
                "kimi-ai-pricing-index-markdown",
                "https://platform.kimi.ai/docs/pricing/chat.md",
                platform_id="platform.kimi.ai",
                source_type="pricing",
                channel="pricing",
                parser_strategy="markdown_document",
                stale_after_days=7,
                capability_categories=["pricing", "models_catalog"],
            ),
        ],
    },
    {
        "provider_id": "qwen",
        "display_name": "Qwen / DashScope",
        "source_status": "official_docs",
        "source_type": "models_catalog",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": "html_table",
        "stale_after_days": 7,
        "notes": "Alibaba Cloud Model Studio docs are the primary source for Qwen models, OpenAI-compatible endpoints, multimodal guides, and limit pages.",
        "source_records": [
            _source_record(
                "qwen-models",
                "https://help.aliyun.com/zh/model-studio/models",
                source_type="models_catalog",
                parser_strategy="html_table",
                stale_after_days=7,
                capability_categories=["models_catalog", "context_window", "output_limit"],
            ),
            _source_record(
                "qwen-release-notes",
                "https://help.aliyun.com/zh/model-studio/newly-released-models",
                source_type="release_notes",
                channel="release_notes",
                parser_strategy="html_document",
                stale_after_days=7,
                capability_categories=["release_notes"],
                source_stability="likely_to_change",
            ),
            _source_record(
                "qwen-openai-chat-compat",
                "https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["protocol_reference", "streaming"],
            ),
            _source_record(
                "qwen-openai-responses-compat",
                "https://help.aliyun.com/zh/model-studio/compatibility-with-openai-responses-api",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["protocol_reference", "tool_calling", "streaming", "reasoning"],
            ),
            _source_record(
                "qwen-text-generation",
                "https://help.aliyun.com/zh/model-studio/text-generation-model/",
                source_type="api_reference",
                parser_strategy="html_table",
                capability_categories=["protocol_reference", "reasoning", "streaming"],
            ),
            _source_record(
                "qwen-function-calling",
                "https://help.aliyun.com/zh/model-studio/qwen-function-calling",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["tool_calling"],
            ),
            _source_record(
                "qwen-vision",
                "https://help.aliyun.com/zh/model-studio/vision",
                source_type="api_reference",
                parser_strategy="html_table",
                capability_categories=["image_input", "video_input", "output_limit"],
            ),
            _source_record(
                "qwen-text-to-image",
                "https://help.aliyun.com/zh/model-studio/text-to-image",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["image_output", "models_catalog"],
            ),
            _source_record(
                "qwen-image-model",
                "https://help.aliyun.com/zh/model-studio/image-model/",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["image_output", "models_catalog", "output_limit"],
            ),
            _source_record(
                "qwen-image-api",
                "https://help.aliyun.com/zh/model-studio/qwen-image-api",
                source_type="api_reference",
                parser_strategy="html_document",
                capability_categories=["image_output", "protocol_reference", "output_limit"],
            ),
            _source_record(
                "qwen-asr",
                "https://help.aliyun.com/zh/model-studio/asr-model/",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["audio_input", "streaming"],
            ),
            _source_record(
                "qwen-tts-api",
                "https://help.aliyun.com/zh/model-studio/qwen-tts-api",
                source_type="api_reference",
                parser_strategy="html_document",
                capability_categories=["audio_output", "output_limit", "protocol_reference"],
            ),
            _source_record(
                "qwen-non-realtime-tts",
                "https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["audio_output", "streaming", "protocol_reference", "models_catalog"],
            ),
            _source_record(
                "cosyvoice-tts-http-api",
                "https://help.aliyun.com/zh/model-studio/cosyvoice-tts-http-api",
                source_type="api_reference",
                parser_strategy="html_document",
                capability_categories=["audio_output", "streaming", "protocol_reference", "models_catalog"],
            ),
            _source_record(
                "qwen-tts-realtime",
                "https://help.aliyun.com/zh/model-studio/qwen-tts-realtime-api-reference/",
                source_type="api_reference",
                parser_strategy="html_document",
                capability_categories=["audio_output", "streaming", "protocol_reference"],
            ),
            _source_record(
                "qwen-error-code",
                "https://help.aliyun.com/zh/model-studio/error-code",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["errors_limits"],
            ),
            _source_record(
                "qwen-rate-limit",
                "https://help.aliyun.com/zh/model-studio/rate-limit",
                source_type="guide",
                parser_strategy="html_document",
                capability_categories=["errors_limits", "output_limit"],
            ),
            _source_record(
                "qwen-product-billing",
                "https://help.aliyun.com/zh/model-studio/product-billing",
                source_type="pricing",
                channel="pricing",
                parser_strategy="html_document",
                stale_after_days=7,
                capability_categories=["pricing"],
            ),
        ],
    },
    {
        "provider_id": "glm",
        "display_name": "GLM / Z.AI",
        "source_status": "official_docs",
        "source_type": "models_catalog",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": "llms_index",
        "stale_after_days": 7,
        "notes": "Use Z.AI docs as the primary source for GLM 5.x model behavior, reasoning controls, tool calls, streaming, and pricing.",
        "source_records": [
            _source_record(
                "glm-llms-index",
                "https://docs.z.ai/llms.txt",
                source_type="documentation_index",
                parser_strategy="llms_index",
                capability_categories=["models_catalog", "context_window", "reasoning", "tool_calling", "pricing"],
                stale_after_days=1,
                source_stability="likely_to_change",
                notes="Official machine-readable Z.AI documentation index. Follow only bounded same-origin Markdown links.",
            ),
            _source_record(
                "glm-5-2",
                "https://docs.z.ai/guides/llm/glm-5.2.md",
                source_type="models_catalog",
                parser_strategy="markdown_document",
                capability_categories=["models_catalog", "context_window", "reasoning", "tool_calling", "streaming"],
                stale_after_days=7,
                source_stability="versioned",
            ),
            _source_record(
                "glm-chat-completion",
                "https://docs.z.ai/api-reference/llm/chat-completion.md",
                source_type="api_reference",
                channel="api_reference",
                parser_strategy="markdown_document",
                capability_categories=["protocol_reference", "tool_calling", "streaming", "image_input", "audio_input", "video_input", "output_limit"],
            ),
            _source_record(
                "glm-core-parameters",
                "https://docs.z.ai/guides/overview/concept-param.md",
                source_type="guide",
                parser_strategy="markdown_document",
                capability_categories=["reasoning", "streaming", "output_limit", "context_window"],
            ),
            _source_record(
                "glm-function-calling",
                "https://docs.z.ai/guides/capabilities/function-calling.md",
                source_type="guide",
                parser_strategy="markdown_document",
                capability_categories=["tool_calling"],
            ),
            _source_record(
                "glm-streaming",
                "https://docs.z.ai/guides/capabilities/streaming.md",
                source_type="guide",
                parser_strategy="markdown_document",
                capability_categories=["streaming"],
            ),
            _source_record(
                "glm-stream-tool",
                "https://docs.z.ai/guides/tools/stream-tool.md",
                source_type="guide",
                parser_strategy="markdown_document",
                capability_categories=["tool_calling", "streaming"],
            ),
            _source_record(
                "glm-thinking-mode",
                "https://docs.z.ai/guides/capabilities/thinking-mode.md",
                source_type="guide",
                parser_strategy="markdown_document",
                capability_categories=["reasoning", "tool_calling"],
            ),
            _source_record(
                "glm-api-code",
                "https://docs.z.ai/api-reference/api-code.md",
                source_type="guide",
                parser_strategy="markdown_document",
                capability_categories=["errors_limits"],
            ),
            _source_record(
                "glm-pricing",
                "https://docs.z.ai/guides/overview/pricing.md",
                source_type="pricing",
                channel="pricing",
                parser_strategy="markdown_table",
                stale_after_days=7,
                capability_categories=["pricing"],
            ),
        ],
    },
    {
        "provider_id": "openrouter",
        "display_name": "OpenRouter (Reasoning Reference)",
        "source_status": "secondary_context",
        "source_type": "guide",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": "html_document",
        "stale_after_days": 7,
        "promotion_policy": {
            "promotable": False,
            "requires_manual_review": True,
            "reason": "OpenRouter is a secondary design reference for reasoning-effort normalization, not a source of truth for provider capability promotion.",
        },
        "notes": "Keep OpenRouter as secondary context for reasoning abstraction and API-shape comparison only.",
        "source_records": [
            _source_record(
                "openrouter-reasoning-tokens",
                "https://openrouter.ai/docs/guides/best-practices/reasoning-tokens",
                source_type="guide",
                capability_categories=["reasoning", "output_limit", "streaming"],
                source_role="secondary_context",
            ),
            _source_record(
                "openrouter-parameters",
                "https://openrouter.ai/docs/api-reference/parameters",
                source_type="api_reference",
                channel="api_reference",
                capability_categories=["reasoning", "tool_calling", "streaming", "output_limit", "protocol_reference"],
                source_role="secondary_context",
            ),
        ],
    },
]
