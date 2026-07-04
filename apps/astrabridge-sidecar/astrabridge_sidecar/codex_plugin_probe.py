from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from .app_server_client import JsonRpcError
from .codex_app_server_probe import ProbeClientFactory
from .common import app_runtime_dir, new_id, now_iso, write_json
from .security import redact_sensitive


def probe_plugin_discovery(
    *,
    codex_home: Path,
    client_factory: ProbeClientFactory | None = None,
    local_search_roots: list[Path] | None = None,
    artifact_root: Path | None = None,
    request_timeout: float = 20.0,
) -> dict[str, Any]:
    probe_id = new_id("codex-plugin-probe")
    generated_at = now_iso()
    artifact_dir = (artifact_root or app_runtime_dir("kernel-probes")).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / f"{probe_id}.json"
    codex_home_path = Path(codex_home).resolve()
    config_path = codex_home_path / "config.toml"
    search_roots = _resolve_search_roots(codex_home_path, local_search_roots)
    warnings: list[str] = []

    features = _feature_flags(config_path, warnings)
    status = {
        "config_feature_state": features["plugins"],
        "plugin_sharing_feature_state": features["plugin_sharing"],
        "remote_plugin_feature_state": features["remote_plugin"],
        "list_status": "not_checked",
        "installed_status": "not_checked",
        "read_status": "not_checked",
        "marketplace_status": "not_checked",
        "manifest_fallback_status": "not_checked",
    }

    discovered_plugins: dict[str, dict[str, Any]] = {}
    discovered_marketplaces: list[dict[str, Any]] = []
    marketplace_load_errors: list[dict[str, str]] = []
    featured_plugin_ids: list[str] = []
    plugin_read_records: list[dict[str, Any]] = []
    malformed_manifest_paths: list[str] = []
    client_marketplaces: list[dict[str, Any]] = []

    if client_factory is not None:
        client = client_factory(lambda method, params: None, lambda method, params: {})
        try:
            client.start()
            cwd_params = _cwd_params(search_roots)
            list_result = _request_plugin_command(
                client=client,
                method="plugin/list",
                params=cwd_params,
                timeout=request_timeout,
            )
            status["list_status"] = list_result["status"]
            if isinstance(list_result.get("result"), dict):
                client_marketplaces = _marketplaces_from_response(list_result["result"])
                marketplace_load_errors.extend(_load_errors_from_response(list_result["result"]))
                featured_plugin_ids.extend(_featured_ids_from_response(list_result["result"]))
                _merge_plugins_from_marketplaces(
                    discovered_plugins,
                    client_marketplaces,
                    prefer_installed=False,
                )

            installed_result = _request_plugin_command(
                client=client,
                method="plugin/installed",
                params=cwd_params,
                timeout=request_timeout,
            )
            status["installed_status"] = installed_result["status"]
            if isinstance(installed_result.get("result"), dict):
                installed_marketplaces = _marketplaces_from_response(installed_result["result"])
                marketplace_load_errors.extend(_load_errors_from_response(installed_result["result"]))
                _merge_plugins_from_marketplaces(
                    discovered_plugins,
                    installed_marketplaces,
                    prefer_installed=True,
                )
                client_marketplaces.extend(installed_marketplaces)

            readable_plugin = _first_readable_plugin(discovered_plugins)
            if readable_plugin is not None:
                read_result = _request_plugin_command(
                    client=client,
                    method="plugin/read",
                    params={
                        "pluginName": readable_plugin["plugin_name"],
                        "marketplacePath": readable_plugin.get("marketplace_path"),
                        "remoteMarketplaceName": readable_plugin.get("remote_marketplace_name"),
                    },
                    timeout=request_timeout,
                )
                status["read_status"] = read_result["status"]
                if isinstance(read_result.get("result"), dict):
                    detail = _plugin_detail_record(read_result["result"])
                    if detail:
                        plugin_read_records.append(detail)
                        _merge_plugin_read_detail(discovered_plugins, detail)
            else:
                status["read_status"] = "skipped"
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

    fallback = _scan_local_plugin_manifests(search_roots)
    malformed_manifest_paths.extend(fallback["malformed_manifest_paths"])
    warnings.extend(fallback["warnings"])
    _merge_fallback_plugins(discovered_plugins, fallback["plugins"])
    discovered_marketplaces.extend(fallback["marketplaces"])

    if client_marketplaces:
        for entry in client_marketplaces:
            discovered_marketplaces.append(entry)

    status["marketplace_status"] = _marketplace_status(
        client_marketplaces=client_marketplaces,
        fallback_marketplaces=fallback["marketplaces"],
        load_errors=marketplace_load_errors,
    )
    status["manifest_fallback_status"] = _manifest_fallback_status(fallback)

    report = {
        "schema_version": "codex-plugin-probe-v1",
        "generated_at": generated_at,
        "probe_id": probe_id,
        "report_path": str(report_path),
        "plugin": {
            **status,
            "codex_home": str(codex_home_path),
            "config_path": str(config_path),
            "local_search_roots": [str(root) for root in search_roots],
            "featured_plugin_ids": sorted(set(featured_plugin_ids)),
            "marketplace_load_errors": _dedupe_load_errors(marketplace_load_errors),
            "discovered_marketplaces": _dedupe_marketplaces(discovered_marketplaces),
            "discovered_plugins": sorted(discovered_plugins.values(), key=lambda item: (str(item.get("plugin_id") or ""), str(item.get("source_kind") or ""))),
            "plugin_read_records": plugin_read_records,
            "malformed_manifest_paths": sorted(set(malformed_manifest_paths)),
        },
        "known_warnings": _dedupe_preserve_order(warnings),
    }
    sanitized = redact_sensitive(report)
    write_json(report_path, sanitized)
    return sanitized


def _resolve_search_roots(codex_home: Path, local_search_roots: list[Path] | None) -> list[Path]:
    roots = [codex_home]
    for root in list(local_search_roots or []):
        candidate = Path(root).resolve()
        if candidate not in roots:
            roots.append(candidate)
    return roots


def _feature_flags(config_path: Path, warnings: list[str]) -> dict[str, str]:
    defaults = {"plugins": "unknown", "plugin_sharing": "unknown", "remote_plugin": "unknown"}
    if not config_path.exists():
        warnings.append("Rendered CODEX_HOME config.toml is missing while probing plugins.")
        return defaults
    try:
        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        warnings.append(f"Rendered CODEX_HOME config.toml is malformed: {str(exc)[:200]}")
        return defaults
    features = parsed.get("features")
    if not isinstance(features, dict):
        return defaults
    result: dict[str, str] = {}
    for key in defaults:
        value = features.get(key)
        if isinstance(value, bool):
            result[key] = "enabled" if value else "disabled_by_app"
        else:
            result[key] = "unknown"
    return result


def _cwd_params(search_roots: list[Path]) -> dict[str, Any]:
    return {"cwds": [str(root) for root in search_roots], "marketplaceKinds": ["local"]}


def _request_plugin_command(
    *,
    client: Any,
    method: str,
    params: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    try:
        return {"status": "supported", "result": client.request(method, params, timeout=timeout)}
    except TimeoutError:
        return {"status": "timeout", "result": None}
    except JsonRpcError as exc:
        return {"status": _plugin_command_status(exc), "result": None}
    except Exception:  # noqa: BLE001
        return {"status": "error", "result": None}


def _plugin_command_status(exc: JsonRpcError) -> str:
    if int(exc.code or 0) == -32601:
        return "unsupported"
    return "error_response"


def _marketplaces_from_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in list(payload.get("marketplaces") or []) if isinstance(item, dict)]


def _load_errors_from_response(payload: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for item in list(payload.get("marketplaceLoadErrors") or []) if isinstance(payload.get("marketplaceLoadErrors"), list) else []:
        if not isinstance(item, dict):
            continue
        errors.append(
            {
                "marketplace_path": str(item.get("marketplacePath") or "").strip(),
                "message": str(item.get("message") or "").strip()[:240],
            }
        )
    return errors


def _featured_ids_from_response(payload: dict[str, Any]) -> list[str]:
    values = payload.get("featuredPluginIds")
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _merge_plugins_from_marketplaces(
    discovered_plugins: dict[str, dict[str, Any]],
    marketplaces: list[dict[str, Any]],
    *,
    prefer_installed: bool,
) -> None:
    for marketplace in marketplaces:
        marketplace_name = str(marketplace.get("name") or "").strip() or None
        marketplace_path = str(marketplace.get("path") or "").strip() or None
        plugins = list(marketplace.get("plugins") or [])
        for item in plugins:
            if not isinstance(item, dict):
                continue
            record = _plugin_summary_record(item, marketplace_name=marketplace_name, marketplace_path=marketplace_path)
            if not record:
                continue
            key = record["plugin_id"]
            existing = discovered_plugins.get(key)
            if existing is None:
                discovered_plugins[key] = record
                continue
            if prefer_installed and record.get("availability") == "installed":
                discovered_plugins[key] = {**existing, **record}
                continue
            merged = {**existing}
            for field in ("display_name", "version", "source_kind", "availability", "marketplace_name", "marketplace_path", "remote_marketplace_name", "enabled", "interface_display_name", "short_description"):
                if record.get(field) not in {None, "", "unknown"}:
                    merged[field] = record[field]
            discovered_plugins[key] = merged


def _plugin_summary_record(
    payload: dict[str, Any],
    *,
    marketplace_name: str | None,
    marketplace_path: str | None,
) -> dict[str, Any] | None:
    plugin_id = str(payload.get("id") or payload.get("name") or "").strip()
    if not plugin_id:
        return None
    interface = payload.get("interface")
    interface_payload = interface if isinstance(interface, dict) else {}
    source = payload.get("source")
    source_kind = _source_kind(source, marketplace_path)
    install_policy = str(payload.get("installPolicy") or "").strip()
    availability_value = str(payload.get("availability") or "").strip()
    installed = bool(payload.get("installed", False))
    if installed:
        availability = "installed"
    elif availability_value == "AVAILABLE" or install_policy in {"AVAILABLE", "INSTALLED_BY_DEFAULT"}:
        availability = "available"
    elif availability_value == "DISABLED_BY_ADMIN" or install_policy == "NOT_AVAILABLE":
        availability = "unavailable"
    else:
        availability = "unknown"
    source_payload = source if isinstance(source, dict) else {}
    remote_marketplace_name = marketplace_name if source_payload.get("type") == "remote" else None
    return {
        "plugin_id": plugin_id,
        "plugin_name": str(payload.get("name") or plugin_id).strip(),
        "display_name": str(interface_payload.get("displayName") or payload.get("name") or plugin_id).strip() or None,
        "version": str(payload.get("localVersion") or "").strip() or None,
        "source_kind": source_kind,
        "availability": availability,
        "marketplace_name": marketplace_name,
        "marketplace_path": marketplace_path,
        "remote_marketplace_name": remote_marketplace_name,
        "enabled": bool(payload.get("enabled", False)),
        "interface_display_name": str(interface_payload.get("displayName") or "").strip() or None,
        "short_description": str(interface_payload.get("shortDescription") or "").strip() or None,
        "logo": str(interface_payload.get("logo") or "").strip() or None,
        "logo_url": str(interface_payload.get("logoUrl") or "").strip() or None,
        "composer_icon": str(interface_payload.get("composerIcon") or "").strip() or None,
        "composer_icon_url": str(interface_payload.get("composerIconUrl") or "").strip() or None,
        "brand_color": str(interface_payload.get("brandColor") or "").strip() or None,
    }


def _source_kind(source: Any, marketplace_path: str | None) -> str:
    if not isinstance(source, dict):
        return "unknown"
    source_type = str(source.get("type") or "").strip()
    if source_type == "remote":
        return "remote_marketplace"
    if source_type == "git":
        return "shared_remote"
    if source_type == "local":
        return "local_marketplace" if marketplace_path else "installed_root"
    return "unknown"


def _first_readable_plugin(discovered_plugins: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    candidates = sorted(
        discovered_plugins.values(),
        key=lambda item: (item.get("availability") != "installed", str(item.get("plugin_id") or "")),
    )
    return candidates[0] if candidates else None


def _plugin_detail_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    plugin = payload.get("plugin")
    if not isinstance(plugin, dict):
        return None
    summary = plugin.get("summary")
    if not isinstance(summary, dict):
        return None
    interface_payload = {}
    summary_interface = summary.get("interface")
    if isinstance(summary_interface, dict):
        interface_payload = summary_interface
    elif isinstance(plugin.get("interface"), dict):
        interface_payload = plugin.get("interface")
    plugin_id = str(summary.get("id") or summary.get("name") or "").strip()
    if not plugin_id:
        return None
    return {
        "plugin_id": plugin_id,
        "display_name": str(interface_payload.get("displayName") or summary.get("name") or plugin_id).strip() or None,
        "description": str(plugin.get("description") or "").strip() or None,
        "skills": sorted(str(item.get("name") or "").strip() for item in list(plugin.get("skills") or []) if isinstance(item, dict) and str(item.get("name") or "").strip()),
        "apps": sorted(str(item.get("id") or item.get("name") or "").strip() for item in list(plugin.get("apps") or []) if isinstance(item, dict) and str(item.get("id") or item.get("name") or "").strip()),
        "mcp_servers": sorted(str(item).strip() for item in list(plugin.get("mcpServers") or []) if str(item).strip()),
        "marketplace_name": str(plugin.get("marketplaceName") or "").strip() or None,
        "marketplace_path": str(plugin.get("marketplacePath") or "").strip() or None,
        "logo": str(interface_payload.get("logo") or "").strip() or None,
        "logo_url": str(interface_payload.get("logoUrl") or "").strip() or None,
        "composer_icon": str(interface_payload.get("composerIcon") or "").strip() or None,
        "composer_icon_url": str(interface_payload.get("composerIconUrl") or "").strip() or None,
        "brand_color": str(interface_payload.get("brandColor") or "").strip() or None,
    }


def _merge_plugin_read_detail(discovered_plugins: dict[str, dict[str, Any]], detail: dict[str, Any]) -> None:
    plugin_id = str(detail.get("plugin_id") or "").strip()
    if not plugin_id:
        return
    existing = discovered_plugins.get(plugin_id)
    if existing is None:
        discovered_plugins[plugin_id] = dict(detail)
        return
    merged = {**existing}
    for field in ("description", "skills", "apps", "mcp_servers", "marketplace_name", "marketplace_path", "logo", "logo_url", "composer_icon", "composer_icon_url", "brand_color"):
        if detail.get(field):
            merged[field] = detail[field]
    discovered_plugins[plugin_id] = merged


def _scan_local_plugin_manifests(search_roots: list[Path]) -> dict[str, Any]:
    plugins: list[dict[str, Any]] = []
    marketplaces: list[dict[str, Any]] = []
    warnings: list[str] = []
    malformed_manifest_paths: list[str] = []
    seen_marketplaces: set[str] = set()
    referenced_plugin_roots: set[Path] = set()

    for root in search_roots:
        for marketplace_path in sorted(root.rglob("marketplace.json")):
            marketplace_key = str(marketplace_path.resolve())
            if marketplace_key in seen_marketplaces:
                continue
            seen_marketplaces.add(marketplace_key)
            marketplace_payload = _read_json_file(marketplace_path)
            if not isinstance(marketplace_payload, dict):
                continue
            marketplace_name = str(marketplace_payload.get("name") or marketplace_path.stem).strip() or marketplace_path.stem
            plugin_entries = list(marketplace_payload.get("plugins") or [])
            marketplaces.append(
                {
                    "name": marketplace_name,
                    "path": str(marketplace_path.resolve()),
                    "plugin_count": len([item for item in plugin_entries if isinstance(item, dict)]),
                    "source": "manifest_fallback",
                }
            )
            for entry in plugin_entries:
                if not isinstance(entry, dict):
                    continue
                record, referenced_root, warning = _plugin_record_from_marketplace_entry(marketplace_path, marketplace_name, entry)
                if warning:
                    warnings.append(warning)
                if referenced_root is not None:
                    referenced_plugin_roots.add(referenced_root)
                if record is not None:
                    plugins.append(record)
                if record is not None and record.get("manifest_status") == "malformed":
                    malformed_manifest_paths.append(str(record.get("manifest_path") or ""))

        for manifest_path in sorted(root.rglob("plugin.json")):
            if manifest_path.parent.name != ".codex-plugin":
                continue
            plugin_root = manifest_path.parent.parent.resolve()
            if plugin_root in referenced_plugin_roots:
                continue
            default_availability = "unknown"
            try:
                manifest_path.resolve().relative_to((root / "plugins").resolve())
            except Exception:
                default_availability = "unknown"
            else:
                default_availability = "installed"
            record = _plugin_record_from_manifest(
                manifest_path,
                marketplace_name=None,
                marketplace_path=None,
                default_availability=default_availability,
            )
            if record is None:
                continue
            plugins.append(record)
            if record.get("manifest_status") == "malformed":
                malformed_manifest_paths.append(str(record.get("manifest_path") or ""))

    manifest_fallback_status = "empty"
    if malformed_manifest_paths:
        manifest_fallback_status = "malformed"
    elif plugins or marketplaces:
        manifest_fallback_status = "used"

    return {
        "plugins": plugins,
        "marketplaces": marketplaces,
        "warnings": warnings,
        "malformed_manifest_paths": [path for path in malformed_manifest_paths if path],
        "status": manifest_fallback_status,
    }


def _plugin_record_from_marketplace_entry(
    marketplace_path: Path,
    marketplace_name: str,
    entry: dict[str, Any],
) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    plugin_name = str(entry.get("name") or "").strip()
    if not plugin_name:
        return None, None, None
    source = entry.get("source")
    source_payload = source if isinstance(source, dict) else {}
    source_type = str(source_payload.get("source") or source_payload.get("type") or "").strip()
    if source_type != "local":
        return (
            {
                "plugin_id": plugin_name,
                "plugin_name": plugin_name,
                "display_name": plugin_name,
                "version": None,
                "source_kind": "remote_marketplace" if source_type == "remote" else "unknown",
                "availability": "available",
                "marketplace_name": marketplace_name,
                "marketplace_path": str(marketplace_path.resolve()),
                "manifest_status": "not_checked",
                "manifest_path": None,
            },
            None,
            None,
        )
    relative_plugin_path = str(source_payload.get("path") or "").strip()
    if not relative_plugin_path:
        return None, None, f"Marketplace entry {plugin_name} in {marketplace_path} is missing source.path."
    plugin_root = (marketplace_path.parent / relative_plugin_path).resolve()
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    record = _plugin_record_from_manifest(
        manifest_path,
        marketplace_name=marketplace_name,
        marketplace_path=str(marketplace_path.resolve()),
        default_availability="available",
        plugin_name_hint=plugin_name,
    )
    if record is None:
        return (
            {
                "plugin_id": plugin_name,
                "plugin_name": plugin_name,
                "display_name": plugin_name,
                "version": None,
                "source_kind": "local_marketplace",
                "availability": "available",
                "marketplace_name": marketplace_name,
                "marketplace_path": str(marketplace_path.resolve()),
                "manifest_status": "missing",
                "manifest_path": str(manifest_path),
            },
            plugin_root,
            f"Marketplace entry {plugin_name} points to a missing plugin manifest: {manifest_path}",
        )
    return record, plugin_root, None


def _plugin_record_from_manifest(
    manifest_path: Path,
    *,
    marketplace_name: str | None,
    marketplace_path: str | None,
    default_availability: str,
    plugin_name_hint: str | None = None,
) -> dict[str, Any] | None:
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "plugin_id": plugin_name_hint or manifest_path.parent.parent.name,
            "plugin_name": plugin_name_hint or manifest_path.parent.parent.name,
            "display_name": plugin_name_hint or manifest_path.parent.parent.name,
            "version": None,
            "source_kind": "local_marketplace" if marketplace_path else "installed_root",
            "availability": default_availability,
            "marketplace_name": marketplace_name,
            "marketplace_path": marketplace_path,
            "manifest_status": "malformed",
            "manifest_path": str(manifest_path.resolve()),
        }
    if not isinstance(payload, dict):
        return None
    interface = payload.get("interface")
    interface_payload = interface if isinstance(interface, dict) else {}
    plugin_name = str(payload.get("name") or plugin_name_hint or manifest_path.parent.parent.name).strip()
    if not plugin_name:
        return None
    return {
        "plugin_id": plugin_name,
        "plugin_name": plugin_name,
        "display_name": str(interface_payload.get("displayName") or plugin_name).strip() or plugin_name,
        "version": str(payload.get("version") or "").strip() or None,
        "source_kind": "local_marketplace" if marketplace_path else "installed_root",
        "availability": default_availability,
        "marketplace_name": marketplace_name,
        "marketplace_path": marketplace_path,
        "manifest_status": "ok",
        "manifest_path": str(manifest_path.resolve()),
        "description": str(interface_payload.get("longDescription") or interface_payload.get("shortDescription") or "").strip() or None,
        "mcp_servers_declared": _manifest_component_names(payload.get("mcpServers")),
        "apps_declared": _manifest_component_names(payload.get("apps")),
        "skills_declared": _manifest_component_names(payload.get("skills")),
        "logo": str(interface_payload.get("logo") or "").strip() or None,
        "logo_url": str(interface_payload.get("logoUrl") or "").strip() or None,
        "composer_icon": str(interface_payload.get("composerIcon") or "").strip() or None,
        "composer_icon_url": str(interface_payload.get("composerIconUrl") or "").strip() or None,
        "brand_color": str(interface_payload.get("brandColor") or "").strip() or None,
    }


def _manifest_component_names(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                names.append(text)
        return sorted(set(names))
    if isinstance(value, dict):
        names: list[str] = []
        for key in value.keys():
            text = str(key).strip()
            if text:
                names.append(text)
        return sorted(set(names))
    return []


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _merge_fallback_plugins(discovered_plugins: dict[str, dict[str, Any]], plugins: list[dict[str, Any]]) -> None:
    for record in plugins:
        key = str(record.get("plugin_id") or "").strip()
        if not key:
            continue
        existing = discovered_plugins.get(key)
        if existing is None:
            discovered_plugins[key] = record
            continue
        merged = {**existing}
        if existing.get("availability") != "installed" and record.get("availability") == "installed":
            merged["availability"] = "installed"
        for field in (
            "display_name",
            "version",
            "source_kind",
            "marketplace_name",
            "marketplace_path",
            "description",
            "mcp_servers_declared",
            "apps_declared",
            "skills_declared",
            "manifest_status",
            "manifest_path",
            "logo",
            "logo_url",
            "composer_icon",
            "composer_icon_url",
            "brand_color",
        ):
            value = record.get(field)
            if value is not None and value != "" and value != [] and value != "not_checked":
                merged[field] = record[field]
        discovered_plugins[key] = merged


def _marketplace_status(
    *,
    client_marketplaces: list[dict[str, Any]],
    fallback_marketplaces: list[dict[str, Any]],
    load_errors: list[dict[str, str]],
) -> str:
    if load_errors:
        return "partial"
    if client_marketplaces:
        return "supported"
    if fallback_marketplaces:
        return "manifest_fallback"
    return "empty"


def _manifest_fallback_status(fallback: dict[str, Any]) -> str:
    status = str(fallback.get("status") or "empty")
    if status == "used":
        return "supported"
    if status == "malformed":
        return "malformed"
    if status == "empty":
        return "empty"
    return status


def _dedupe_marketplaces(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in values:
        name = str(item.get("name") or "").strip()
        path = str(item.get("path") or "").strip()
        key = (name, path)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return sorted(result, key=lambda item: (str(item.get("name") or ""), str(item.get("path") or "")))


def _dedupe_load_errors(values: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in values:
        key = (str(item.get("marketplace_path") or ""), str(item.get("message") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
