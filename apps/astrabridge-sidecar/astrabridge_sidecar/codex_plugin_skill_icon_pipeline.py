from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


OFFICIAL_ICON_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "plugins": {},
    "skills": {},
}

_REMOTE_RASTER_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_LOCAL_MANIFEST_MIME_BY_SUFFIX = dict(_REMOTE_RASTER_MIME_BY_SUFFIX)
_CURATED_LOCAL_MIME_BY_SUFFIX = {
    **_REMOTE_RASTER_MIME_BY_SUFFIX,
    ".svg": "image/svg+xml",
}
_OFFICIAL_REMOTE_HOSTS = {
    "openai.com",
    "cdn.openai.com",
    "github.com",
    "raw.githubusercontent.com",
    "githubusercontent.com",
}
_HEX_COLOR_RE = re.compile(r"^#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def resolve_plugin_icon_metadata(
    *,
    plugin: dict[str, Any],
    source_catalog: dict[str, Any] | None,
    runtime_roots: dict[str, Any] | None,
    search_roots: list[Path] | None,
    official_overrides: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    plugin_id = _clean_text(plugin.get("plugin_id") or plugin.get("plugin_name"))
    display_name = _clean_text(plugin.get("display_name") or plugin_id)
    base_root = _plugin_root(plugin)
    return _resolve_registry_icon(
        record_kind="plugin",
        record_key=plugin_id,
        display_name=display_name or "Plugin",
        source_catalog=source_catalog,
        runtime_roots=runtime_roots,
        search_roots=search_roots,
        base_root=base_root,
        local_path_candidates=[
            plugin.get("logo"),
            plugin.get("composer_icon"),
            plugin.get("icon_path"),
        ],
        remote_url_candidates=[
            plugin.get("logo_url"),
            plugin.get("composer_icon_url"),
            plugin.get("icon_url"),
        ],
        brand_color=plugin.get("brand_color"),
        official_overrides=official_overrides,
    )


def resolve_skill_icon_metadata(
    *,
    skill: dict[str, Any],
    source_catalog: dict[str, Any] | None,
    runtime_roots: dict[str, Any] | None,
    search_roots: list[Path] | None,
    official_overrides: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    skill_name = _clean_text(skill.get("skill_name"))
    display_name = _clean_text(skill.get("display_name") or skill_name)
    path = _clean_text(skill.get("path"))
    base_root = Path(path).resolve().parent if path else None
    return _resolve_registry_icon(
        record_kind="skill",
        record_key=skill_name,
        display_name=display_name or "Skill",
        source_catalog=source_catalog,
        runtime_roots=runtime_roots,
        search_roots=search_roots,
        base_root=base_root,
        local_path_candidates=[
            skill.get("icon_large"),
            skill.get("icon_small"),
            skill.get("icon_path"),
        ],
        remote_url_candidates=[
            skill.get("icon_url"),
        ],
        brand_color=skill.get("brand_color"),
        official_overrides=official_overrides,
    )


def _resolve_registry_icon(
    *,
    record_kind: str,
    record_key: str,
    display_name: str,
    source_catalog: dict[str, Any] | None,
    runtime_roots: dict[str, Any] | None,
    search_roots: list[Path] | None,
    base_root: Path | None,
    local_path_candidates: list[Any],
    remote_url_candidates: list[Any],
    brand_color: Any,
    official_overrides: dict[str, dict[str, dict[str, Any]]] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    warnings: list[dict[str, Any]] = []
    notes: list[str] = []
    override = _official_override((official_overrides or OFFICIAL_ICON_OVERRIDES), record_kind, record_key)
    trusted_roots = _trusted_roots(runtime_roots, search_roots, base_root)

    if override is not None:
        icon, override_warnings, override_notes = _official_override_icon(
            override=override,
            display_name=display_name,
            source_catalog=source_catalog,
        )
        warnings.extend(override_warnings)
        notes.extend(override_notes)
        if icon is not None:
            return icon, warnings, notes

    local_icon, local_warnings, local_notes = _local_manifest_icon(
        candidates=local_path_candidates,
        display_name=display_name,
        base_root=base_root,
        trusted_roots=trusted_roots,
    )
    warnings.extend(local_warnings)
    notes.extend(local_notes)
    if local_icon is not None:
        return local_icon, warnings, notes

    official_icon, official_warnings, official_notes = _official_remote_icon(
        candidates=remote_url_candidates,
        display_name=display_name,
        source_catalog=source_catalog,
    )
    warnings.extend(official_warnings)
    notes.extend(official_notes)
    if official_icon is not None:
        return official_icon, warnings, notes

    fallback_icon = _generated_fallback_icon(
        record_kind=record_kind,
        record_key=record_key,
        display_name=display_name,
        runtime_roots=runtime_roots,
        brand_color=brand_color,
    )
    warnings.append(
        {
            "code": "icon-missing",
            "severity": "info",
            "message": "No approved official or safe local icon was found. Using an AstraBridge-generated fallback icon.",
            "field": "icon",
        }
    )
    notes.append("icon_provenance:generated_fallback")
    return fallback_icon, warnings, notes


def _official_override_icon(
    *,
    override: dict[str, Any],
    display_name: str,
    source_catalog: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    warnings: list[dict[str, Any]] = []
    notes = ["icon_override:official"]
    asset_path = _clean_text(override.get("asset_path"))
    asset_url = _clean_text(override.get("asset_url"))
    label = _clean_text(override.get("label") or display_name) or display_name
    if asset_path:
        metadata, error = _validated_local_icon(
            candidate=asset_path,
            display_name=label,
            base_root=Path(__file__).resolve().parents[2],
            trusted_roots=[],
            mime_by_suffix=_CURATED_LOCAL_MIME_BY_SUFFIX,
            provenance_kind="official",
            allow_trusted_outside_roots=True,
        )
        if metadata is not None:
            metadata["notes"] = list(dict.fromkeys(["licensed_or_curated_official_asset", *notes]))
            return metadata, warnings, metadata["notes"]
        warnings.append(
            {
                "code": "icon-official-asset-invalid",
                "severity": "warning",
                "message": error or "Official icon override could not be validated.",
                "field": "icon.asset_path",
            }
        )
    if asset_url:
        metadata, error = _validated_remote_icon_url(
            candidate=asset_url,
            display_name=label,
            source_catalog=source_catalog,
            provenance_kind="official",
            catalog_hosts=_allowed_official_hosts(source_catalog),
        )
        if metadata is not None:
            metadata["notes"] = list(dict.fromkeys(["licensed_or_curated_official_asset", *notes]))
            return metadata, warnings, metadata["notes"]
        warnings.append(
            {
                "code": "icon-official-url-invalid",
                "severity": "warning",
                "message": error or "Official icon override URL could not be validated.",
                "field": "icon.asset_url",
            }
        )
    return None, warnings, notes


def _local_manifest_icon(
    *,
    candidates: list[Any],
    display_name: str,
    base_root: Path | None,
    trusted_roots: list[Path],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    warnings: list[dict[str, Any]] = []
    notes: list[str] = []
    for candidate in candidates:
        text = _clean_text(candidate)
        if not text:
            continue
        metadata, error = _validated_local_icon(
            candidate=text,
            display_name=display_name,
            base_root=base_root,
            trusted_roots=trusted_roots,
            mime_by_suffix=_LOCAL_MANIFEST_MIME_BY_SUFFIX,
            provenance_kind="bundled_local",
            allow_trusted_outside_roots=False,
        )
        if metadata is not None:
            metadata["notes"] = ["manifest_local_icon"]
            return metadata, warnings, metadata["notes"]
        warnings.append(
            {
                "code": "icon-unsafe-path" if "unsafe" in (error or "").lower() or "outside" in (error or "").lower() else "icon-local-invalid",
                "severity": "warning",
                "message": error or "Local manifest icon could not be validated.",
                "field": "icon.asset_path",
            }
        )
        notes.append(f"icon_rejected_candidate:{text}")
    return None, warnings, notes


def _official_remote_icon(
    *,
    candidates: list[Any],
    display_name: str,
    source_catalog: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    warnings: list[dict[str, Any]] = []
    notes: list[str] = []
    if _clean_text((source_catalog or {}).get("kind")) != "official":
        return None, warnings, notes
    allowed_hosts = _allowed_official_hosts(source_catalog)
    for candidate in candidates:
        text = _clean_text(candidate)
        if not text:
            continue
        metadata, error = _validated_remote_icon_url(
            candidate=text,
            display_name=display_name,
            source_catalog=source_catalog,
            provenance_kind="official",
            catalog_hosts=allowed_hosts,
        )
        if metadata is not None:
            metadata["notes"] = ["validated_official_remote_icon"]
            return metadata, warnings, metadata["notes"]
        warnings.append(
            {
                "code": "icon-unsafe-url",
                "severity": "warning",
                "message": error or "Remote icon URL could not be validated.",
                "field": "icon.asset_url",
            }
        )
        notes.append(f"icon_rejected_url:{text}")
    return None, warnings, notes


def _generated_fallback_icon(
    *,
    record_kind: str,
    record_key: str,
    display_name: str,
    runtime_roots: dict[str, Any] | None,
    brand_color: Any,
) -> dict[str, Any]:
    cache_root = _fallback_cache_root(runtime_roots)
    cache_root.mkdir(parents=True, exist_ok=True)
    slug = _slug(display_name or record_key or record_kind)
    fingerprint = hashlib.sha256(f"{record_kind}:{record_key}:{display_name}".encode("utf-8")).hexdigest()[:16]
    asset_path = cache_root / f"{slug}-{fingerprint}.svg"
    text = _render_fallback_svg(
        label=_initials(display_name or record_key or record_kind),
        background=_fallback_color(record_kind, brand_color, record_key),
    )
    if not asset_path.exists() or asset_path.read_text(encoding="utf-8") != text:
        asset_path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "provenance_kind": "generated_fallback",
        "label": display_name,
        "asset_path": str(asset_path.resolve()),
        "mime_type": "image/svg+xml",
        "checksum_algorithm": "sha256",
        "checksum_value": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "validated": True,
        "notes": [
            "astrabridge_generated_replacement",
            "not_official_brand_asset",
        ],
    }


def _validated_local_icon(
    *,
    candidate: str,
    display_name: str,
    base_root: Path | None,
    trusted_roots: list[Path],
    mime_by_suffix: dict[str, str],
    provenance_kind: str,
    allow_trusted_outside_roots: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    if "://" in candidate:
        return None, "Unsafe local icon candidate uses a URL-like path."
    try:
        raw = Path(candidate).expanduser()
        resolved = (raw if raw.is_absolute() else ((base_root or Path.cwd()) / raw)).resolve()
    except Exception as exc:  # noqa: BLE001
        return None, f"Local icon path could not be resolved safely: {exc}"
    if not resolved.exists() or not resolved.is_file():
        return None, f"Local icon path is missing: {resolved}"
    suffix = resolved.suffix.lower()
    mime_type = mime_by_suffix.get(suffix)
    if not mime_type:
        return None, f"Unsafe local icon suffix is not allowed: {resolved.suffix or '<none>'}"
    allowed = False
    if allow_trusted_outside_roots:
        allowed = True
    else:
        if base_root is not None:
            allowed = _is_relative_to(resolved, base_root)
        else:
            allowed = any(_is_relative_to(resolved, root) for root in trusted_roots)
    if not allowed:
        return None, f"Unsafe local icon path escapes trusted roots: {resolved}"
    checksum = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return (
        {
            "provenance_kind": provenance_kind,
            "label": display_name,
            "asset_path": str(resolved),
            "mime_type": mime_type,
            "checksum_algorithm": "sha256",
            "checksum_value": checksum,
            "validated": True,
        },
        None,
    )


def _validated_remote_icon_url(
    *,
    candidate: str,
    display_name: str,
    source_catalog: dict[str, Any] | None,
    provenance_kind: str,
    catalog_hosts: set[str],
) -> tuple[dict[str, Any] | None, str | None]:
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.netloc:
        return None, "Remote icon URL must use https and include a host."
    suffix = Path(parsed.path).suffix.lower()
    mime_type = _REMOTE_RASTER_MIME_BY_SUFFIX.get(suffix)
    if not mime_type:
        return None, f"Remote icon URL suffix is not allowed: {suffix or '<none>'}"
    host = parsed.hostname.lower() if parsed.hostname else ""
    if not any(host == allowed or host.endswith(f".{allowed}") for allowed in catalog_hosts):
        return None, f"Remote icon URL host is not in the approved official host set: {host or '<missing>'}"
    return (
        {
            "provenance_kind": provenance_kind,
            "label": display_name,
            "asset_url": candidate,
            "mime_type": mime_type,
            "validated": True,
            "notes": [
                "validated_remote_url_policy",
                f"source_catalog_kind:{_clean_text((source_catalog or {}).get('kind') or 'unknown')}",
            ],
        },
        None,
    )


def _official_override(overrides: dict[str, dict[str, dict[str, Any]]], record_kind: str, record_key: str) -> dict[str, Any] | None:
    bucket = overrides.get(f"{record_kind}s") or {}
    override = bucket.get(record_key)
    return override if isinstance(override, dict) else None


def _allowed_official_hosts(source_catalog: dict[str, Any] | None) -> set[str]:
    hosts = set(_OFFICIAL_REMOTE_HOSTS)
    catalog_url = _clean_text((source_catalog or {}).get("source_url"))
    if catalog_url:
        parsed = urlparse(catalog_url)
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    return hosts


def _trusted_roots(runtime_roots: dict[str, Any] | None, search_roots: list[Path] | None, base_root: Path | None) -> list[Path]:
    roots: list[Path] = []
    for value in dict(runtime_roots or {}).values():
        text = _clean_text(value)
        if not text:
            continue
        try:
            resolved = Path(text).expanduser().resolve()
        except Exception:
            continue
        roots.append(resolved)
    for value in list(search_roots or []):
        try:
            roots.append(value.resolve())
        except Exception:
            continue
    if base_root is not None:
        roots.append(base_root.resolve())
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _fallback_cache_root(runtime_roots: dict[str, Any] | None) -> Path:
    for key in ("codex_home_root", "project_runtime_root", "workspace_runtime_cwd"):
        value = _clean_text((runtime_roots or {}).get(key))
        if value:
            return Path(value).expanduser().resolve() / ".astrabridge" / "registry-icons"
    return Path.cwd().resolve() / ".astrabridge" / "registry-icons"


def _plugin_root(plugin: dict[str, Any]) -> Path | None:
    manifest_path = _clean_text(plugin.get("manifest_path"))
    if not manifest_path:
        return None
    try:
        return Path(manifest_path).expanduser().resolve().parent.parent
    except Exception:
        return None


def _render_fallback_svg(*, label: str, background: str) -> str:
    safe_label = _escape_xml(label[:2].upper() or "AB")
    return (
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"64\" height=\"64\" viewBox=\"0 0 64 64\" role=\"img\" aria-label=\"AstraBridge generated icon\">"
        f"<rect x=\"0\" y=\"0\" width=\"64\" height=\"64\" rx=\"12\" fill=\"{background}\" />"
        "<circle cx=\"50\" cy=\"14\" r=\"4\" fill=\"rgba(255,255,255,0.22)\" />"
        f"<text x=\"32\" y=\"38\" text-anchor=\"middle\" font-family=\"Segoe UI, Arial, sans-serif\" font-size=\"24\" font-weight=\"700\" fill=\"#ffffff\">{safe_label}</text>"
        "</svg>\n"
    )


def _fallback_color(record_kind: str, brand_color: Any, record_key: str) -> str:
    color = _clean_text(brand_color)
    if color and _HEX_COLOR_RE.match(color):
        return color if color.startswith("#") else f"#{color}"
    palette = {
        "plugin": ["#355c8a", "#1d6f78", "#8a4f3a", "#4f7a3b"],
        "skill": ["#7a4b2b", "#2d6b5f", "#5b4f92", "#7a5f2b"],
    }
    options = palette.get(record_kind, ["#556270"])
    return options[int(hashlib.sha256(record_key.encode("utf-8")).hexdigest()[:2], 16) % len(options)]


def _initials(value: str) -> str:
    tokens = [token for token in re.split(r"[^0-9A-Za-z]+", value.upper()) if token]
    if not tokens:
        return "AB"
    if len(tokens) == 1:
        token = tokens[0]
        return token[:2]
    return f"{tokens[0][0]}{tokens[1][0]}"


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", value.strip()).strip("-._")
    return cleaned[:64] or "registry-icon"


def _escape_xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
