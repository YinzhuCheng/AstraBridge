from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common import path_for_host, read_json


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
    for key, value in summary.items():
        if not key.endswith("_path"):
            continue
        path = _safe_path(workspace_root, value)
        if path is None:
            continue
        artifact_refs.append(
            {
                "artifact_type": key[: -len("_path")],
                "path": str(path),
                "relative_path": _relative_path(workspace_root, path),
                "exists": path.exists(),
                "mime_type": _mime_type(path),
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
    registry = read_json(registry_path, None)
    assets = list((registry or {}).get("assets") or []) if isinstance(registry, dict) else []
    entries: list[dict[str, Any]] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        source = _safe_path(workspace_root, item.get("source_path") or item.get("local_path"))
        if source is None:
            continue
        asset_id = str(item.get("asset_id") or source.stem)
        entries.append(
            {
                "artifact_id": asset_id,
                "capability_id": "image.generate",
                "provider_id": "yunwu",
                "model": str(item.get("model") or ""),
                "saved_at": str(item.get("created_at") or item.get("updated_at") or ""),
                "summary_path": str(registry_path),
                "relative_summary_path": _relative_path(workspace_root, registry_path),
                "artifact_refs": [
                    {
                        "artifact_type": "image",
                        "path": str(source),
                        "relative_path": _relative_path(workspace_root, source),
                        "exists": source.exists(),
                        "mime_type": _mime_type(source),
                    }
                ],
                "preview": {
                    "kind": "image",
                    "text": str(item.get("role") or item.get("label") or ""),
                    "audio_path": "",
                    "image_path": str(source),
                },
                "metadata": {
                    "asset_id": asset_id,
                    "status": str(item.get("status") or item.get("quality_status") or ""),
                    "warnings": list(item.get("warnings") or [])[:5],
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
