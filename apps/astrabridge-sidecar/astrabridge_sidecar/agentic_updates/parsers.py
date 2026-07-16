from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..common import now_iso, write_json
from .artifacts import ensure_agentic_update_run_layout
from .contracts import assert_secret_free_agentic_update_payload


AGENTIC_UPDATE_PARSER_OUTPUT_SCHEMA_VERSION = "astrabridge-agentic-update-parser-output-v1"
SUPPORTED_PROVIDER_PARSER_IDS = ("qwen", "deepseek", "kimi", "glm", "openai", "yunwu")
GENERIC_PARSER_ID = "generic_conservative_v1"
QWEN_OFFICIAL_DOCS_PARSER_ID = "qwen_official_docs_conservative_v1"
_KNOWN_MODEL_FIELDS = {
    "id",
    "model_id",
    "native_model",
    "model",
    "display_name",
    "name",
    "context_window",
    "advertised_context_window",
    "modalities",
    "input_modalities",
    "reasoning_modes",
    "supported_reasoning_levels",
    "default_reasoning_level",
    "pricing",
    "pricing_input_per_mtok",
    "pricing_output_per_mtok",
    "deprecated",
    "deprecated_after",
    "default_for_provider",
    "recommended",
    "confidence",
    "tool_support",
    "supports_tool_calls",
    "web_search",
    "supports_web_search",
    "vision",
    "supports_vision",
    "audio",
    "supports_audio",
    "apply_patch",
    "supports_apply_patch",
    "qwen_parser_evidence",
}


def provider_parser_stubs() -> dict[str, dict[str, Any]]:
    stubs = {
        provider_id: {
            "provider_id": provider_id,
            "parser_id": f"{provider_id}_stub_conservative_v1",
            "implementation": GENERIC_PARSER_ID,
            "status": "stub_uses_generic_parser",
            "notes": "Provider-specific parser is intentionally conservative until official source fixtures and validation gates mature.",
        }
        for provider_id in SUPPORTED_PROVIDER_PARSER_IDS
    }
    stubs["qwen"] = {
        "provider_id": "qwen",
        "parser_id": QWEN_OFFICIAL_DOCS_PARSER_ID,
        "implementation": QWEN_OFFICIAL_DOCS_PARSER_ID,
        "status": "provider_specific_parser",
        "notes": "Extracts conservative Qwen model-id candidates from official Model Studio HTML parser excerpts; metadata remains unverified until smoke validation.",
    }
    return stubs


def parse_agentic_update_source_pack(
    *,
    workspace_root: str | Path,
    run_id: str,
    source_pack_path: str | Path | None = None,
    source_records: list[dict[str, Any]] | None = None,
    parser_id: str = GENERIC_PARSER_ID,
) -> dict[str, Any]:
    layout = ensure_agentic_update_run_layout(workspace_root, run_id)
    pack_path = Path(source_pack_path) if source_pack_path is not None else Path(layout["files"]["source_pack"])
    records = [dict(item) for item in source_records] if source_records is not None else _read_source_pack(pack_path)
    proposals: list[dict[str, Any]] = []
    warnings: list[str] = []
    for source_index, record in enumerate(records):
        if not bool(record.get("ok")):
            warnings.append(f"source_skipped:{record.get('provider_id') or 'unknown'}:{record.get('classification') or 'unknown'}")
            continue
        extracted, extract_warnings = _extract_models_from_source(record)
        warnings.extend(extract_warnings)
        for model_index, model in enumerate(extracted):
            proposals.append(_model_proposal_from_record(record, model, source_index=source_index, model_index=model_index))
    output = {
        "schema_version": AGENTIC_UPDATE_PARSER_OUTPUT_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "run_id": run_id,
        "parser_id": parser_id,
        "parser_stubs": provider_parser_stubs(),
        "source_pack_path": str(pack_path),
        "summary": {
            "source_count": len(records),
            "parsed_model_count": len(proposals),
            "warning_count": len(warnings),
            "status": "parsed" if proposals else "empty",
        },
        "proposals": proposals,
        "warnings": warnings,
        "artifact_paths": {
            "parser_output": layout["files"]["parser_output"],
        },
    }
    assert_secret_free_agentic_update_payload(output, label="agentic_update_parser_output")
    write_json(Path(layout["files"]["parser_output"]), output)
    return output


def _read_source_pack(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Agentic update source pack is missing: {path}")
    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid source pack JSONL at line {line_no}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"Source pack line {line_no} must be a JSON object.")
        records.append(item)
    return records


def _extract_models_from_source(record: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    excerpt = str(record.get("parser_excerpt") or record.get("excerpt") or "")
    provider_id = str(record.get("provider_id") or "unknown")
    parsed_json = _extract_json_payload(excerpt)
    warnings: list[str] = []
    if isinstance(parsed_json, dict):
        raw_models = parsed_json.get("models")
        if isinstance(raw_models, list):
            models = [dict(item) for item in raw_models if isinstance(item, dict)]
            return models, warnings
        if any(field in parsed_json for field in ("model_id", "native_model", "model", "id")):
            return [parsed_json], warnings
    if isinstance(parsed_json, list):
        models = [dict(item) for item in parsed_json if isinstance(item, dict)]
        if models:
            return models, warnings
    looks_like_html = _looks_like_html_document(excerpt)
    if not looks_like_html:
        models = _parse_line_models(excerpt)
        if models:
            return models, warnings
    if provider_id == "qwen":
        models = _extract_qwen_models_from_official_docs(record, excerpt)
        if models:
            return models, warnings
        warnings.append(f"no_models_parsed:qwen:{record.get('source_id') or 'unknown_source'}")
        return [], warnings
    if looks_like_html:
        warnings.append(f"html_source_requires_provider_parser:{provider_id}:{record.get('source_id') or 'unknown_source'}")
        return [], warnings
    warnings.append(f"no_models_parsed:{provider_id}:{record.get('source_id') or 'unknown_source'}")
    return [], warnings


_QWEN_MODEL_ID_RE = re.compile(r"(?i)\bqwen(?:[23](?:\.\d+)?|(?:[-][a-z0-9]+)+|(?:\.[0-9]+[-][a-z0-9]+))[-a-z0-9._]*\b")
_QWEN_SERIES_ONLY = {
    "qwen",
    "qwen2",
    "qwen2.5",
    "qwen3",
    "qwen3.5",
    "qwen3.6",
    "qwen3.7",
    "qwen-coder",
    "qwen-image-api",
    "qwen-image-edit-api",
    "qwen-image-edit-guide",
    "qwen-api-reference",
    "qwen-code",
    "qwen-structured-output",
    "qwen2-vl",
    "qwen2.5-vl",
    "qwen3-code",
    "qwen3-vl",
}
_QWEN_EXCLUDED_FRAGMENTS = (
    ".py",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".zip",
    "api-reference",
    "by-calling-api",
    "calling-api",
    "color",
    "icon",
    "paw",
    "series",
    "tp-series",
    "img-url",
)


def _extract_qwen_models_from_official_docs(record: dict[str, Any], text: str) -> list[dict[str, Any]]:
    source_id = str(record.get("source_id") or "")
    ordered: dict[str, dict[str, Any]] = {}
    for match in _QWEN_MODEL_ID_RE.finditer(text):
        native_model = _normalize_qwen_model_id(match.group(0))
        if not _is_qwen_model_id_candidate(native_model):
            continue
        window = text[max(0, match.start() - 220) : min(len(text), match.end() + 220)]
        modalities = _qwen_modalities(native_model, source_id=source_id, context=window)
        existing = ordered.get(native_model)
        if existing:
            existing["input_modalities"] = _dedupe([*list(existing.get("input_modalities") or []), *modalities])
            continue
        model = {
            "model_id": f"qwen/{native_model}",
            "display_name": _qwen_display_name(native_model),
            "input_modalities": modalities,
            "confidence": "medium",
            "qwen_parser_evidence": "model_id_text_match",
        }
        context_window = _qwen_context_window_from_text(window)
        if context_window is not None:
            model["context_window"] = context_window
        ordered[native_model] = model
    return list(ordered.values())


def _normalize_qwen_model_id(value: str) -> str:
    return value.strip().strip(".,;:()[]{}<>\"'").lower().replace("_", "-")


def _is_qwen_model_id_candidate(native_model: str) -> bool:
    if not native_model or native_model in _QWEN_SERIES_ONLY:
        return False
    if native_model.startswith(("qwen35", "qwen36", "qwen37")):
        return False
    if re.search(r"-\d{4}-\d{1,2}$|-\d{4}-\d{2}-\d$", native_model):
        return False
    if re.search(r"-(?:n|c|p|t|x0|cl)$", native_model):
        return False
    if any(fragment in native_model for fragment in _QWEN_EXCLUDED_FRAGMENTS):
        return False
    if "-" not in native_model and not re.search(r"qwen[23]\.\d+-", native_model):
        return False
    if len(native_model) < 8 or len(native_model) > 80:
        return False
    return True


def _qwen_display_name(native_model: str) -> str:
    return " ".join(part.upper() if part in {"vl", "asr", "tts", "mt"} else part.capitalize() for part in re.split(r"[-_]", native_model))


def _qwen_modalities(native_model: str, *, source_id: str, context: str) -> list[str]:
    lowered = f"{native_model} {source_id} {context}".lower()
    modalities = ["text"]
    if any(marker in lowered for marker in ("-vl", "vision", "ocr", "image", "video")):
        modalities.append("image")
    if any(marker in lowered for marker in ("audio", "omni", "asr", "tts", "realtime", "livetranslate")):
        modalities.append("audio")
    if "video" in lowered:
        modalities.append("video")
    return _dedupe(modalities)


def _qwen_context_window_from_text(text: str) -> int | None:
    normalized = text.replace(",", "").replace("_", "")
    patterns = (
        r"(?i)(\d{3,7})\s*(?:tokens?|token|上下文|context)",
        r"(?i)(?:tokens?|token|上下文|context)\D{0,16}(\d{3,7})",
        r"(?i)(\d{2,4})\s*k\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        value = _int_or_none(match.group(1))
        if value is None:
            continue
        if pattern.endswith(r"k\b"):
            value *= 1000
        if 1_000 <= value <= 10_000_000:
            return value
    return None


def _looks_like_html_document(text: str) -> bool:
    head = text[:2000].lower()
    return "<!doctype html" in head or "<html" in head or "<meta " in head or "<script" in head


def _extract_json_payload(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped:
        return None
    fenced = re.search(r"```(?:json)?\s*(?P<body>[\s\S]*?)```", stripped, flags=re.IGNORECASE)
    if fenced:
        stripped = fenced.group("body").strip()
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = stripped.find(start_char)
        end = stripped.rfind(end_char)
        if start != -1 and end > start:
            candidate = stripped[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


def _parse_line_models(text: str) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for line in text.splitlines():
        normalized = line.strip().strip("-* ")
        if not normalized:
            continue
        parts = [part.strip() for part in re.split(r"\s*\|\s*|;\s*", normalized) if part.strip()]
        record: dict[str, Any] = {}
        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
            elif "=" in part:
                key, value = part.split("=", 1)
            else:
                continue
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            if key in {"model", "model_id", "native_model", "id"}:
                record["model_id"] = value
            elif key in {"name", "display_name"}:
                record["display_name"] = value
            elif key in {"context", "context_window", "advertised_context_window"}:
                record["context_window"] = _int_or_none(value)
            elif key in {"modalities", "input_modalities"}:
                record["input_modalities"] = _split_values(value)
            elif key in {"reasoning", "reasoning_modes", "supported_reasoning_levels"}:
                record["supported_reasoning_levels"] = _split_values(value)
            elif key in {"recommended", "default_for_provider", "deprecated", "tool_support", "web_search", "vision", "audio", "apply_patch"}:
                record[key] = _bool_value(value)
            elif key in {"confidence", "default_reasoning_level", "deprecated_after"}:
                record[key] = value
            else:
                record[key] = value
        if record:
            models.append(record)
    return models


def _model_proposal_from_record(
    source: dict[str, Any],
    model: dict[str, Any],
    *,
    source_index: int,
    model_index: int,
) -> dict[str, Any]:
    provider_id = str(source.get("provider_id") or _provider_from_model(model) or "unknown")
    native_model = _native_model_id(provider_id, model)
    model_id = f"{provider_id}/{native_model}" if provider_id and "/" not in native_model else native_model
    warnings = _model_warnings(model, provider_id=provider_id, native_model=native_model)
    unknown_fields = sorted(str(key) for key in model.keys() if str(key) not in _KNOWN_MODEL_FIELDS)
    warnings.extend(f"unknown_field:{field}" for field in unknown_fields)
    modalities = _modalities(model)
    reasoning_levels = _string_list(model.get("supported_reasoning_levels") or model.get("reasoning_modes"))
    proposal = {
        "proposal_id": f"{provider_id}-{native_model}-{source_index}-{model_index}",
        "provider_id": provider_id,
        "model_id": model_id,
        "native_model": native_model,
        "display_name": str(model.get("display_name") or model.get("name") or native_model),
        "candidate_metadata": {
            "advertised_context_window": _int_or_none(model.get("advertised_context_window") or model.get("context_window")),
            "input_modalities": modalities,
            "supported_reasoning_levels": reasoning_levels,
            "default_reasoning_level": _optional_string(model.get("default_reasoning_level")),
            "pricing": _pricing(model),
            "deprecated": bool(model.get("deprecated", False)),
            "deprecated_after": _optional_string(model.get("deprecated_after")),
            "default_for_provider": bool(model.get("default_for_provider", False)),
            "recommended": bool(model.get("recommended", False)),
            "confidence": _confidence(model),
        },
        "capability_claims": {
            "tool_calls": _capability_claim(model, "tool_support", "supports_tool_calls"),
            "web_search": _capability_claim(model, "web_search", "supports_web_search"),
            "vision": _capability_claim(model, "vision", "supports_vision", declared_default="image" in modalities),
            "audio": _capability_claim(model, "audio", "supports_audio"),
            "apply_patch": _capability_claim(model, "apply_patch", "supports_apply_patch"),
        },
        "source_refs": [
            {
                "source_id": source.get("source_id"),
                "source_url": source.get("url"),
                "content_hash": source.get("content_hash"),
                "excerpt_chars": source.get("excerpt_chars"),
                "parser_strategy": source.get("parser_strategy"),
            }
        ],
        "validation_state": {
            "status": "requires_validation",
            "verified": False,
            "evidence_paths": [],
        },
        "warnings": warnings,
    }
    return proposal


def _provider_from_model(model: dict[str, Any]) -> str | None:
    model_id = str(model.get("model_id") or model.get("id") or model.get("model") or "").strip()
    if "/" in model_id:
        return model_id.split("/", 1)[0]
    return None


def _native_model_id(provider_id: str, model: dict[str, Any]) -> str:
    for key in ("native_model", "model", "model_id", "id"):
        value = str(model.get(key) or "").strip()
        if not value:
            continue
        if "/" in value:
            prefix, native = value.split("/", 1)
            return native if prefix == provider_id else value
        return value
    return "unknown-model"


def _model_warnings(model: dict[str, Any], *, provider_id: str, native_model: str) -> list[str]:
    warnings: list[str] = []
    if native_model == "unknown-model":
        warnings.append("missing_model_id")
    if _int_or_none(model.get("advertised_context_window") or model.get("context_window")) is None:
        warnings.append("missing_context_window_defaulted_unknown")
    if not _string_list(model.get("supported_reasoning_levels") or model.get("reasoning_modes")):
        warnings.append("missing_reasoning_modes_defaulted_empty")
    if not _string_list(model.get("input_modalities") or model.get("modalities")):
        warnings.append("missing_modalities_defaulted_text_only")
    if provider_id == "unknown":
        warnings.append("missing_provider_id")
    warnings.append("requires_validation_before_promotion")
    return warnings


def _modalities(model: dict[str, Any]) -> list[str]:
    values = _string_list(model.get("input_modalities") or model.get("modalities"))
    normalized = [item.lower() for item in values if item.lower() in {"text", "image", "audio", "video"}]
    if "text" not in normalized:
        normalized.insert(0, "text")
    return _dedupe(normalized) or ["text"]


def _pricing(model: dict[str, Any]) -> dict[str, Any]:
    raw = model.get("pricing") if isinstance(model.get("pricing"), dict) else {}
    return {
        "input_per_mtok": _float_or_none(model.get("pricing_input_per_mtok") or raw.get("input_per_mtok")),
        "output_per_mtok": _float_or_none(model.get("pricing_output_per_mtok") or raw.get("output_per_mtok")),
        "currency": str(raw.get("currency") or model.get("pricing_currency") or "").strip() or None,
        "status": "parsed_unvalidated",
    }


def _capability_claim(model: dict[str, Any], primary_key: str, fallback_key: str, *, declared_default: bool = False) -> dict[str, Any]:
    declared = _bool_or_default(model.get(primary_key), _bool_or_default(model.get(fallback_key), declared_default))
    return {
        "declared": declared,
        "claim_status": "unverified_claim" if declared else "not_declared",
        "validation_status": "requires_validation" if declared else "not_validated",
        "verified": False,
    }


def _confidence(model: dict[str, Any]) -> str:
    value = str(model.get("confidence") or "low").strip().lower()
    return value if value in {"low", "medium", "high"} else "low"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_values(value)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _split_values(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,/ ]+", str(value)) if item.strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        text = str(value).strip().replace(",", "").replace("_", "")
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", "").replace("_", ""))
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "supported"}


def _bool_or_default(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return _bool_value(value)
