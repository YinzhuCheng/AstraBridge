from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit


KIMI_PLATFORM_CHINA = "platform.kimi.com"
KIMI_PLATFORM_INTERNATIONAL = "platform.kimi.ai"

KIMI_PLATFORM_BINDINGS: dict[str, dict[str, str]] = {
    KIMI_PLATFORM_CHINA: {
        "platform_id": KIMI_PLATFORM_CHINA,
        "display_name": "Kimi API China",
        "api_base_url": "https://api.moonshot.cn/v1",
        "models_url": "https://api.moonshot.cn/v1/models",
        "docs_base_url": "https://platform.kimi.com/docs",
        "docs_index_url": "https://platform.kimi.com/docs/llms.txt",
        "credential_scope": KIMI_PLATFORM_CHINA,
    },
    KIMI_PLATFORM_INTERNATIONAL: {
        "platform_id": KIMI_PLATFORM_INTERNATIONAL,
        "display_name": "Kimi API International",
        "api_base_url": "https://api.moonshot.ai/v1",
        "models_url": "https://api.moonshot.ai/v1/models",
        "docs_base_url": "https://platform.kimi.ai/docs",
        "docs_index_url": "https://platform.kimi.ai/docs/llms.txt",
        "credential_scope": KIMI_PLATFORM_INTERNATIONAL,
    },
}

_KIMI_PLATFORM_ALIASES = {
    "china": KIMI_PLATFORM_CHINA,
    "cn": KIMI_PLATFORM_CHINA,
    "kimi.com": KIMI_PLATFORM_CHINA,
    "platform.kimi.com": KIMI_PLATFORM_CHINA,
    "api.moonshot.cn": KIMI_PLATFORM_CHINA,
    "international": KIMI_PLATFORM_INTERNATIONAL,
    "global": KIMI_PLATFORM_INTERNATIONAL,
    "ai": KIMI_PLATFORM_INTERNATIONAL,
    "kimi.ai": KIMI_PLATFORM_INTERNATIONAL,
    "platform.kimi.ai": KIMI_PLATFORM_INTERNATIONAL,
    "api.moonshot.ai": KIMI_PLATFORM_INTERNATIONAL,
}


def normalize_kimi_platform_id(value: Any) -> str | None:
    text = str(value or "").strip().lower().rstrip("/")
    if not text:
        return None
    if text in KIMI_PLATFORM_BINDINGS:
        return text
    if text in _KIMI_PLATFORM_ALIASES:
        return _KIMI_PLATFORM_ALIASES[text]
    try:
        host = str(urlsplit(text if "://" in text else f"https://{text}").hostname or "").lower()
    except ValueError:
        return None
    return _KIMI_PLATFORM_ALIASES.get(host)


def kimi_platform_for_base_url(base_url: Any) -> str | None:
    return normalize_kimi_platform_id(base_url)


def kimi_platform_binding(platform_id: Any) -> dict[str, str] | None:
    normalized = normalize_kimi_platform_id(platform_id)
    if not normalized:
        return None
    return dict(KIMI_PLATFORM_BINDINGS[normalized])


def kimi_endpoint_variants() -> list[dict[str, str]]:
    return [dict(KIMI_PLATFORM_BINDINGS[platform_id]) for platform_id in (KIMI_PLATFORM_CHINA, KIMI_PLATFORM_INTERNATIONAL)]


__all__ = [
    "KIMI_PLATFORM_BINDINGS",
    "KIMI_PLATFORM_CHINA",
    "KIMI_PLATFORM_INTERNATIONAL",
    "kimi_endpoint_variants",
    "kimi_platform_binding",
    "kimi_platform_for_base_url",
    "normalize_kimi_platform_id",
]
