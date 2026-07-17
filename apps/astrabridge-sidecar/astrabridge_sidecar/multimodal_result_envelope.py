from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any

from .common import new_id, now_iso, path_for_host
from .protocol.generated.v1 import SCHEMA_VERSION, validate_protocol_payload


MCP_TYPED_RESULT_SCHEMA_VERSION = "astrabridge-mcp-tool-result-v1"
INLINE_TEXT_PREVIEW_LIMIT = 1200
_WORKSPACE_ARTIFACT_PREFIXES = (".astrabridge/", "PRIVATE/")
_IMAGE_ARTIFACT_TYPES = {"image", "asset", "generated", "persisted_asset"}
_OUTPUT_ARTIFACT_TYPES_BY_CAPABILITY = {
    "vision.analyze": {"text"},
    "speech.transcribe": {"transcript"},
    "speech.synthesize": {"audio", "transcript"},
}
_DIAGNOSTIC_ARTIFACT_TYPES = {"request", "response", "summary", "sse", "manifest"}


def enrich_capability_result(
    capability_id: str,
    result: dict[str, Any],
    *,
    workspace_root: str | Path | None,
    request_id: str | None = None,
) -> dict[str, Any]:
    clean_capability_id = str(capability_id or "").strip()
    if not clean_capability_id or not isinstance(result, dict):
        return result
    workspace = _workspace_root_path(workspace_root)
    typed_request_id = _identifier(request_id or result.get("response_id") or new_id(f"{clean_capability_id.replace('.', '-')}"))
    lineage = _lineage_for_result(clean_capability_id, typed_request_id)
    created_at = str(result.get("created_at") or now_iso())
    output_refs, diagnostic_refs = _capability_protocol_artifact_refs(clean_capability_id, result, workspace, lineage=lineage)
    content_parts = _capability_content_parts(clean_capability_id, result, output_refs)
    safe_output = _capability_safe_output(clean_capability_id, result, output_refs, diagnostic_refs, content_parts)
    inline_policy = _externalize_large_inline_fields(result, output_refs)
    capability_output = validate_protocol_payload(
        "CapabilityOutput",
        {
            "capability_id": clean_capability_id,
            "schema_version": SCHEMA_VERSION,
            "request_id": typed_request_id,
            "status": _capability_status_for_result(result, output_refs),
            "output": safe_output,
            "artifact_refs": output_refs,
            "diagnostic_refs": diagnostic_refs,
            "content_parts": content_parts,
            "inline_policy": inline_policy,
            "created_at": created_at,
        },
    )
    result["protocol_artifact_refs"] = output_refs
    result["diagnostic_refs"] = diagnostic_refs
    result["content_parts"] = content_parts
    result["inline_policy"] = inline_policy
    result["capability_output"] = capability_output
    result["typed_result"] = {
        "schema_version": MCP_TYPED_RESULT_SCHEMA_VERSION,
        "request_id": typed_request_id,
        "tool": f"astrabridge_capability_{clean_capability_id.replace('.', '_')}",
        "result_kind": "capability",
        "capability_id": clean_capability_id,
        "status": capability_output["status"],
        "artifact_refs": output_refs,
        "diagnostic_refs": diagnostic_refs,
        "content_parts": content_parts,
        "summary": safe_output,
        "created_at": created_at,
        "output_schema": "CapabilityOutput",
        "inline_policy": inline_policy,
    }
    return result


def enrich_yunwu_image_result(
    tool_name: str,
    result: dict[str, Any],
    *,
    workspace_root: str | Path | None,
    request_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        return result
    workspace = _workspace_root_path(workspace_root)
    typed_request_id = _identifier(request_id or new_id("yunwu-image"))
    lineage = _lineage_for_result("image.generate", typed_request_id, source_node_id="tool.yunwu_image")
    output_refs = _image_protocol_artifact_refs(result, workspace, lineage=lineage)
    diagnostic_refs = _diagnostic_protocol_artifact_refs(
        [
            {
                "artifact_type": "manifest",
                "path": result.get("asset_manifest_path"),
                "mime_type": "application/json",
            }
        ],
        workspace,
        lineage=lineage,
    )
    content_parts = _image_content_parts(result, output_refs)
    inline_policy = {
        "max_inline_text_chars": INLINE_TEXT_PREVIEW_LIMIT,
        "externalized_fields": ["asset_manifest_path", "persisted_assets"] if output_refs or diagnostic_refs else [],
        "truncated_fields": [],
    }
    safe_output = {
        "tool": str(tool_name or "").strip(),
        "requested_n": int(result.get("requested_n") or 0),
        "actual_n": int(result.get("actual_n") or len(output_refs)),
        "count_mismatch": bool(result.get("count_mismatch", False)),
        "media_types": sorted({str(item.get("media_type") or "") for item in output_refs if str(item.get("media_type") or "").strip()}),
        "artifact_count": len(output_refs),
    }
    result["protocol_artifact_refs"] = output_refs
    result["diagnostic_refs"] = diagnostic_refs
    result["content_parts"] = content_parts
    result["inline_policy"] = inline_policy
    result["typed_result"] = {
        "schema_version": MCP_TYPED_RESULT_SCHEMA_VERSION,
        "request_id": typed_request_id,
        "tool": str(tool_name or "").strip(),
        "result_kind": "image_generation",
        "status": "partial" if bool(result.get("count_mismatch", False)) else "ok",
        "artifact_refs": output_refs,
        "diagnostic_refs": diagnostic_refs,
        "content_parts": content_parts,
        "summary": safe_output,
        "created_at": now_iso(),
        "inline_policy": inline_policy,
    }
    return result


def enrich_web_result(
    tool_name: str,
    result: dict[str, Any],
    *,
    workspace_root: str | Path | None,
    record_path: str | Path | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        return result
    workspace = _workspace_root_path(workspace_root)
    typed_request_id = _identifier(request_id or new_id("web-result"))
    lineage = _lineage_for_result("web.search", typed_request_id, source_node_id="tool.astrabridge_web")
    output_refs: list[dict[str, Any]] = []
    if record_path:
        artifact = _protocol_artifact_ref_for_path(
            record_path,
            workspace_root=workspace,
            artifact_id=_identifier(Path(str(record_path)).stem or f"{tool_name}-record"),
            lineage=lineage,
            media_type="application/json",
            artifact_kind="record",
        )
        if artifact is not None:
            output_refs.append(artifact)
    summary = _web_safe_output(tool_name, result)
    summary_json = validate_protocol_payload(
        "ContentPart",
        {
            "part_id": _identifier(f"{typed_request_id}.summary"),
            "kind": "json",
            "mime_type": "application/json",
            "data": summary,
            "metadata": {"part_type": "web_summary"},
        },
    )
    result["protocol_artifact_refs"] = output_refs
    result["diagnostic_refs"] = []
    result["content_parts"] = [summary_json]
    result["inline_policy"] = {
        "max_inline_text_chars": INLINE_TEXT_PREVIEW_LIMIT,
        "externalized_fields": ["record_path"] if output_refs else [],
        "truncated_fields": [],
    }
    result["typed_result"] = {
        "schema_version": MCP_TYPED_RESULT_SCHEMA_VERSION,
        "request_id": typed_request_id,
        "tool": str(tool_name or "").strip(),
        "result_kind": "web_search",
        "status": "ok",
        "artifact_refs": output_refs,
        "diagnostic_refs": [],
        "content_parts": [summary_json],
        "summary": summary,
        "created_at": now_iso(),
        "inline_policy": dict(result["inline_policy"]),
    }
    return result


def protocol_artifact_snapshot(
    *,
    workspace_root: str | Path,
    artifact_path: str | Path,
    artifact_id: str,
    lineage: dict[str, Any],
    media_type: str,
    artifact_kind: str,
) -> dict[str, Any] | None:
    return _protocol_artifact_ref_for_path(
        artifact_path,
        workspace_root=_workspace_root_path(workspace_root),
        artifact_id=_identifier(artifact_id),
        lineage=lineage,
        media_type=media_type,
        artifact_kind=artifact_kind,
    )


def typed_result_text_summary(payload: dict[str, Any], *, title: str) -> str:
    typed_result = dict(payload.get("typed_result") or {})
    lines = [title]
    if typed_result:
        lines.append(json.dumps(typed_result.get("summary") or {}, ensure_ascii=False, indent=2))
        artifact_refs = [dict(item) for item in list(typed_result.get("artifact_refs") or []) if isinstance(item, dict)]
        diagnostic_refs = [dict(item) for item in list(typed_result.get("diagnostic_refs") or []) if isinstance(item, dict)]
        if artifact_refs:
            lines.append("")
            lines.append("Artifacts:")
            for item in artifact_refs[:8]:
                uri = str(item.get("artifact_uri") or dict(item.get("metadata") or {}).get("relative_path") or "").strip()
                media_type = str(item.get("media_type") or "application/octet-stream").strip()
                size_text = _format_size(int(item.get("size_bytes") or 0))
                digest_text = _compact_digest(str(item.get("digest_sha256") or ""))
                detail = " · ".join(part for part in (media_type, size_text, digest_text) if part)
                lines.append(f"- {uri}" + (f" ({detail})" if detail else ""))
        if diagnostic_refs:
            lines.append("")
            lines.append("Diagnostics:")
            for item in diagnostic_refs[:8]:
                uri = str(item.get("artifact_uri") or dict(item.get("metadata") or {}).get("relative_path") or "").strip()
                if uri:
                    lines.append(f"- {uri}")
        return "\n".join(lines)
    lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def _capability_protocol_artifact_refs(
    capability_id: str,
    result: dict[str, Any],
    workspace_root: Path | None,
    *,
    lineage: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if capability_id == "image.generate":
        return _image_protocol_artifact_refs(result, workspace_root, lineage=lineage), _diagnostic_protocol_artifact_refs(
            [{"artifact_type": "manifest", "path": result.get("asset_manifest_path"), "mime_type": "application/json"}],
            workspace_root,
            lineage=lineage,
        )
    refs = [dict(item) for item in list(result.get("artifact_refs") or []) if isinstance(item, dict)]
    output_types = _OUTPUT_ARTIFACT_TYPES_BY_CAPABILITY.get(capability_id, set())
    output_refs = _legacy_protocol_artifact_refs(
        refs,
        workspace_root,
        lineage=lineage,
        include_types=output_types if output_types else None,
    )
    diagnostic_refs = _diagnostic_protocol_artifact_refs(refs, workspace_root, lineage=lineage)
    return output_refs, diagnostic_refs


def _image_protocol_artifact_refs(
    result: dict[str, Any],
    workspace_root: Path | None,
    *,
    lineage: dict[str, Any],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    persisted_assets = [dict(item) for item in list(result.get("persisted_assets") or []) if isinstance(item, dict)]
    if persisted_assets:
        for index, item in enumerate(persisted_assets, start=1):
            artifact = _protocol_artifact_ref_for_path(
                item.get("local_path"),
                workspace_root=workspace_root,
                artifact_id=_identifier(str(item.get("asset_id") or f"image-artifact-{index}")),
                lineage=lineage,
                media_type=str(item.get("mime_type") or _media_type_for_path(item.get("local_path"), default="image/png")),
                artifact_kind="image",
                metadata={
                    "relative_path": _safe_relative_path(workspace_root, item.get("local_path")),
                    "actual_width": item.get("actual_width"),
                    "actual_height": item.get("actual_height"),
                    "actual_format": item.get("actual_format"),
                    "has_alpha": item.get("has_alpha"),
                    "transparency_status": item.get("transparency_status"),
                },
            )
            if artifact is not None:
                refs.append(artifact)
    if refs:
        return refs
    for index, item in enumerate(list(result.get("artifact_refs") or []), start=1):
        if not isinstance(item, dict):
            continue
        artifact = _protocol_artifact_ref_for_path(
            item.get("local_path") or item.get("path"),
            workspace_root=workspace_root,
            artifact_id=_identifier(str(item.get("asset_id") or f"image-artifact-{index}")),
            lineage=lineage,
            media_type=_media_type_for_path(item.get("local_path") or item.get("path"), default="image/png"),
            artifact_kind="image",
            metadata={
                "relative_path": _safe_relative_path(workspace_root, item.get("local_path") or item.get("path")),
                "result_index": item.get("result_index"),
                "actual_width": item.get("actual_width"),
                "actual_height": item.get("actual_height"),
                "actual_format": item.get("actual_format"),
                "validation_warnings": list(item.get("validation_warnings") or []),
            },
        )
        if artifact is not None:
            refs.append(artifact)
    return refs


def _legacy_protocol_artifact_refs(
    refs: list[dict[str, Any]],
    workspace_root: Path | None,
    *,
    lineage: dict[str, Any],
    include_types: set[str] | None = None,
) -> list[dict[str, Any]]:
    protocol_refs: list[dict[str, Any]] = []
    for index, item in enumerate(refs, start=1):
        artifact_type = str(item.get("artifact_type") or "").strip().lower()
        if include_types is not None and artifact_type not in include_types:
            continue
        candidate_path = item.get("path") or item.get("local_path")
        artifact = _protocol_artifact_ref_for_path(
            candidate_path,
            workspace_root=workspace_root,
            artifact_id=_identifier(f"{artifact_type or 'artifact'}-{index}"),
            lineage=lineage,
            media_type=str(item.get("media_type") or item.get("mime_type") or _media_type_for_path(candidate_path)).strip(),
            artifact_kind=artifact_type or "artifact",
            metadata={
                "relative_path": _safe_relative_path(workspace_root, candidate_path),
                "artifact_type": artifact_type or None,
            },
        )
        if artifact is not None:
            protocol_refs.append(artifact)
    return protocol_refs


def _diagnostic_protocol_artifact_refs(
    refs: list[dict[str, Any]],
    workspace_root: Path | None,
    *,
    lineage: dict[str, Any],
) -> list[dict[str, Any]]:
    diagnostic_refs: list[dict[str, Any]] = []
    for index, item in enumerate(refs, start=1):
        artifact_type = str(item.get("artifact_type") or "").strip().lower()
        if artifact_type not in _DIAGNOSTIC_ARTIFACT_TYPES:
            continue
        candidate_path = item.get("path") or item.get("local_path")
        artifact = _protocol_artifact_ref_for_path(
            candidate_path,
            workspace_root=workspace_root,
            artifact_id=_identifier(f"{artifact_type or 'diagnostic'}-{index}"),
            lineage=lineage,
            media_type=str(item.get("media_type") or item.get("mime_type") or _media_type_for_path(candidate_path)).strip(),
            artifact_kind=artifact_type or "diagnostic",
            metadata={
                "relative_path": _safe_relative_path(workspace_root, candidate_path),
                "artifact_type": artifact_type or None,
            },
        )
        if artifact is not None:
            diagnostic_refs.append(artifact)
    return diagnostic_refs


def _capability_content_parts(capability_id: str, result: dict[str, Any], artifact_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if capability_id == "image.generate":
        return _image_content_parts(result, artifact_refs)
    parts: list[dict[str, Any]] = []
    text_value = _clean_text(result.get("text"))
    if text_value:
        bounded_text, truncated = _bounded_text(text_value)
        parts.append(
            validate_protocol_payload(
                "ContentPart",
                {
                    "part_id": _identifier(f"{capability_id}.text"),
                    "kind": "text",
                    "mime_type": "text/plain",
                    "text": bounded_text,
                    "metadata": {"truncated": truncated, "part_type": "text_preview"},
                },
            )
        )
    for index, artifact in enumerate(artifact_refs, start=1):
        parts.append(_artifact_content_part(artifact, part_id=f"{capability_id}.artifact.{index}"))
    return parts


def _image_content_parts(result: dict[str, Any], artifact_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    revised_prompt = _clean_text(result.get("revised_prompt"))
    if revised_prompt:
        bounded_text, truncated = _bounded_text(revised_prompt)
        parts.append(
            validate_protocol_payload(
                "ContentPart",
                {
                    "part_id": _identifier("image.generate.revised_prompt"),
                    "kind": "text",
                    "mime_type": "text/plain",
                    "text": bounded_text,
                    "metadata": {"truncated": truncated, "part_type": "revised_prompt"},
                },
            )
        )
    for index, artifact in enumerate(artifact_refs, start=1):
        parts.append(_artifact_content_part(artifact, part_id=f"image.generate.artifact.{index}"))
    return parts


def _artifact_content_part(artifact: dict[str, Any], *, part_id: str) -> dict[str, Any]:
    media_type = str(artifact.get("media_type") or "application/octet-stream").strip()
    primary_kind = media_type.split("/", 1)[0].lower()
    part_kind = "artifact"
    if primary_kind == "image":
        part_kind = "image"
    elif primary_kind == "audio":
        part_kind = "audio"
    elif primary_kind == "video":
        part_kind = "video"
    elif media_type in {"application/pdf", "text/markdown", "text/plain"}:
        part_kind = "document"
    return validate_protocol_payload(
        "ContentPart",
        {
            "part_id": _identifier(part_id),
            "kind": part_kind,
            "mime_type": media_type,
            "artifact": artifact,
            "metadata": {
                "artifact_uri": artifact.get("artifact_uri"),
                "relative_path": dict(artifact.get("metadata") or {}).get("relative_path"),
            },
        },
    )


def _capability_safe_output(
    capability_id: str,
    result: dict[str, Any],
    artifact_refs: list[dict[str, Any]],
    diagnostic_refs: list[dict[str, Any]],
    content_parts: list[dict[str, Any]],
) -> dict[str, Any]:
    if capability_id == "image.generate":
        return {
            "provider_id": str(result.get("provider_id") or ""),
            "model": str(result.get("model") or ""),
            "operation": str(result.get("operation") or "generate"),
            "requested_n": int(result.get("requested_n") or 0),
            "actual_n": int(result.get("actual_n") or len(artifact_refs)),
            "count_mismatch": bool(result.get("count_mismatch", False)),
            "revised_prompt": _clean_text(result.get("revised_prompt")),
            "artifact_count": len(artifact_refs),
            "diagnostic_count": len(diagnostic_refs),
            "content_part_count": len(content_parts),
        }
    if capability_id == "vision.analyze":
        bounded_text, truncated = _bounded_text(_clean_text(result.get("text")))
        return {
            "provider_id": str(result.get("provider_id") or ""),
            "model": str(result.get("model") or ""),
            "text_preview": bounded_text,
            "text_truncated": truncated,
            "image_input_count": int(result.get("image_input_count") or 0),
            "detail": str(result.get("detail") or ""),
            "artifact_count": len(artifact_refs),
            "diagnostic_count": len(diagnostic_refs),
        }
    if capability_id == "speech.transcribe":
        bounded_text, truncated = _bounded_text(_clean_text(result.get("text")))
        return {
            "provider_id": str(result.get("provider_id") or ""),
            "model": str(result.get("model") or ""),
            "text_preview": bounded_text,
            "text_truncated": truncated,
            "language": str(result.get("language") or ""),
            "audio_input_count": int(result.get("audio_input_count") or 0),
            "artifact_count": len(artifact_refs),
            "diagnostic_count": len(diagnostic_refs),
        }
    bounded_text, truncated = _bounded_text(_clean_text(result.get("text")))
    return {
        "provider_id": str(result.get("provider_id") or ""),
        "model": str(result.get("model") or ""),
        "text_preview": bounded_text,
        "text_truncated": truncated,
        "mime_type": str(result.get("mime_type") or ""),
        "audio_format": str(result.get("audio_format") or ""),
        "duration_sec": result.get("duration_sec"),
        "artifact_count": len(artifact_refs),
        "diagnostic_count": len(diagnostic_refs),
    }


def _web_safe_output(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "astrabridge_web_search_batch":
        merged_results = [dict(item) for item in list(result.get("merged_results") or []) if isinstance(item, dict)]
        return {
            "tool": tool_name,
            "query_count": int(result.get("query_count") or 0),
            "result_count": int(result.get("result_count") or len(merged_results)),
            "results": [
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("url") or ""),
                    "query": str(item.get("query") or ""),
                }
                for item in merged_results[:5]
            ],
        }
    if tool_name == "astrabridge_web_search":
        merged_results = [dict(item) for item in list(result.get("merged_results") or []) if isinstance(item, dict)]
        return {
            "tool": tool_name,
            "result_count": len(merged_results),
            "results": [
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("url") or ""),
                }
                for item in merged_results[:5]
            ],
        }
    if tool_name == "astrabridge_web_fetch":
        bounded_text, truncated = _bounded_text(_clean_text(result.get("text")))
        return {
            "tool": tool_name,
            "url": str(result.get("url") or ""),
            "content_type": str(result.get("content_type") or ""),
            "text_preview": bounded_text,
            "text_truncated": truncated or bool(result.get("truncated")),
            "char_count": int(result.get("char_count") or 0),
            "status_code": result.get("status_code"),
        }
    sources = [dict(item) for item in list(result.get("sources") or []) if isinstance(item, dict)]
    failures = [dict(item) for item in list(result.get("failures") or []) if isinstance(item, dict)]
    return {
        "tool": tool_name,
        "research_goal": _clean_text(result.get("research_goal")),
        "source_count": int(result.get("source_count") or len(sources)),
        "fetched_source_count": int(result.get("fetched_source_count") or 0),
        "failure_count": len(failures),
        "sources": [
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "source_origin": str(item.get("source_origin") or ""),
                "fetch_ok": bool(item.get("fetch_ok", True)),
            }
            for item in sources[:6]
        ],
    }


def _capability_status_for_result(result: dict[str, Any], artifact_refs: list[dict[str, Any]]) -> str:
    if bool(result.get("count_mismatch", False)):
        return "partial"
    if not artifact_refs and str(result.get("capability_id") or "").strip() == "image.generate":
        return "partial"
    return "ok"


def _externalize_large_inline_fields(result: dict[str, Any], artifact_refs: list[dict[str, Any]]) -> dict[str, Any]:
    externalized_fields: list[str] = []
    truncated_fields: list[str] = []
    audio_base64 = _clean_text(result.get("audio_bytes_base64"))
    if audio_base64:
        result["audio_bytes_base64_present"] = True
        if artifact_refs or len(audio_base64) > INLINE_TEXT_PREVIEW_LIMIT:
            result.pop("audio_bytes_base64", None)
            externalized_fields.append("audio_bytes_base64")
    text = _clean_text(result.get("text"))
    if text and len(text) > INLINE_TEXT_PREVIEW_LIMIT:
        truncated_fields.append("text")
    return {
        "max_inline_text_chars": INLINE_TEXT_PREVIEW_LIMIT,
        "externalized_fields": externalized_fields,
        "truncated_fields": truncated_fields,
    }


def _protocol_artifact_ref_for_path(
    raw_path: Any,
    *,
    workspace_root: Path | None,
    artifact_id: str,
    lineage: dict[str, Any],
    media_type: str,
    artifact_kind: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if workspace_root is None:
        return None
    path = _safe_workspace_path(workspace_root, raw_path)
    if path is None or not path.exists() or not path.is_file():
        return None
    relative_path = _safe_relative_path(workspace_root, path)
    if not relative_path:
        return None
    artifact = {
        "artifact_id": _identifier(artifact_id or path.stem or "artifact"),
        "artifact_uri": f"workspace://{relative_path}",
        "media_type": str(media_type or _media_type_for_path(path)).strip() or "application/octet-stream",
        "status": "ready",
        "lineage": dict(lineage),
        "size_bytes": int(path.stat().st_size),
        "digest_sha256": _sha256_file(path),
        "metadata": {
            "relative_path": relative_path,
            "artifact_kind": str(artifact_kind or "artifact").strip() or "artifact",
            **{key: value for key, value in dict(metadata or {}).items() if value is not None and value != ""},
        },
    }
    return validate_protocol_payload("ArtifactRef", artifact)


def _safe_workspace_path(workspace_root: Path, raw_path: Any) -> Path | None:
    text = str(raw_path or "").strip()
    if not text:
        return None
    try:
        path = path_for_host(text).resolve()
        relative = path.relative_to(workspace_root)
    except Exception:
        return None
    normalized = str(relative).replace("\\", "/").strip()
    if not normalized or not normalized.startswith(_WORKSPACE_ARTIFACT_PREFIXES):
        return None
    return path


def _safe_relative_path(workspace_root: Path | None, raw_path: Any) -> str:
    if workspace_root is None:
        return ""
    path = _safe_workspace_path(workspace_root, raw_path)
    if path is None:
        return ""
    return str(path.relative_to(workspace_root)).replace("\\", "/")


def _workspace_root_path(workspace_root: str | Path | None) -> Path | None:
    text = str(workspace_root or "").strip()
    if not text:
        return None
    try:
        return path_for_host(text).resolve()
    except Exception:
        return None


def _lineage_for_result(capability_id: str, request_id: str, *, source_node_id: str | None = None) -> dict[str, Any]:
    clean_capability_id = str(capability_id or "").strip() or "artifact"
    return {
        "task_id": _identifier(f"capability.{clean_capability_id}"),
        "run_id": _identifier(request_id),
        "source_node_id": _identifier(source_node_id or f"capability.{clean_capability_id}"),
    }


def _identifier(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "artifact"
    cleaned = []
    for char in text:
        cleaned.append(char if char.isalnum() or char in {".", "_", ":", "-"} else "-")
    compact = "".join(cleaned).strip(".:_-") or "artifact"
    if not compact[0].isalnum():
        compact = f"artifact-{compact}"
    return compact[:128]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_text(value: str, limit: int = INLINE_TEXT_PREVIEW_LIMIT) -> tuple[str, bool]:
    text = _clean_text(value)
    if len(text) <= limit:
        return text, False
    return text[: max(0, limit - 1)].rstrip() + "…", True


def _format_size(value: int) -> str:
    if value <= 0:
        return ""
    units = ["B", "KB", "MB", "GB"]
    amount = float(value)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if amount < 1024 or candidate == units[-1]:
            break
        amount /= 1024
    if unit == "B":
        return f"{int(amount)} {unit}"
    return f"{amount:.1f} {unit}"


def _compact_digest(value: str) -> str:
    digest = _clean_text(value)
    if not digest:
        return ""
    return f"sha256:{digest[:12]}"


def _media_type_for_path(raw_path: Any, *, default: str = "application/octet-stream") -> str:
    text = str(raw_path or "").strip()
    if not text:
        return default
    guessed, _encoding = mimetypes.guess_type(text)
    return guessed or default


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
