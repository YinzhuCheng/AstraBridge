from __future__ import annotations

from copy import deepcopy
import html
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
KIMI_OFFICIAL_DOCS_PARSER_ID = "kimi_official_markdown_conservative_v1"
DEEPSEEK_OFFICIAL_DOCS_PARSER_ID = "deepseek_official_docs_conservative_v1"
GLM_OFFICIAL_DOCS_PARSER_ID = "glm_official_markdown_conservative_v1"
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
    "native_supported_reasoning_levels",
    "native_default_reasoning_level",
    "reasoning_parameter",
    "reasoning_effort_mapping",
    "pricing",
    "pricing_input_per_mtok",
    "pricing_output_per_mtok",
    "pricing_cached_input_per_mtok",
    "pricing_currency",
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
    "kimi_parser_evidence",
    "deepseek_parser_evidence",
    "glm_parser_evidence",
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
    stubs["kimi"] = {
        "provider_id": "kimi",
        "parser_id": KIMI_OFFICIAL_DOCS_PARSER_ID,
        "implementation": KIMI_OFFICIAL_DOCS_PARSER_ID,
        "status": "provider_specific_parser",
        "notes": "Merges conservative model, context, modality, native reasoning, pricing, and adapter-mapping evidence from official Kimi Markdown documents; every capability remains unverified until validation.",
    }
    stubs["deepseek"] = {
        "provider_id": "deepseek",
        "parser_id": DEEPSEEK_OFFICIAL_DOCS_PARSER_ID,
        "implementation": DEEPSEEK_OFFICIAL_DOCS_PARSER_ID,
        "status": "provider_specific_parser",
        "notes": "Extracts model, context, pricing, deprecation, thinking, and reasoning-effort evidence from bounded official DeepSeek HTML excerpts.",
    }
    stubs["glm"] = {
        "provider_id": "glm",
        "parser_id": GLM_OFFICIAL_DOCS_PARSER_ID,
        "implementation": GLM_OFFICIAL_DOCS_PARSER_ID,
        "status": "provider_specific_parser",
        "notes": "Merges GLM model, context, modality, tool, and native reasoning-effort evidence from official machine-readable Markdown documents.",
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
    proposals_by_model: dict[tuple[str, str], dict[str, Any]] = {}
    warnings: list[str] = []
    for source_index, record in enumerate(records):
        if not bool(record.get("ok")):
            warnings.append(f"source_skipped:{record.get('provider_id') or 'unknown'}:{record.get('classification') or 'unknown'}")
            continue
        extracted, extract_warnings = _extract_models_from_source(record)
        warnings.extend(extract_warnings)
        for model_index, model in enumerate(extracted):
            proposal = _model_proposal_from_record(record, model, source_index=source_index, model_index=model_index)
            key = (str(proposal.get("provider_id") or ""), str(proposal.get("native_model") or ""))
            if key in proposals_by_model:
                proposals_by_model[key] = _merge_model_proposals(proposals_by_model[key], proposal)
            else:
                proposals_by_model[key] = proposal
    proposals = []
    for proposal in proposals_by_model.values():
        proposal = _reconcile_resolved_model_warnings(proposal)
        if _weak_kimi_family_candidate(proposal):
            warnings.append(f"weak_model_candidate_dropped:kimi:{proposal.get('native_model') or 'unknown'}")
            continue
        proposals.append(proposal)
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
    if str(record.get("parser_strategy") or "") == "llms_index":
        return [], []
    parsed_json = _extract_json_payload(excerpt)
    warnings: list[str] = []
    if isinstance(parsed_json, dict):
        raw_models = parsed_json.get("models")
        if isinstance(raw_models, list):
            models = [dict(item) for item in raw_models if isinstance(item, dict) and _looks_like_model_record(item)]
            if models:
                return models, warnings
        if _looks_like_model_record(parsed_json):
            return [parsed_json], warnings
    if isinstance(parsed_json, list):
        models = [dict(item) for item in parsed_json if isinstance(item, dict) and _looks_like_model_record(item)]
        if models:
            return models, warnings
    if provider_id == "kimi":
        models = _extract_kimi_models_from_official_docs(record, excerpt)
        if models:
            return models, warnings
        warnings.append(f"no_models_parsed:kimi:{record.get('source_id') or 'unknown_source'}")
        return [], warnings
    if provider_id == "deepseek":
        models = _extract_deepseek_models_from_official_docs(record, excerpt)
        if models:
            return models, warnings
        warnings.append(f"no_models_parsed:deepseek:{record.get('source_id') or 'unknown_source'}")
        return [], warnings
    if provider_id == "glm":
        models = _extract_glm_models_from_official_docs(record, excerpt)
        if models:
            return models, warnings
        warnings.append(f"no_models_parsed:glm:{record.get('source_id') or 'unknown_source'}")
        return [], warnings
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


def _looks_like_model_record(value: dict[str, Any]) -> bool:
    return any(isinstance(value.get(field), str) and str(value.get(field) or "").strip() for field in ("model_id", "native_model", "model", "id"))


_DEEPSEEK_MODEL_ID_RE = re.compile(r"(?i)\bdeepseek-(?:v\d+(?:\.\d+)?(?:-[a-z0-9]+)+|chat|reasoner)\b")
_GLM_MODEL_ID_RE = re.compile(r"(?i)\bglm-\d+(?:\.\d+)?(?:-[a-z0-9]+)*\b")


def _extract_deepseek_models_from_official_docs(record: dict[str, Any], text: str) -> list[dict[str, Any]]:
    plain = _official_doc_plain_text(text)
    model_ids = _dedupe([match.group(0).lower() for match in _DEEPSEEK_MODEL_ID_RE.finditer(plain)])
    context_window = _deepseek_context_window_from_text(plain)
    table_contracts = _deepseek_table_contracts(text)
    reasoning = _deepseek_reasoning_contract(plain)
    models: list[dict[str, Any]] = []
    for native_model in model_ids:
        evidence = _model_evidence_window(plain, native_model)
        lowered = evidence.lower()
        deprecated = native_model in {"deepseek-chat", "deepseek-reasoner"} and any(
            marker in lowered for marker in ("deprecated", "deprecation", "no longer maintained", "alias")
        )
        model: dict[str, Any] = {
            "model_id": f"deepseek/{native_model}",
            "display_name": " ".join(part.upper() if re.fullmatch(r"v\d+(?:\.\d+)?", part) else part.capitalize() for part in native_model.split("-")),
            "input_modalities": ["text"],
            "deprecated": deprecated,
            "confidence": "high" if str(record.get("trust_level") or "") == "official" else "medium",
            "tool_support": any(marker in plain.lower() for marker in ("tool calls", "tool_calls", "tool calling")),
            "deepseek_parser_evidence": "official_html_model_reference",
        }
        table_contract = dict(table_contracts.get(native_model) or {})
        model_context_window = table_contract.pop("context_window", None) or context_window
        if model_context_window is not None:
            model["context_window"] = model_context_window
        model.update(reasoning)
        model.update(table_contract)
        model.update(_deepseek_pricing_from_text(native_model, text))
        models.append(model)
    return models


def _deepseek_context_window_from_text(text: str) -> int | None:
    # DeepSeek's public API tables use decimal SI notation for token limits.
    if re.search(r"\bcontext\s+(?:length|window)\b.{0,120}\b1\s*m\b", text, re.IGNORECASE | re.DOTALL):
        return 1_000_000
    return _context_window_from_text(text)


def _deepseek_reasoning_contract(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if "reasoning_effort" not in lowered and "reasoning effort" not in lowered:
        return {}
    native_levels = [level for level in ("high", "max") if re.search(rf"[`\"']?{level}[`\"']?", lowered)]
    if not native_levels:
        return {}
    mapping = {"low": "high", "medium": "high", "high": "high"}
    if "max" in native_levels:
        mapping["xhigh"] = "max"
    supported = ["off", *mapping.keys()]
    return {
        "supported_reasoning_levels": _dedupe(supported),
        "default_reasoning_level": "high",
        "native_supported_reasoning_levels": native_levels,
        "native_default_reasoning_level": "high" if "high" in native_levels else native_levels[0],
        "reasoning_parameter": "reasoning_effort",
        "reasoning_effort_mapping": mapping,
    }


def _deepseek_pricing_from_text(native_model: str, text: str) -> dict[str, Any]:
    for row in _official_doc_rows(text):
        if native_model not in row.lower():
            continue
        prices = [float(value) for value in re.findall(r"\$\s*([0-9]+(?:\.[0-9]+)?)", row)]
        if len(prices) >= 3:
            return {
                "pricing_cached_input_per_mtok": prices[0],
                "pricing_input_per_mtok": prices[1],
                "pricing_output_per_mtok": prices[2],
                "pricing_currency": "USD",
            }
    return {}


def _deepseek_table_contracts(text: str) -> dict[str, dict[str, Any]]:
    rows = _official_doc_table_rows(text)
    model_ids: list[str] = []
    model_row_index = -1
    for index, cells in enumerate(rows):
        found = _dedupe([match.group(0).lower() for cell in cells for match in _DEEPSEEK_MODEL_ID_RE.finditer(cell)])
        if found:
            model_ids = found
            model_row_index = index
            break
    if not model_ids:
        return {}
    contracts = {model_id: {} for model_id in model_ids}
    pricing: dict[str, dict[str, float]] = {model_id: {} for model_id in model_ids}
    for cells in rows[model_row_index + 1 :]:
        row_text = " ".join(cells)
        lowered = row_text.lower()
        if "context length" in lowered or "context window" in lowered:
            context_window = _deepseek_context_window_from_text(row_text)
            if context_window is not None:
                for model_id in model_ids:
                    contracts[model_id]["context_window"] = context_window
        prices = [float(value) for value in re.findall(r"\$\s*([0-9]+(?:\.[0-9]+)?)", row_text)]
        if len(prices) < len(model_ids):
            continue
        field = None
        if "cache hit" in lowered:
            field = "pricing_cached_input_per_mtok"
        elif "cache miss" in lowered:
            field = "pricing_input_per_mtok"
        elif "output" in lowered and "token" in lowered:
            field = "pricing_output_per_mtok"
        if field:
            for index, model_id in enumerate(model_ids):
                pricing[model_id][field] = prices[index]
    for model_id, values in pricing.items():
        if values:
            contracts[model_id].update(values)
            contracts[model_id]["pricing_currency"] = "USD"
    return contracts


def _extract_glm_models_from_official_docs(record: dict[str, Any], text: str) -> list[dict[str, Any]]:
    plain = _official_doc_plain_text(text)
    model_ids = _dedupe(
        [
            match.group(0).lower()
            for match in _GLM_MODEL_ID_RE.finditer(text)
            if _is_glm_model_id_candidate(match.group(0)) and _is_glm_model_reference(text, match.start(), match.end())
        ]
    )
    context_window = _context_window_from_text(plain)
    reasoning = _glm_reasoning_contract(plain)
    lowered = plain.lower()
    models: list[dict[str, Any]] = []
    for native_model in model_ids:
        evidence = _model_evidence_window(plain, native_model).lower()
        modalities = ["text"]
        if any(marker in evidence for marker in ("image input", "vision", "image understanding", "multimodal")):
            modalities.append("image")
        if "video input" in evidence or "video understanding" in evidence:
            modalities.append("video")
        if "audio input" in evidence or "audio understanding" in evidence:
            modalities.append("audio")
        model: dict[str, Any] = {
            "model_id": f"glm/{native_model}",
            "display_name": native_model.upper().replace("-", " "),
            "input_modalities": modalities,
            "deprecated": "deprecated" in evidence or "discontinued" in evidence,
            "confidence": "high" if str(record.get("trust_level") or "") == "official" else "medium",
            "tool_support": any(marker in lowered for marker in ("function calling", "tool calls", "tool_calls", "tool_choice")),
            "vision": "image" in modalities,
            "audio": "audio" in modalities,
            "glm_parser_evidence": "official_markdown_model_reference",
        }
        if context_window is not None:
            model["context_window"] = context_window
        model.update(reasoning)
        models.append(model)
    return models


def _is_glm_model_id_candidate(native_model: str) -> bool:
    normalized = native_model.lower().strip(".,;:()[]{}<>\"'")
    if normalized.endswith(("-model", "-api", "-guide", "-docs")):
        return False
    major = re.match(r"glm-(\d+)", normalized)
    return bool(major and int(major.group(1)) >= 4)


def _is_glm_model_reference(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 64) : start]
    suffix = text[end : min(len(text), end + 16)]
    if re.search(r"(?:[`\"']|\*\*|\[)\s*$", prefix) and re.match(r"\s*(?:[`\"']|\*\*|\])", suffix):
        return True
    if re.search(r"(?i)\bmodel\s*[:=]\s*[`\"']?\s*$", prefix):
        return True
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end].strip()
    if re.match(r"^#{1,6}\s+", line) and re.fullmatch(r"#{1,6}\s+[`*]*glm-[a-z0-9._-]+[`*]*", line, flags=re.IGNORECASE):
        return True
    return bool(line.startswith("|") and "|" in line[1:])


def _glm_reasoning_contract(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if "reasoning_effort" not in lowered and "reasoning effort" not in lowered:
        return {}
    native_order = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
    native_levels = [level for level in native_order if re.search(rf"[`\"']{level}[`\"']", lowered)]
    if not native_levels:
        return {}
    mapping = {"off": "none", "minimal": "minimal", "low": "high", "medium": "high", "high": "high", "xhigh": "max"}
    mapping = {key: value for key, value in mapping.items() if value in native_levels}
    default_native = "max" if "max" in native_levels else "high" if "high" in native_levels else native_levels[-1]
    default_codex = "xhigh" if default_native == "max" else default_native
    return {
        "supported_reasoning_levels": list(mapping),
        "default_reasoning_level": default_codex,
        "native_supported_reasoning_levels": native_levels,
        "native_default_reasoning_level": default_native,
        "reasoning_parameter": "reasoning_effort",
        "reasoning_effort_mapping": mapping,
    }


def _official_doc_rows(text: str) -> list[str]:
    rows = []
    for match in re.finditer(r"(?is)<tr\b[^>]*>(.*?)</tr>", text):
        rows.append(_official_doc_plain_text(match.group(1)))
    rows.extend(line.strip() for line in text.splitlines() if line.strip().startswith("|") and line.strip().endswith("|"))
    return rows


def _official_doc_table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for match in re.finditer(r"(?is)<tr\b[^>]*>(.*?)</tr>", text):
        cells = [
            _official_doc_plain_text(cell.group(1))
            for cell in re.finditer(r"(?is)<t[dh]\b[^>]*>(.*?)</t[dh]>", match.group(1))
        ]
        if cells:
            rows.append(cells)
    return rows


def _official_doc_plain_text(text: str) -> str:
    value = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", text)
    value = re.sub(r"(?i)</(?:td|th|tr|p|li|h[1-6])>", "\n", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = html.unescape(value)
    return "\n".join(re.sub(r"\s+", " ", line).strip() for line in value.splitlines() if line.strip())


def _model_evidence_window(text: str, native_model: str, radius: int = 1200) -> str:
    match = re.search(re.escape(native_model), text, flags=re.IGNORECASE)
    if not match:
        return text[: radius * 2]
    return text[max(0, match.start() - radius) : min(len(text), match.end() + radius)]


_KIMI_MODEL_ID_RE = re.compile(
    r"(?i)\b(?:kimi-k\d(?:[.\d]*)(?:-[a-z0-9]+)*|kimi-latest|kimi-thinking-preview|"
    r"moonshot-v1-(?:8k|32k|128k)(?:-vision-preview)?)\b"
)
_KIMI_CODEX_REASONING_ORDER = ("off", "minimal", "low", "medium", "high", "xhigh")
_KIMI_NATIVE_REASONING_ORDER = ("none", "off", "minimal", "low", "medium", "high", "max", "xhigh")


def _extract_kimi_models_from_official_docs(record: dict[str, Any], text: str) -> list[dict[str, Any]]:
    evidence_by_model: dict[str, list[str]] = {}
    deprecated_models: set[str] = set()
    table_models: set[str] = set()
    in_deprecated_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            in_deprecated_section = "deprecated" in stripped.lower() or "discontinued" in stripped.lower()
        table_match = re.match(
            r"^\|\s*`?(?P<model>(?:kimi|moonshot)-[a-z0-9][a-z0-9._-]*)`?\s*\|(?P<description>.*)\|\s*$",
            stripped,
            flags=re.IGNORECASE,
        )
        if not table_match:
            continue
        native_model = _normalize_kimi_model_id(table_match.group("model"))
        if not _is_kimi_model_id_candidate(native_model):
            continue
        evidence_by_model.setdefault(native_model, []).append(stripped)
        table_models.add(native_model)
        if in_deprecated_section or "deprecated" in table_match.group("description").lower():
            deprecated_models.add(native_model)

    for match in _KIMI_MODEL_ID_RE.finditer(text):
        if not _is_kimi_model_reference(text, match.start(), match.end()):
            continue
        native_model = _normalize_kimi_model_id(match.group(0))
        if not _is_kimi_model_id_candidate(native_model):
            continue
        window = text[max(0, match.start() - 700) : min(len(text), match.end() + 900)]
        evidence_by_model.setdefault(native_model, []).append(window)
        if _kimi_model_deprecation_evidence(native_model, window):
            deprecated_models.add(native_model)

    models: list[dict[str, Any]] = []
    single_model_document = len(evidence_by_model) == 1
    for native_model, snippets in evidence_by_model.items():
        evidence = text if single_model_document else "\n".join(_dedupe(snippets))
        model = _kimi_model_from_evidence(
            native_model,
            evidence,
            deprecated=native_model in deprecated_models,
            parser_evidence=(
                "official_model_table"
                if native_model in table_models and str(record.get("source_type") or "") == "models_catalog"
                else "official_pricing_table"
                if native_model in table_models and str(record.get("source_type") or "") == "pricing"
                else "official_markdown_model_reference"
            ),
        )
        models.append(model)
    return models


def _normalize_kimi_model_id(value: str) -> str:
    return value.strip().strip(".,;:()[]{}<>\"'").lower().replace("_", "-")


def _is_kimi_model_id_candidate(native_model: str) -> bool:
    if not native_model or len(native_model) > 80:
        return False
    if any(
        native_model.endswith(suffix)
        for suffix in (
            "-quickstart",
            "-best-practice",
            "-api-reference",
            "-guide",
            "-cli",
        )
    ):
        return False
    return bool(_KIMI_MODEL_ID_RE.fullmatch(native_model))


def _is_kimi_model_reference(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 48) : start]
    suffix = text[end : min(len(text), end + 8)]
    if re.search(r"[`\"']\s*$", prefix) and re.match(r"\s*[`\"']", suffix):
        return True
    if re.search(r"(?i)\bmodel\s*[:=]\s*[`\"']?\s*$", prefix):
        return True
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end].strip()
    return bool(line.startswith("|") and "|" in line[1:])


def _kimi_model_deprecation_evidence(native_model: str, text: str) -> bool:
    escaped = re.escape(native_model)
    patterns = (
        rf"(?i)[`\"']?{escaped}[`\"']?(?:\s+series\s+models?)?\s+(?:was|were|is|are|will\s+be)?\s*(?:officially\s+)?(?:deprecated|discontinued|sunset)",
        rf"(?i)(?:deprecated|discontinued|sunset)\s+(?:model\s+)?[`\"']?{escaped}[`\"']?",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _kimi_model_from_evidence(
    native_model: str,
    evidence: str,
    *,
    deprecated: bool,
    parser_evidence: str,
) -> dict[str, Any]:
    modalities = _kimi_modalities(native_model, evidence)
    reasoning = _kimi_reasoning_contract(evidence)
    pricing = _kimi_pricing_from_text(native_model, evidence)
    lowered = evidence.lower()
    model: dict[str, Any] = {
        "model_id": f"kimi/{native_model}",
        "display_name": _kimi_display_name(native_model),
        "input_modalities": modalities,
        "deprecated": deprecated,
        "confidence": "medium",
        "tool_support": any(marker in lowered for marker in ("toolcalls", "tool calls", "tool calling", "tool use", "tool_choice")),
        "web_search": "web_search" in lowered or "internet search" in lowered,
        "vision": "image" in modalities,
        "audio": "audio" in modalities,
        "kimi_parser_evidence": parser_evidence,
    }
    context_window = _context_window_from_text(evidence)
    if context_window is not None:
        model["context_window"] = context_window
    model.update(reasoning)
    model.update(pricing)
    return model


def _kimi_display_name(native_model: str) -> str:
    parts = re.split(r"[-_]", native_model)
    rendered = []
    for part in parts:
        if part in {"kimi", "moonshot", "code", "highspeed", "thinking", "preview", "latest"}:
            rendered.append(part.capitalize())
        elif re.fullmatch(r"(?:k|v)\d(?:\.\d+)?", part, flags=re.IGNORECASE):
            rendered.append(part.upper())
        elif re.fullmatch(r"\d+k", part, flags=re.IGNORECASE):
            rendered.append(part.upper())
        else:
            rendered.append(part.capitalize())
    return " ".join(rendered)


def _kimi_modalities(native_model: str, evidence: str) -> list[str]:
    lowered = f"{native_model} {evidence}".lower()
    modalities = ["text"]
    if any(marker in lowered for marker in ("native visual", "visual understanding", "vision model", "image input", "image understanding", "visual and text")):
        modalities.append("image")
    if any(marker in lowered for marker in ("video input", "video understanding", "image and video", "images and videos")):
        if "image" not in modalities:
            modalities.append("image")
        modalities.append("video")
    if any(marker in lowered for marker in ("audio input", "audio understanding", "speech input")):
        modalities.append("audio")
    if "vision-preview" in native_model and "image" not in modalities:
        modalities.append("image")
    return _dedupe(modalities)


def _kimi_reasoning_contract(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if "reasoning_effort" not in lowered and "reasoning effort" not in lowered:
        return {}
    lines = text.splitlines()
    relevant_indexes = [
        index
        for index, line in enumerate(lines)
        if "reasoning_effort" in line.lower() or "reasoning effort" in line.lower()
    ]
    relevant_lines = [lines[index] for index in relevant_indexes]
    relevant_text = "\n".join(relevant_lines)
    quoted = {
        value.lower()
        for value in re.findall(
            r"[`\"'](none|off|minimal|low|medium|high|max|xhigh)[`\"']",
            relevant_text,
            flags=re.IGNORECASE,
        )
    }
    if not quoted:
        for index in relevant_indexes:
            if index + 1 >= len(lines):
                continue
            neighbor = lines[index + 1]
            if any(marker in neighbor.lower() for marker in ("support", "accept", "default")):
                relevant_lines.append(neighbor)
        relevant_text = "\n".join(relevant_lines)
        quoted = {
            value.lower()
            for value in re.findall(
                r"[`\"'](none|off|minimal|low|medium|high|max|xhigh)[`\"']",
                relevant_text,
                flags=re.IGNORECASE,
            )
        }
    native_levels = [level for level in _KIMI_NATIVE_REASONING_ORDER if level in quoted]
    if not native_levels:
        return {}
    native_to_codex = {"none": "off", "off": "off", "max": "xhigh", "xhigh": "xhigh"}
    codex_levels = _dedupe([native_to_codex.get(level, level) for level in native_levels])
    codex_levels = [level for level in _KIMI_CODEX_REASONING_ORDER if level in codex_levels]
    default_native = None
    for level in reversed(_KIMI_NATIVE_REASONING_ORDER):
        if level not in native_levels:
            continue
        if re.search(rf"(?i)(?:default(?:s|ed)?(?:\s+is|\s+to|\s*[:=])?\s*[`\"']?{re.escape(level)}\b|\b{re.escape(level)}[`\"']?\s+as\s+the\s+default)", relevant_text):
            default_native = level
            break
    default_codex = native_to_codex.get(default_native, default_native) if default_native else None
    codex_to_provider = {native_to_codex.get(level, level): level for level in native_levels}
    return {
        "supported_reasoning_levels": codex_levels,
        "default_reasoning_level": default_codex,
        "native_supported_reasoning_levels": native_levels,
        "native_default_reasoning_level": default_native,
        "reasoning_parameter": "reasoning_effort",
        "reasoning_effort_mapping": codex_to_provider,
    }


def _kimi_pricing_from_text(native_model: str, text: str) -> dict[str, Any]:
    candidate_lines = [line for line in text.splitlines() if native_model in line.lower()]
    for line in candidate_lines:
        prices = [
            float(value)
            for value in re.findall(
                r"(?:\$\s*|\{\s*[`\"']\$[`\"']\s*\}\s*)([0-9]+(?:\.[0-9]+)?)",
                line,
            )
        ]
        if len(prices) >= 3:
            return {
                "pricing_cached_input_per_mtok": prices[0],
                "pricing_input_per_mtok": prices[1],
                "pricing_output_per_mtok": prices[2],
                "pricing_currency": "USD",
            }
        if len(prices) >= 2:
            return {
                "pricing_input_per_mtok": prices[0],
                "pricing_output_per_mtok": prices[1],
                "pricing_currency": "USD",
            }
    return {}


def _context_window_from_text(text: str) -> int | None:
    normalized = text.replace("_", "")
    matches: list[int] = []
    patterns = (
        r"(?i)context(?:\s+window|\s+length)?(?:\s+of|\s+up\s+to)?\s*[:=]?\s*(\d[\d,]*(?:\.\d+)?)\s*([km])?\b",
        r"(?i)(\d[\d,]*(?:\.\d+)?)\s*([km])\s*(?:-?token|\s+token|\s+context)",
        r"(?i)(\d{1,3}(?:,\d{3})+|\d{4,8})[-\s]+tokens?\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, normalized):
            value = _scaled_token_value(match.group(1), match.group(2) if match.lastindex and match.lastindex >= 2 else None)
            if value is not None and 1_000 <= value <= 10_000_000:
                matches.append(value)
    return max(matches) if matches else None


def _scaled_token_value(number: str, suffix: str | None) -> int | None:
    try:
        numeric = float(str(number).replace(",", ""))
    except ValueError:
        return None
    normalized_suffix = str(suffix or "").lower()
    if normalized_suffix == "m":
        return int(numeric * (1_048_576 if numeric <= 4 and numeric.is_integer() else 1_000_000))
    if normalized_suffix == "k":
        whole = int(numeric)
        multiplier = 1024 if numeric.is_integer() and whole in {8, 16, 32, 64, 128, 256, 512, 1024} else 1000
        return int(numeric * multiplier)
    return int(numeric)


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
    native_reasoning_levels = _string_list(model.get("native_supported_reasoning_levels"))
    reasoning_mapping = dict(model.get("reasoning_effort_mapping") or {}) if isinstance(model.get("reasoning_effort_mapping"), dict) else {}
    reasoning_parameter = _optional_string(model.get("reasoning_parameter"))
    proposal = {
        "proposal_id": f"{provider_id}-{native_model}-{source_index}-{model_index}",
        "provider_id": provider_id,
        "model_id": model_id,
        "native_model": native_model,
        "display_name": str(model.get("display_name") or model.get("name") or native_model),
        "parser_evidence": _dedupe(
            [
                str(value).strip()
                for value in (
                    model.get("kimi_parser_evidence"),
                    model.get("qwen_parser_evidence"),
                    model.get("deepseek_parser_evidence"),
                    model.get("glm_parser_evidence"),
                )
                if str(value or "").strip()
            ]
        ),
        "candidate_metadata": {
            "advertised_context_window": _int_or_none(model.get("advertised_context_window") or model.get("context_window")),
            "input_modalities": modalities,
            "supported_reasoning_levels": reasoning_levels,
            "default_reasoning_level": _optional_string(model.get("default_reasoning_level")),
            "native_supported_reasoning_levels": native_reasoning_levels,
            "native_default_reasoning_level": _optional_string(model.get("native_default_reasoning_level")),
            "reasoning_effort_mapping": reasoning_mapping,
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
        "adapter_requirements": {
            "reasoning_parameter": reasoning_parameter,
            "codex_to_provider_reasoning_effort": reasoning_mapping,
            "review_status": "requires_adapter_review" if reasoning_parameter or reasoning_mapping else "not_declared",
        },
        "source_refs": [
            {
                "source_id": source.get("source_id"),
                "source_url": source.get("url"),
                "platform_id": source.get("platform_id"),
                "content_hash": source.get("content_hash"),
                "excerpt_chars": source.get("excerpt_chars"),
                "parser_strategy": source.get("parser_strategy"),
                "source_type": source.get("source_type"),
                "trust_level": source.get("trust_level"),
                "channel": source.get("channel"),
                "discovered_from_source_id": source.get("discovered_from_source_id"),
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


def _merge_model_proposals(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(existing)
    warnings = [str(item) for item in list(merged.get("warnings") or [])]
    existing_metadata = dict(merged.get("candidate_metadata") or {})
    candidate_metadata = dict(candidate.get("candidate_metadata") or {})

    for field in ("input_modalities", "supported_reasoning_levels", "native_supported_reasoning_levels"):
        existing_metadata[field] = _dedupe(
            [
                *_string_list(existing_metadata.get(field)),
                *_string_list(candidate_metadata.get(field)),
            ]
        )
    for field in ("advertised_context_window", "default_reasoning_level", "native_default_reasoning_level"):
        current_value = existing_metadata.get(field)
        candidate_value = candidate_metadata.get(field)
        if current_value in (None, "", []):
            existing_metadata[field] = candidate_value
        elif candidate_value not in (None, "", []) and current_value != candidate_value:
            warnings.append(f"conflicting_candidate_metadata:{field}")
    for field in ("deprecated_after",):
        if not existing_metadata.get(field) and candidate_metadata.get(field):
            existing_metadata[field] = candidate_metadata[field]
    for field in ("deprecated", "default_for_provider", "recommended"):
        existing_metadata[field] = bool(existing_metadata.get(field) or candidate_metadata.get(field))

    existing_mapping = dict(existing_metadata.get("reasoning_effort_mapping") or {})
    for codex_effort, provider_effort in dict(candidate_metadata.get("reasoning_effort_mapping") or {}).items():
        if codex_effort in existing_mapping and existing_mapping[codex_effort] != provider_effort:
            warnings.append(f"conflicting_reasoning_effort_mapping:{codex_effort}")
            continue
        existing_mapping[str(codex_effort)] = str(provider_effort)
    existing_metadata["reasoning_effort_mapping"] = existing_mapping

    existing_pricing = dict(existing_metadata.get("pricing") or {})
    candidate_pricing = dict(candidate_metadata.get("pricing") or {})
    for field in ("input_per_mtok", "output_per_mtok", "cached_input_per_mtok", "currency"):
        current_value = existing_pricing.get(field)
        candidate_value = candidate_pricing.get(field)
        if current_value in (None, ""):
            existing_pricing[field] = candidate_value
        elif candidate_value not in (None, "") and current_value != candidate_value:
            warnings.append(f"conflicting_candidate_pricing:{field}")
    existing_pricing["status"] = "parsed_unvalidated"
    existing_metadata["pricing"] = existing_pricing
    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    current_confidence = str(existing_metadata.get("confidence") or "low")
    candidate_confidence = str(candidate_metadata.get("confidence") or "low")
    if confidence_rank.get(candidate_confidence, 0) > confidence_rank.get(current_confidence, 0):
        existing_metadata["confidence"] = candidate_confidence
    merged["candidate_metadata"] = existing_metadata

    capability_claims = dict(merged.get("capability_claims") or {})
    for capability_id, raw_claim in dict(candidate.get("capability_claims") or {}).items():
        incoming = dict(raw_claim or {})
        current = dict(capability_claims.get(capability_id) or {})
        if bool(incoming.get("declared")):
            current = incoming
        capability_claims[capability_id] = current
    merged["capability_claims"] = capability_claims

    adapter_requirements = dict(merged.get("adapter_requirements") or {})
    incoming_adapter = dict(candidate.get("adapter_requirements") or {})
    if not adapter_requirements.get("reasoning_parameter") and incoming_adapter.get("reasoning_parameter"):
        adapter_requirements["reasoning_parameter"] = incoming_adapter["reasoning_parameter"]
    adapter_mapping = dict(adapter_requirements.get("codex_to_provider_reasoning_effort") or {})
    adapter_mapping.update(dict(incoming_adapter.get("codex_to_provider_reasoning_effort") or {}))
    adapter_requirements["codex_to_provider_reasoning_effort"] = adapter_mapping
    if adapter_requirements.get("reasoning_parameter") or adapter_mapping:
        adapter_requirements["review_status"] = "requires_adapter_review"
    merged["adapter_requirements"] = adapter_requirements

    source_refs = [dict(item) for item in list(merged.get("source_refs") or []) if isinstance(item, dict)]
    seen_refs = {
        (str(item.get("source_id") or ""), str(item.get("source_url") or ""), str(item.get("content_hash") or ""))
        for item in source_refs
    }
    for item in list(candidate.get("source_refs") or []):
        if not isinstance(item, dict):
            continue
        marker = (str(item.get("source_id") or ""), str(item.get("source_url") or ""), str(item.get("content_hash") or ""))
        if marker not in seen_refs:
            source_refs.append(dict(item))
            seen_refs.add(marker)
    merged["source_refs"] = source_refs
    merged["parser_evidence"] = _dedupe(
        [
            *[str(item) for item in list(merged.get("parser_evidence") or [])],
            *[str(item) for item in list(candidate.get("parser_evidence") or [])],
        ]
    )
    warnings.extend(str(item) for item in list(candidate.get("warnings") or []))
    merged["warnings"] = _dedupe(warnings)
    return merged


def _weak_kimi_family_candidate(proposal: dict[str, Any]) -> bool:
    if str(proposal.get("provider_id") or "") != "kimi":
        return False
    native_model = str(proposal.get("native_model") or "")
    if not re.fullmatch(r"kimi-k\d+(?:\.\d+)?", native_model):
        return False
    evidence = set(str(item) for item in list(proposal.get("parser_evidence") or []))
    return not bool(evidence.intersection({"official_model_table", "official_pricing_table"}))


def _reconcile_resolved_model_warnings(proposal: dict[str, Any]) -> dict[str, Any]:
    reconciled = deepcopy(proposal)
    metadata = dict(reconciled.get("candidate_metadata") or {})
    resolved: set[str] = set()
    if str(reconciled.get("native_model") or "") not in {"", "unknown-model"}:
        resolved.add("missing_model_id")
    if metadata.get("advertised_context_window") is not None:
        resolved.add("missing_context_window_defaulted_unknown")
    if _string_list(metadata.get("supported_reasoning_levels") or metadata.get("native_supported_reasoning_levels")):
        resolved.add("missing_reasoning_modes_defaulted_empty")
    modalities = _string_list(metadata.get("input_modalities"))
    if any(item != "text" for item in modalities):
        resolved.add("missing_modalities_defaulted_text_only")
    if str(reconciled.get("provider_id") or "") not in {"", "unknown"}:
        resolved.add("missing_provider_id")
    reconciled["warnings"] = [
        str(item)
        for item in list(reconciled.get("warnings") or [])
        if str(item) not in resolved
    ]
    return reconciled


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
    if not _string_list(model.get("supported_reasoning_levels") or model.get("reasoning_modes") or model.get("native_supported_reasoning_levels")):
        warnings.append("missing_reasoning_modes_defaulted_empty")
    if not _string_list(model.get("input_modalities") or model.get("modalities")):
        warnings.append("missing_modalities_defaulted_text_only")
    if provider_id == "unknown":
        warnings.append("missing_provider_id")
    if model.get("reasoning_parameter") or model.get("reasoning_effort_mapping"):
        warnings.append("provider_reasoning_transport_mapping_requires_adapter_review")
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
        "cached_input_per_mtok": _float_or_none(model.get("pricing_cached_input_per_mtok") or raw.get("cached_input_per_mtok")),
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
