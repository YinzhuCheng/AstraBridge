from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common import path_for_host, read_json
from ..multimodal_result_envelope import protocol_artifact_snapshot


CAPABILITY_ARTIFACTS_SCHEMA_VERSION = "astrabridge-capability-artifacts-v1"

_CAPABILITY_DIRS = {
    "vision.analyze": "vision_analyze",
    "speech.transcribe": "speech_transcribe",
    "speech.synthesize": "speech_synthesize",
}

_PREVIEW_KEYS = {
    "vision.analyze": ("text_path",),
    "speech.transcribe": ("transcript_path",),
    "speech.synthesize": ("transcript_path",),
}


def capability_artifact_snapshot(
    workspace_root: str,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    root = path_for_host(workspace_root).resolve()
    capability_root = root / ".astrabridge" / "capabilities"
    entries: list[dict[str, Any]] = []
    for capability_id, directory in _CAPABILITY_DIRS.items():
        entries.extend(_summary_entries(root, capability_root / directory, capability_id))
    entries.extend(_image_asset_entries(root))
    entries.sort(key=lambda item: str(item.get("saved_at") or ""), reverse=True)
    limited = entries[: max(1, min(int(limit or 20), 100))]
    return {
        "schema_version": CAPABILITY_ARTIFACTS_SCHEMA_VERSION,
        "workspace_root": str(root),
        "artifacts": limited,
        "count": len(limited),
        "total_count": len(entries),
    }


def _summary_entries(workspace_root: Path, capability_dir: Path, capability_id: str) -> list[dict[str, Any]]:
    if not capability_dir.exists():
        return []
    entries: list[dict[str, Any]] = []
    for summary_path in capability_dir.glob("*/summary.json"):
        summary = read_json(summary_path, None)
        if not isinstance(summary, dict):
            continue
        entry = _entry_from_summary(workspace_root, summary_path, summary, capability_id)
        if entry:
            entries.append(entry)
    return entries


def _entry_from_summary(workspace_root: Path, summary_path: Path, summary: dict[str, Any], capability_id: str) -> dict[str, Any] | None:
    artifact_refs = []
    lineage = _artifact_lineage(capability_id, summary_path.parent.name)
    for key, value in summary.items():
        if not key.endswith("_path"):
            continue
        path = _safe_path(workspace_root, value)
        if path is None:
            continue
        artifact_type = key[: -len("_path")]
        protocol_ref = protocol_artifact_snapshot(
            workspace_root=workspace_root,
            artifact_path=path,
            artifact_id=f"{summary_path.parent.name}-{artifact_type}",
            lineage=lineage,
            media_type=_mime_type(path),
            artifact_kind=artifact_type,
        )
        artifact_refs.append(
            {
                "artifact_type": artifact_type,
                "path": str(path),
                "relative_path": _relative_path(workspace_root, path),
                "exists": path.exists(),
                "mime_type": _mime_type(path),
                "artifact_uri": str(protocol_ref.get("artifact_uri") or "") if isinstance(protocol_ref, dict) else "",
                "size_bytes": int(protocol_ref.get("size_bytes") or 0) if isinstance(protocol_ref, dict) else 0,
                "digest_sha256": str(protocol_ref.get("digest_sha256") or "") if isinstance(protocol_ref, dict) else "",
                "lineage": dict(protocol_ref.get("lineage") or {}) if isinstance(protocol_ref, dict) else {},
            }
        )
    preview_text = ""
    for key in _PREVIEW_KEYS.get(capability_id, ()):
        path = _safe_path(workspace_root, summary.get(key))
        if path and path.exists() and path.is_file():
            preview_text = _preview_text(path)
            break
    return {
        "artifact_id": summary_path.parent.name,
        "capability_id": capability_id,
        "provider_id": str(summary.get("provider_id") or ""),
        "model": str(summary.get("model") or ""),
        "saved_at": str(summary.get("saved_at") or ""),
        "summary_path": str(summary_path),
        "relative_summary_path": _relative_path(workspace_root, summary_path),
        "artifact_refs": artifact_refs,
        "preview": {
            "kind": _preview_kind(capability_id),
            "text": preview_text,
            "audio_path": _ref_path(artifact_refs, "audio"),
            "image_path": _ref_path(artifact_refs, "image"),
        },
        "metadata": _safe_summary_metadata(summary),
    }


def _image_asset_entries(workspace_root: Path) -> list[dict[str, Any]]:
    registry_path = workspace_root / ".astrabridge" / "assets" / "asset_registry.json"
    generated_manifest_path = workspace_root / ".astrabridge" / "assets" / "generated" / "asset_manifest.json"
    registry = read_json(registry_path, None)
    generated_manifest = read_json(generated_manifest_path, None)
    asset_sources: list[tuple[Path, dict[str, Any]]] = []
    if isinstance(registry, dict):
        asset_sources.extend((registry_path, item) for item in list(registry.get("assets") or []) if isinstance(item, dict))
    if isinstance(generated_manifest, dict):
        asset_sources.extend(
            (generated_manifest_path, item) for item in list(generated_manifest.get("assets") or []) if isinstance(item, dict)
        )

    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source_manifest_path, item in asset_sources:
        source = _safe_path(workspace_root, item.get("source_path") or item.get("local_path"))
        if source is None:
            continue
        asset_id = str(item.get("asset_id") or source.stem)
        key = (asset_id, str(source))
        if key in seen:
            continue
        seen.add(key)
        lineage = _artifact_lineage("image.generate", asset_id)
        protocol_ref = protocol_artifact_snapshot(
            workspace_root=workspace_root,
            artifact_path=source,
            artifact_id=asset_id,
            lineage=lineage,
            media_type=_mime_type(source),
            artifact_kind="image",
        )
        entries.append(
            {
                "artifact_id": asset_id,
                "capability_id": "image.generate",
                "provider_id": str(item.get("provider") or "yunwu"),
                "model": str(item.get("model") or ""),
                "saved_at": str(item.get("generated_at") or item.get("created_at") or item.get("updated_at") or ""),
                "summary_path": str(source_manifest_path),
                "relative_summary_path": _relative_path(workspace_root, source_manifest_path),
                "artifact_refs": [
                    {
                        "artifact_type": "image",
                        "path": str(source),
                        "relative_path": _relative_path(workspace_root, source),
                        "exists": source.exists(),
                        "mime_type": _mime_type(source),
                        "artifact_uri": str(protocol_ref.get("artifact_uri") or "") if isinstance(protocol_ref, dict) else "",
                        "size_bytes": int(protocol_ref.get("size_bytes") or 0) if isinstance(protocol_ref, dict) else 0,
                        "digest_sha256": str(protocol_ref.get("digest_sha256") or "") if isinstance(protocol_ref, dict) else "",
                        "lineage": dict(protocol_ref.get("lineage") or {}) if isinstance(protocol_ref, dict) else {},
                    }
                ],
                "preview": {
                    "kind": "image",
                    "text": str(item.get("role") or item.get("label") or item.get("purpose") or ""),
                    "audio_path": "",
                    "image_path": str(source),
                },
                "metadata": {
                    "asset_id": asset_id,
                    "status": str(item.get("status") or item.get("quality_status") or ""),
                    "tool": str(item.get("tool") or ""),
                    "quality": str(item.get("quality") or ""),
                    "transparency_status": str(item.get("transparency_status") or ""),
                    "warnings": list(item.get("warnings") or item.get("validation_warnings") or [])[:5],
                },
            }
        )
    return entries


def _safe_summary_metadata(summary: dict[str, Any]) -> dict[str, Any]:
    blocked_suffixes = ("_path",)
    blocked_keys = {"request", "response", "json", "body", "headers", "authorization", "api_key", "token"}
    safe: dict[str, Any] = {}
    for key, value in summary.items():
        key_text = str(key)
        if key_text.endswith(blocked_suffixes) or key_text.lower() in blocked_keys:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key_text] = value
    return safe


def _safe_path(workspace_root: Path, raw: Any) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        path = path_for_host(text).resolve()
        path.relative_to(workspace_root)
        return path
    except Exception:
        return None


def _relative_path(workspace_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root))
    except Exception:
        return str(path)


def _preview_text(path: Path, *, limit: int = 280) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text.strip().replace("\r\n", "\n")[:limit]


def _preview_kind(capability_id: str) -> str:
    if capability_id == "speech.synthesize":
        return "audio"
    if capability_id in {"speech.transcribe", "vision.analyze"}:
        return "text"
    return "json"


def _ref_path(refs: list[dict[str, Any]], artifact_type: str) -> str:
    for item in refs:
        if str(item.get("artifact_type") or "") == artifact_type:
            return str(item.get("path") or "")
    return ""


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return f"image/{'jpeg' if suffix in {'.jpg', '.jpeg'} else suffix.lstrip('.')}"
    if suffix in {".wav", ".mp3", ".ogg"}:
        return f"audio/{suffix.lstrip('.')}"
    if suffix == ".json":
        return "application/json"
    if suffix == ".txt":
        return "text/plain"
    return "application/octet-stream"


def _artifact_lineage(capability_id: str, run_id: str) -> dict[str, Any]:
    return {
        "task_id": f"capability.{capability_id}",
        "run_id": str(run_id or "artifact"),
        "source_node_id": f"capability.{capability_id}",
    }
