from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..common import now_iso, write_json
from .artifacts import ensure_agentic_update_run_layout, validate_agentic_update_artifact_path
from .contracts import (
    agentic_update_proposal_template,
    assert_secret_free_agentic_update_payload,
    normalize_update_scope_contract,
    validate_update_proposal,
)


AGENTIC_UPDATE_KERNEL_CANDIDATE_SCHEMA_VERSION = "astrabridge-agentic-update-codex-kernel-candidates-v1"
CODEX_KERNEL_RELEASE_SOURCE_SCHEMA_VERSION = "astrabridge-codex-kernel-release-sources-v1"

DEFAULT_KERNEL_CANDIDATE_MAX_EXCERPT_CHARS = 1200
DEFAULT_KERNEL_CANDIDATE_MAX_CANDIDATES = 20
KERNEL_CANDIDATE_RELATIVE_PATH = "parsed/codex-kernel-candidates.json"


def codex_kernel_release_sources() -> list[dict[str, Any]]:
    return [
        _normalize_kernel_release_source(
            {
                "source_id": "openai-codex-github-releases",
                "url": "https://github.com/openai/codex/releases",
                "source_type": "release_notes",
                "trust_level": "official",
                "channel": "release_notes",
                "parser_strategy": "github_releases",
                "stale_after_days": 3,
                "promotable": True,
                "notes": "Official OpenAI Codex repository release notes. Discovery records metadata only.",
            }
        ),
        _normalize_kernel_release_source(
            {
                "source_id": "openai-codex-github-repository",
                "url": "https://github.com/openai/codex",
                "source_type": "source_repository",
                "trust_level": "official",
                "channel": "source_repository",
                "parser_strategy": "github_repository",
                "stale_after_days": 7,
                "promotable": True,
                "notes": "Official OpenAI Codex source repository for tags and install guidance cross-checks.",
            }
        ),
        _normalize_kernel_release_source(
            {
                "source_id": "openai-codex-npm-package",
                "url": "https://www.npmjs.com/package/@openai/codex",
                "source_type": "package_registry",
                "trust_level": "official",
                "channel": "stable_package",
                "parser_strategy": "npm_package",
                "stale_after_days": 3,
                "promotable": True,
                "notes": "Package registry metadata for @openai/codex candidate versions.",
            }
        ),
        _normalize_kernel_release_source(
            {
                "source_id": "openai-codex-install-script",
                "url": "https://chatgpt.com/codex/install.sh",
                "source_type": "installer_script",
                "trust_level": "official",
                "channel": "stable_installer",
                "parser_strategy": "installer_hint",
                "stale_after_days": 7,
                "promotable": False,
                "requires_manual_review": True,
                "notes": "Installer URL is only an install hint source. Discovery must not execute it.",
            }
        ),
    ]


def discover_codex_kernel_candidates(
    *,
    workspace_root: str | Path,
    run_id: str,
    run_contract: dict[str, Any],
    source_records: list[dict[str, Any]] | None = None,
    fixture_sources: dict[str, Any] | None = None,
    max_candidates: int = DEFAULT_KERNEL_CANDIDATE_MAX_CANDIDATES,
    max_excerpt_chars: int = DEFAULT_KERNEL_CANDIDATE_MAX_EXCERPT_CHARS,
) -> dict[str, Any]:
    contract = normalize_update_scope_contract(run_contract)
    if "codex_kernel" not in set(contract["scope"]):
        raise ValueError("Codex kernel candidate discovery requires codex_kernel scope.")
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive.")
    if max_excerpt_chars < 80:
        raise ValueError("max_excerpt_chars must be at least 80.")

    layout = ensure_agentic_update_run_layout(workspace_root, run_id)
    candidate_path = validate_agentic_update_artifact_path(workspace_root, run_id, KERNEL_CANDIDATE_RELATIVE_PATH)
    sources = [_normalize_kernel_release_source(item) for item in (source_records or codex_kernel_release_sources())]
    mode = "fixture" if fixture_sources is not None or not contract["allow_network"] else "metadata_only"
    now = now_iso()
    warnings: list[str] = []
    source_summaries: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    if mode == "metadata_only":
        warnings.append("network_fetch_deferred:use_discovery_runner_or_fixture_sources")

    for source_index, source in enumerate(sources):
        fixture = _fixture_for_source(fixture_sources or {}, source)
        source_summary = _source_summary_from_fixture(source, fixture, mode=mode, max_excerpt_chars=max_excerpt_chars)
        source_summaries.append(source_summary)
        if not source_summary["ok"]:
            warnings.extend(source_summary["warnings"])
            continue
        extracted, extract_warnings = _extract_kernel_candidate_records(source_summary["excerpt"])
        warnings.extend(extract_warnings)
        for candidate_index, record in enumerate(extracted):
            if len(candidates) >= max_candidates:
                warnings.append("candidate_limit_reached")
                break
            candidate = _kernel_candidate_from_record(
                record,
                source_summary,
                contract,
                source_index=source_index,
                candidate_index=candidate_index,
            )
            if candidate is None:
                warnings.append(f"candidate_skipped_missing_version:{source_summary['source_id']}:{candidate_index}")
                continue
            candidates.append(candidate)

    proposal = kernel_candidates_to_update_proposal(
        run_contract=contract,
        run_id=run_id,
        candidates=candidates,
        sources=source_summaries,
        mode=mode,
        warnings=warnings,
    )
    summary = {
        "source_count": len(source_summaries),
        "candidate_count": len(candidates),
        "warning_count": len(warnings),
        "status": "discovered" if candidates else "empty",
        "install_authorized": bool(contract["allow_install"]),
        "installed_or_switched": False,
    }
    output = {
        "schema_version": AGENTIC_UPDATE_KERNEL_CANDIDATE_SCHEMA_VERSION,
        "generated_at": now,
        "run_id": run_id,
        "mode": mode,
        "run_contract": contract,
        "summary": summary,
        "sources": source_summaries,
        "candidates": candidates,
        "proposal": proposal,
        "artifact_paths": {
            "kernel_candidates": str(candidate_path),
            "proposal": layout["files"]["proposal"],
        },
        "side_effect_policy": _discovery_side_effect_policy(),
        "warnings": warnings,
    }
    assert_secret_free_agentic_update_payload(output, label="codex_kernel_candidate_discovery")
    write_json(candidate_path, output)
    write_json(Path(layout["files"]["proposal"]), proposal)
    return output


def kernel_candidates_to_update_proposal(
    *,
    run_contract: dict[str, Any],
    run_id: str,
    candidates: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
    mode: str = "fixture",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    contract = normalize_update_scope_contract(run_contract)
    if "codex_kernel" not in set(contract["scope"]):
        raise ValueError("Codex kernel proposals require codex_kernel scope.")
    proposal = agentic_update_proposal_template(contract, run_id=run_id)
    proposal["discovery_result"] = {
        "schema_version": "astrabridge-agentic-update-discovery-result-v1",
        "generated_at": now_iso(),
        "mode": mode,
        "sources": [_proposal_source_record(item) for item in (sources or [])],
        "findings": [_proposal_candidate_record(item) for item in candidates],
        "warnings": list(warnings or []),
    }
    proposal["diff"]["status"] = "not_generated"
    proposal["diff"]["warnings"].append("codex_kernel_candidates_are_discovery_only")
    proposal["validation_result"]["status"] = "not_run"
    proposal["validation_result"]["warnings"].append("codex_kernel_candidates_require_probe_and_smoke_before_promotion")
    proposal["apply_manifest"]["warnings"].append("discovery_does_not_install_or_switch_codex_binaries")
    proposal["rollback_manifest"]["warnings"].append("no_runtime_state_was_changed_during_discovery")
    return validate_update_proposal(proposal)


def _normalize_kernel_release_source(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise TypeError("Codex kernel release source must be a dict.")
    url = _required_string(record, "url")
    source_id = str(record.get("source_id") or _source_id_from_url(url)).strip()
    if not source_id:
        raise ValueError("Codex kernel release source_id must not be empty.")
    trust_level = str(record.get("trust_level") or "official").strip()
    if trust_level != "official":
        raise ValueError("Codex kernel discovery sources must be official by default.")
    normalized = {
        "schema_version": CODEX_KERNEL_RELEASE_SOURCE_SCHEMA_VERSION,
        "source_id": source_id,
        "url": url,
        "source_type": str(record.get("source_type") or "release_notes").strip(),
        "trust_level": trust_level,
        "channel": str(record.get("channel") or "release_notes").strip(),
        "parser_strategy": str(record.get("parser_strategy") or "manual_review").strip(),
        "stale_after_days": _positive_int(record.get("stale_after_days"), default=7),
        "promotable": bool(record.get("promotable", True)),
        "requires_manual_review": bool(record.get("requires_manual_review", False)),
        "notes": str(record.get("notes") or "").strip(),
    }
    assert_secret_free_agentic_update_payload(normalized, label="codex_kernel_release_source")
    return normalized


def _source_summary_from_fixture(
    source: dict[str, Any],
    fixture: Any,
    *,
    mode: str,
    max_excerpt_chars: int,
) -> dict[str, Any]:
    now = now_iso()
    if fixture is None:
        status_label = "fixture_missing" if mode == "fixture" else "metadata_only_no_fetch"
        return {
            "schema_version": CODEX_KERNEL_RELEASE_SOURCE_SCHEMA_VERSION,
            "source_id": source["source_id"],
            "url": source["url"],
            "final_url": source["url"],
            "source_type": source["source_type"],
            "trust_level": source["trust_level"],
            "channel": source["channel"],
            "parser_strategy": source["parser_strategy"],
            "promotable": source["promotable"],
            "requires_manual_review": source["requires_manual_review"],
            "mode": mode,
            "ok": False,
            "status_label": status_label,
            "content_type": None,
            "content_hash": None,
            "content_bytes": 0,
            "excerpt": "",
            "excerpt_chars": 0,
            "observed_at": now,
            "warnings": [status_label],
        }
    body, content_type, final_url = _coerce_fixture_source(fixture, source)
    excerpt = _safe_excerpt(body, max_excerpt_chars)
    return {
        "schema_version": CODEX_KERNEL_RELEASE_SOURCE_SCHEMA_VERSION,
        "source_id": source["source_id"],
        "url": source["url"],
        "final_url": final_url,
        "source_type": source["source_type"],
        "trust_level": source["trust_level"],
        "channel": source["channel"],
        "parser_strategy": source["parser_strategy"],
        "promotable": source["promotable"],
        "requires_manual_review": source["requires_manual_review"],
        "mode": mode,
        "ok": True,
        "status_label": "ok",
        "content_type": content_type,
        "content_hash": f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}",
        "content_bytes": len(body.encode("utf-8")),
        "excerpt": excerpt,
        "excerpt_chars": len(excerpt),
        "observed_at": now,
        "warnings": [],
    }


def _extract_kernel_candidate_records(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    parsed_json = _extract_json_payload(text)
    warnings: list[str] = []
    if isinstance(parsed_json, dict):
        raw_candidates = parsed_json.get("candidates") or parsed_json.get("releases") or parsed_json.get("versions")
        if isinstance(raw_candidates, list):
            return [dict(item) for item in raw_candidates if isinstance(item, dict)], warnings
        if any(field in parsed_json for field in ("version", "tag_name", "release", "name")):
            return [parsed_json], warnings
    if isinstance(parsed_json, list):
        candidates = [dict(item) for item in parsed_json if isinstance(item, dict)]
        if candidates:
            return candidates, warnings
    line_candidates = _parse_line_candidates(text)
    if not line_candidates:
        warnings.append("no_codex_kernel_candidates_parsed")
    return line_candidates, warnings


def _kernel_candidate_from_record(
    record: dict[str, Any],
    source: dict[str, Any],
    contract: dict[str, Any],
    *,
    source_index: int,
    candidate_index: int,
) -> dict[str, Any] | None:
    version = _candidate_version(record)
    if not version:
        return None
    release_notes = _short_optional_string(
        record.get("release_notes")
        or record.get("notes")
        or record.get("body")
        or record.get("description")
        or record.get("changelog"),
        limit=360,
    )
    warnings = _candidate_warnings(record)
    install_allowed = bool(contract["allow_install"])
    candidate = {
        "schema_version": AGENTIC_UPDATE_KERNEL_CANDIDATE_SCHEMA_VERSION,
        "kind": "codex_kernel_candidate",
        "candidate_id": f"codex-kernel-{_slug(version)}-{source_index}-{candidate_index}",
        "version": version,
        "release_date": _optional_string(record.get("release_date") or record.get("published_at") or record.get("date")),
        "platforms": _string_list(record.get("platforms") or record.get("platform") or record.get("assets")),
        "distribution": {
            "download_url": _optional_string(record.get("download_url") or record.get("asset_url") or record.get("tarball_url")),
            "install_hint": _optional_string(record.get("install_hint") or record.get("install") or record.get("command")),
            "changelog_url": _optional_string(record.get("changelog_url") or record.get("html_url") or record.get("url")),
        },
        "release_notes_excerpt": release_notes,
        "source_refs": [
            {
                "source_id": source.get("source_id"),
                "source_url": source.get("url"),
                "content_hash": source.get("content_hash"),
                "parser_strategy": source.get("parser_strategy"),
            }
        ],
        "permission_policy": {
            "install_allowed": install_allowed,
            "switch_allowed": False,
            "apply_mode": contract["apply_mode"],
        },
        "side_effect_policy": _discovery_side_effect_policy(),
        "validation_state": {
            "status": "requires_kernel_probe_and_smoke",
            "verified": False,
            "probe_evidence_paths": [],
            "smoke_evidence_paths": [],
        },
        "promotion_state": {
            "status": "blocked_until_validation",
            "recommended": False,
            "requires_manual_review": True,
        },
        "warnings": warnings,
    }
    assert_secret_free_agentic_update_payload(candidate, label="codex_kernel_candidate")
    return candidate


def _proposal_source_record(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source.get("source_id"),
        "source_url": source.get("url"),
        "trust": source.get("trust_level"),
        "channel": source.get("channel"),
        "parser_strategy": source.get("parser_strategy"),
        "content_hash": source.get("content_hash"),
        "status_label": source.get("status_label"),
        "short_excerpt": _safe_excerpt(str(source.get("excerpt") or ""), 240),
    }


def _proposal_candidate_record(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "codex_kernel_candidate",
        "candidate_id": candidate["candidate_id"],
        "version": candidate["version"],
        "release_date": candidate["release_date"],
        "platforms": list(candidate["platforms"]),
        "distribution": deepcopy(candidate["distribution"]),
        "source_refs": deepcopy(candidate["source_refs"]),
        "permission_policy": deepcopy(candidate["permission_policy"]),
        "side_effect_policy": deepcopy(candidate["side_effect_policy"]),
        "validation_state": deepcopy(candidate["validation_state"]),
        "promotion_state": deepcopy(candidate["promotion_state"]),
        "warnings": list(candidate["warnings"]),
    }


def _discovery_side_effect_policy() -> dict[str, bool]:
    return {
        "writes_official_codex_config": False,
        "writes_project_codex_files": False,
        "writes_astrabridge_runtime_config": False,
        "installs_binary": False,
        "switches_binary": False,
    }


def _fixture_for_source(fixtures: dict[str, Any], source: dict[str, Any]) -> Any:
    return fixtures.get(source["source_id"]) or fixtures.get(source["url"])


def _coerce_fixture_source(fixture: Any, source: dict[str, Any]) -> tuple[str, str, str]:
    if isinstance(fixture, str):
        return fixture, "text/plain; charset=utf-8", source["url"]
    if isinstance(fixture, bytes):
        return fixture.decode("utf-8", errors="replace"), "application/octet-stream", source["url"]
    if isinstance(fixture, dict):
        final_url = str(fixture.get("url") or fixture.get("final_url") or source["url"]).strip()
        content_type = str(fixture.get("content_type") or "application/json").strip()
        body = fixture.get("body")
        if isinstance(body, bytes):
            text = body.decode("utf-8", errors="replace")
        elif isinstance(body, str):
            text = body
        else:
            text = json.dumps(fixture, ensure_ascii=False, sort_keys=True)
        return text, content_type, final_url or source["url"]
    return json.dumps(fixture, ensure_ascii=False, sort_keys=True), "application/json", source["url"]


def _extract_json_payload(text: str) -> Any | None:
    stripped = str(text or "").strip()
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


def _parse_line_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for line in str(text or "").splitlines():
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
            if key in {"release", "tag", "tag_name", "version"}:
                record["version"] = value
            elif key in {"release_date", "published_at", "date"}:
                record["release_date"] = value
            elif key in {"platform", "platforms", "asset", "assets"}:
                record["platforms"] = _string_list(value)
            elif key in {"download_url", "asset_url", "tarball_url"}:
                record["download_url"] = value
            elif key in {"install", "install_hint", "command"}:
                record["install_hint"] = value
            elif key in {"changelog", "changelog_url", "html_url", "url"}:
                record["changelog_url"] = value
            elif key in {"notes", "release_notes", "description"}:
                record["release_notes"] = value
            else:
                record[key] = value
        if record:
            candidates.append(record)
    return candidates


def _candidate_version(record: dict[str, Any]) -> str | None:
    raw = _optional_string(record.get("version") or record.get("tag_name") or record.get("release") or record.get("name"))
    if not raw:
        return None
    return raw.removeprefix("codex-cli ").removeprefix("codex ").removeprefix("rust-v").removeprefix("v").strip() or raw


def _candidate_warnings(record: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not _optional_string(record.get("release_date") or record.get("published_at") or record.get("date")):
        warnings.append("missing_release_date")
    if not _string_list(record.get("platforms") or record.get("platform") or record.get("assets")):
        warnings.append("missing_platforms")
    if not _optional_string(record.get("download_url") or record.get("asset_url") or record.get("tarball_url")):
        warnings.append("missing_download_url")
    if not _optional_string(record.get("changelog_url") or record.get("html_url") or record.get("url")):
        warnings.append("missing_changelog_url")
    return warnings


def _required_string(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string.")
    text = value.strip()
    if not text:
        raise ValueError(f"{field} must not be empty.")
    return text


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _short_optional_string(value: Any, *, limit: int) -> str | None:
    text = _optional_string(value)
    if text is None:
        return None
    return _safe_excerpt(text, limit)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"\s*,\s*|\s*/\s*", str(value))
    items: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item or "").strip()
        if not text:
            continue
        if text not in seen:
            items.append(text)
            seen.add(text)
    return items


def _safe_excerpt(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def _positive_int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("Positive integer field must be greater than zero.")
    return parsed


def _source_id_from_url(url: str) -> str:
    return _slug(url.replace("https://", "").replace("http://", ""))


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", str(value).strip()).strip("-._")
    return slug[:96] or "candidate"
