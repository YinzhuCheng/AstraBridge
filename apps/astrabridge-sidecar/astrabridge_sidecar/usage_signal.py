from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


USAGE_SIGNAL_SCHEMA_VERSION = "astrabridge-usage-signal-v1"


def normalize_usage_signal(
    *,
    source: str,
    provider_id: Any = None,
    model: Any = None,
    usage: Any = None,
    pricing: dict[str, Any] | None = None,
    reason: str | None = None,
    request_kind: str | None = None,
) -> dict[str, Any]:
    tokens = _token_counts(usage)
    has_usage = any(value is not None for value in tokens.values())
    normalized_reason = reason or ("" if has_usage else "usage_not_reported")
    signal = {
        "schema_version": USAGE_SIGNAL_SCHEMA_VERSION,
        "source": str(source or "unknown"),
        "status": "available" if has_usage else "not_available",
        "reason": normalized_reason or None,
        "provider_id": str(provider_id or "").strip() or None,
        "model": str(model or "").strip() or None,
        "request_kind": str(request_kind or "").strip() or None,
        "tokens": tokens,
        "cost": _cost_signal(tokens, pricing or {}, usage_available=has_usage),
    }
    return {key: value for key, value in signal.items() if value is not None}


def usage_not_available(
    *,
    source: str,
    reason: str,
    provider_id: Any = None,
    model: Any = None,
    request_kind: str | None = None,
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return normalize_usage_signal(
        source=source,
        provider_id=provider_id,
        model=model,
        pricing=pricing,
        reason=reason,
        request_kind=request_kind,
    )


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _token_counts(usage: Any) -> dict[str, int | None]:
    raw = _plain(usage)
    if not isinstance(raw, dict):
        return _empty_tokens()
    total = dict(raw.get("total") or {})
    last = dict(raw.get("last") or {})
    completion_details = dict(raw.get("completion_tokens_details") or raw.get("output_tokens_details") or {})
    prompt_details = dict(raw.get("prompt_tokens_details") or raw.get("input_tokens_details") or {})
    return {
        "input_tokens": _optional_int(
            raw.get("input_tokens"),
            raw.get("prompt_tokens"),
            last.get("inputTokens"),
            prompt_details.get("cached_tokens"),
        ),
        "output_tokens": _optional_int(raw.get("output_tokens"), raw.get("completion_tokens"), last.get("outputTokens")),
        "reasoning_tokens": _optional_int(
            raw.get("reasoning_tokens"),
            completion_details.get("reasoning_tokens"),
            raw.get("output_tokens_details", {}).get("reasoning_tokens") if isinstance(raw.get("output_tokens_details"), dict) else None,
        ),
        "cached_input_tokens": _optional_int(raw.get("cached_input_tokens"), prompt_details.get("cached_tokens")),
        "total_tokens": _optional_int(raw.get("total_tokens"), raw.get("totalTokens"), total.get("totalTokens"), last.get("totalTokens")),
    }


def _empty_tokens() -> dict[str, int | None]:
    return {
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "cached_input_tokens": None,
        "total_tokens": None,
    }


def _optional_int(*values: Any) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cost_signal(tokens: dict[str, int | None], pricing: dict[str, Any], *, usage_available: bool) -> dict[str, Any]:
    currency = str(pricing.get("pricing_currency") or pricing.get("currency") or "").strip()
    input_price = _optional_float(pricing.get("pricing_input_per_mtok") or pricing.get("input_per_mtok"))
    output_price = _optional_float(pricing.get("pricing_output_per_mtok") or pricing.get("output_per_mtok"))
    cached_price = _optional_float(pricing.get("pricing_cached_input_per_mtok") or pricing.get("cached_input_per_mtok"))
    source_url = str(pricing.get("pricing_source_url") or pricing.get("source_url") or "").strip()
    pricing_status = str(pricing.get("pricing_status") or pricing.get("status") or "").strip()
    if not usage_available:
        return {
            "status": "not_available",
            "reason": "usage_not_available",
            "currency": currency or None,
            "pricing_status": pricing_status or "unknown",
            "source_url_present": bool(source_url),
        }
    if input_price is None and output_price is None and cached_price is None:
        return {
            "status": "not_available",
            "reason": "pricing_not_configured",
            "currency": currency or None,
            "pricing_status": pricing_status or "unknown",
            "source_url_present": bool(source_url),
        }
    input_tokens = tokens.get("input_tokens") or 0
    output_tokens = tokens.get("output_tokens") or 0
    cached_tokens = tokens.get("cached_input_tokens") or 0
    input_cost = (input_tokens / 1_000_000) * input_price if input_price is not None else None
    output_cost = (output_tokens / 1_000_000) * output_price if output_price is not None else None
    cached_cost = (cached_tokens / 1_000_000) * cached_price if cached_price is not None else None
    total = sum(value for value in (input_cost, output_cost, cached_cost) if value is not None)
    return {
        "status": "estimated",
        "currency": currency or None,
        "input_cost": _round_cost(input_cost),
        "output_cost": _round_cost(output_cost),
        "cached_input_cost": _round_cost(cached_cost),
        "total_cost": _round_cost(total),
        "pricing_status": pricing_status or "unknown",
        "source_url_present": bool(source_url),
    }


def _round_cost(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 8)
