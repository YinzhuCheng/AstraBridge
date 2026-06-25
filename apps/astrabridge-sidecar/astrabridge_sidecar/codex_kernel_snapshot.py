from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .common import default_codex_home, new_id, now_iso


_METHOD_RE = re.compile(r'"method":\s*"([^"]+)"')
_KNOWN_CLIENT_METHODS = (
    "initialize",
    "thread/start",
    "thread/resume",
    "turn/start",
    "plugin/list",
    "plugin/installed",
    "plugin/read",
    "plugin/install",
    "plugin/uninstall",
    "plugin/share/list",
    "skills/list",
    "skills/extraRoots/set",
    "skills/config/write",
    "config/mcpServer/reload",
    "mcpServerStatus/list",
)
_KNOWN_SERVER_NOTIFICATIONS = (
    "thread/started",
    "turn/started",
    "skills/changed",
    "mcpServer/startupStatus/updated",
    "warning",
)


def observe_protocol_features(
    *,
    client_request_path: Path | None = None,
    server_notification_path: Path | None = None,
) -> dict[str, Any]:
    client_path = client_request_path or _default_client_request_path()
    notification_path = server_notification_path or _default_server_notification_path()

    client_methods = {name: "unknown" for name in _KNOWN_CLIENT_METHODS}
    server_notifications = {name: "unknown" for name in _KNOWN_SERVER_NOTIFICATIONS}
    notes: list[str] = []
    observed_sources = 0

    declared_client = _declared_methods(client_path)
    if declared_client is not None:
        observed_sources += 1
        for name in client_methods:
            client_methods[name] = "declared" if name in declared_client else "unknown"
    else:
        notes.append(f"Generated client request file was not available: {client_path}")

    declared_notifications = _declared_methods(notification_path)
    if declared_notifications is not None:
        observed_sources += 1
        for name in server_notifications:
            server_notifications[name] = "declared" if name in declared_notifications else "unknown"
    else:
        notes.append(f"Generated server notification file was not available: {notification_path}")

    source_kind = "generated_types_only" if observed_sources else "unknown"
    return {
        "source_kind": source_kind,
        "client_methods": client_methods,
        "server_notifications": server_notifications,
        "notes": notes,
    }


def build_codex_kernel_probe_snapshot(
    *,
    binary: dict[str, Any],
    execution_host: str,
    wsl_distro: str | None,
    runtime_status: dict[str, Any],
    runtime_roots: dict[str, Any],
    app_server: dict[str, Any],
    protocol_features: dict[str, Any],
    mcp_report: dict[str, Any] | None,
    plugin_report: dict[str, Any] | None,
    skill_report: dict[str, Any] | None,
    extra_warnings: list[str] | None = None,
    evidence_sources: list[str] | None = None,
) -> dict[str, Any]:
    generated_at = now_iso()
    mcp = _observed_mcp_features(mcp_report)
    plugin = _observed_plugin_features(plugin_report, protocol_features)
    skill = _observed_skill_features(skill_report, protocol_features)
    observed = {
        "binary": {
            "path": binary.get("path"),
            "path_source": _binary_path_source(binary),
            "version_text": binary.get("version_text"),
            "version_semver": binary.get("version_semver"),
            "version_parse_status": binary.get("version_parse_status") or "not_checked",
            "launch_descriptor": binary.get("launch_descriptor"),
        },
        "platform": {
            "execution_host": execution_host if execution_host in {"windows", "wsl"} else "unknown",
            "platform_family": "linux" if execution_host == "wsl" else "windows",
            "platform_os": "linux" if execution_host == "wsl" else "windows",
            "wsl_distro": wsl_distro,
        },
        "runtime_roots": {
            "isolated_codex_home": str(runtime_status.get("codex_home") or runtime_roots.get("codex_home_root") or "") or None,
            "codex_home_source": _codex_home_source(runtime_status),
            "project_runtime_root": _optional_string(runtime_roots.get("project_runtime_root")),
            "workspace_runtime_cwd": _optional_string(runtime_roots.get("workspace_runtime_cwd")),
        },
        "app_server": app_server,
        "protocol_features": protocol_features,
        "mcp_features": mcp,
        "plugin_features": plugin,
        "skill_features": skill,
    }
    inferred = _infer_snapshot(observed)

    warnings = list(extra_warnings or [])
    if isinstance(mcp_report, dict):
        warnings.extend(str(item) for item in list(mcp_report.get("known_warnings") or []))
    if isinstance(plugin_report, dict):
        warnings.extend(str(item) for item in list(plugin_report.get("known_warnings") or []))
    if isinstance(skill_report, dict):
        warnings.extend(str(item) for item in list(skill_report.get("known_warnings") or []))
    if execution_host == "wsl":
        warnings.append("wsl_runtime_requires_linux_native_codex")
    if plugin.get("config_feature_state") == "disabled_by_app":
        warnings.append("rendered_config_disables_plugins")
    warnings = _dedupe_preserve_order(warnings)

    commands = [
        _command_evidence("codex --version", observed["binary"]["version_parse_status"]),
        _command_evidence("config/mcpServer/reload", mcp.get("reload_status")),
        _command_evidence("mcpServerStatus/list", mcp.get("server_status_list_status")),
        _command_evidence("plugin/list", plugin.get("list_status")),
        _command_evidence("plugin/read", plugin.get("read_status")),
        _command_evidence("skills/list", skill.get("list_status")),
    ]
    artifacts = [
        _optional_string((mcp_report or {}).get("report_path")),
        _optional_string((plugin_report or {}).get("report_path")),
        _optional_string((skill_report or {}).get("report_path")),
    ]
    sources = _dedupe_preserve_order(
        list(evidence_sources or [])
        + [
            "apps/astrabridge-sidecar/astrabridge_sidecar/codex_kernel_probe.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/codex_kernel_snapshot.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/codex_mcp_probe.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/codex_plugin_probe.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/codex_skill_probe.py",
            "apps/astrabridge-desktop/src/protocol/generated/ClientRequest.ts",
            "apps/astrabridge-desktop/src/protocol/generated/ServerNotification.ts",
            "PLAN/CODEX_KERNEL_PROBE_CONTRACT.md",
            "PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md",
        ]
    )

    return {
        "schema_version": "codex-kernel-probe-v1",
        "generated_at": generated_at,
        "probe_run_id": new_id("codex-kernel-probe"),
        "observed": observed,
        "inferred": inferred,
        "known_warnings": warnings,
        "evidence": {
            "sources": sources,
            "commands": [item for item in commands if item is not None],
            "artifacts": [item for item in artifacts if item],
        },
    }


def _default_client_request_path() -> Path:
    return Path(__file__).resolve().parents[2] / "astrabridge-desktop" / "src" / "protocol" / "generated" / "ClientRequest.ts"


def _default_server_notification_path() -> Path:
    return Path(__file__).resolve().parents[2] / "astrabridge-desktop" / "src" / "protocol" / "generated" / "ServerNotification.ts"


def _declared_methods(path: Path) -> set[str] | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return {match.group(1) for match in _METHOD_RE.finditer(text)}


def _observed_mcp_features(report: dict[str, Any] | None) -> dict[str, Any]:
    payload = (report or {}).get("mcp") if isinstance(report, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    notes = [str(item) for item in list(payload.get("missing_servers") or []) if str(item).strip()]
    missing_tools = [str(item) for item in list(payload.get("missing_tools") or []) if str(item).strip()]
    if missing_tools:
        notes.append(f"missing_tools:{', '.join(missing_tools)}")
    unexpected = [str(item) for item in list(payload.get("unexpected_servers") or []) if str(item).strip()]
    if unexpected:
        notes.append(f"unexpected_servers:{', '.join(unexpected)}")
    return {
        "config_render_status": payload.get("config_render_status") or "not_checked",
        "config_updated_at": payload.get("config_updated_at"),
        "reload_status": payload.get("reload_status") or "not_checked",
        "server_status_list_status": payload.get("server_status_list_status") or "not_checked",
        "expected_servers": list(payload.get("expected_servers") or []),
        "visible_servers": list(payload.get("visible_servers") or []),
        "expected_tools": list(payload.get("expected_tools") or []),
        "visible_tools": list(payload.get("visible_tools") or []),
        "notes": notes,
    }


def _observed_plugin_features(report: dict[str, Any] | None, protocol_features: dict[str, Any]) -> dict[str, Any]:
    payload = (report or {}).get("plugin") if isinstance(report, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    methods = dict(protocol_features.get("client_methods") or {})
    notes: list[str] = []
    featured_plugin_ids = [str(item) for item in list(payload.get("featured_plugin_ids") or []) if str(item).strip()]
    if featured_plugin_ids:
        notes.append(f"featured_plugin_ids:{', '.join(featured_plugin_ids)}")
    malformed_manifest_paths = list(payload.get("malformed_manifest_paths") or [])
    if malformed_manifest_paths:
        notes.append(f"malformed_manifests:{len(malformed_manifest_paths)}")
    marketplace_load_errors = list(payload.get("marketplace_load_errors") or [])
    if marketplace_load_errors:
        notes.append(f"marketplace_load_errors:{len(marketplace_load_errors)}")
    return {
        "config_feature_state": payload.get("config_feature_state") or "unknown",
        "list_status": payload.get("list_status") or "not_checked",
        "installed_status": payload.get("installed_status") or "not_checked",
        "read_status": payload.get("read_status") or "not_checked",
        "install_status": methods.get("plugin/install") or "unknown",
        "uninstall_status": methods.get("plugin/uninstall") or "unknown",
        "share_status": methods.get("plugin/share/list") or "unknown",
        "marketplace_status": payload.get("marketplace_status") or "not_checked",
        "discovered_plugins": [
            {
                "plugin_id": str(item.get("plugin_id") or ""),
                "display_name": item.get("display_name"),
                "version": item.get("version"),
                "source_kind": item.get("source_kind") or "unknown",
                "availability": item.get("availability") or "unknown",
            }
            for item in list(payload.get("discovered_plugins") or [])
            if isinstance(item, dict) and str(item.get("plugin_id") or "").strip()
        ],
        "notes": notes,
    }


def _observed_skill_features(report: dict[str, Any] | None, protocol_features: dict[str, Any]) -> dict[str, Any]:
    payload = (report or {}).get("skill") if isinstance(report, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    methods = dict(protocol_features.get("client_methods") or {})
    notifications = dict(protocol_features.get("server_notifications") or {})
    return {
        "list_status": payload.get("list_status") or "not_checked",
        "extra_roots_status": methods.get("skills/extraRoots/set") or payload.get("extra_roots_status") or "unknown",
        "config_write_status": methods.get("skills/config/write") or payload.get("config_write_status") or "unknown",
        "change_notification_status": notifications.get("skills/changed") or payload.get("change_notification_status") or "unknown",
        "discovered_roots": list(payload.get("discovered_roots") or []),
        "discovered_skills": [
            {
                "skill_name": str(item.get("skill_name") or ""),
                "display_name": item.get("display_name"),
                "source_kind": item.get("source_kind") or "unknown",
                "owner_plugin_id": item.get("owner_plugin_id"),
                "enablement": item.get("enablement") or "unknown",
            }
            for item in list(payload.get("discovered_skills") or [])
            if isinstance(item, dict) and str(item.get("skill_name") or "").strip()
        ],
        "notes": [str(item) for item in list(payload.get("notes") or []) if str(item).strip()],
    }


def _infer_snapshot(observed: dict[str, Any]) -> dict[str, Any]:
    binary = dict(observed.get("binary") or {})
    app_server = dict(observed.get("app_server") or {})
    mcp = dict(observed.get("mcp_features") or {})
    plugin = dict(observed.get("plugin_features") or {})
    skill = dict(observed.get("skill_features") or {})
    version_status = str(binary.get("version_parse_status") or "not_checked")
    initialize_status = str(app_server.get("initialize_status") or "not_checked")

    compatibility_status = "unknown"
    if version_status in {"missing", "error"} or not binary.get("path"):
        compatibility_status = "blocked"
    elif _probe_activity_present(mcp, plugin, skill, initialize_status):
        compatibility_status = "probed"
    elif version_status == "ok":
        compatibility_status = "partial"

    kernel_upgrade_readiness = "unknown"
    if compatibility_status == "blocked":
        kernel_upgrade_readiness = "blocked"
    elif version_status == "ok":
        kernel_upgrade_readiness = "partial"

    plugin_integration_readiness = "unknown"
    if plugin.get("config_feature_state") == "disabled_by_app":
        plugin_integration_readiness = "blocked_by_app_config"
    elif str(plugin.get("list_status") or "") == "supported" or list(plugin.get("discovered_plugins") or []):
        plugin_integration_readiness = "partial"
    elif any(str(plugin.get(field) or "") == "declared" for field in ("install_status", "uninstall_status", "share_status")):
        plugin_integration_readiness = "declared_not_probed"

    skill_integration_readiness = "unknown"
    if str(skill.get("list_status") or "") == "supported" or list(skill.get("discovered_skills") or []):
        skill_integration_readiness = "partial"
    elif any(str(skill.get(field) or "") == "declared" for field in ("extra_roots_status", "config_write_status", "change_notification_status")):
        skill_integration_readiness = "declared_not_probed"

    risk_flags: list[str] = []
    if app_server.get("launch_mode") in {"direct", "wsl_exec"}:
        risk_flags.append("app_server_flags_fragile")
    if plugin.get("config_feature_state") == "disabled_by_app":
        risk_flags.append("plugin_features_disabled_in_rendered_config")
    if observed.get("platform", {}).get("execution_host") == "wsl":
        risk_flags.append("wsl_runtime_path_rewrite_fragile")

    required_follow_up_checks: list[str] = []
    if version_status != "ok":
        required_follow_up_checks.append("binary_version_probe")
    if initialize_status != "supported":
        required_follow_up_checks.append("app_server_protocol_probe")
    if str(mcp.get("server_status_list_status") or "") != "supported":
        required_follow_up_checks.append("mcp_visibility_probe")
    if str(plugin.get("list_status") or "") != "supported":
        required_follow_up_checks.append("plugin_discovery_probe")
    if str(skill.get("list_status") or "") != "supported":
        required_follow_up_checks.append("skill_discovery_probe")
    required_follow_up_checks.append("kernel_smoke_suite")

    if compatibility_status == "blocked":
        compatibility_summary = "Codex binary or app-server access is incomplete, so AstraBridge cannot yet treat this kernel as a usable baseline."
    elif compatibility_status == "probed":
        compatibility_summary = "Read-only kernel probes completed for the current runtime, but smoke evidence and verified gating are still missing."
    elif compatibility_status == "partial":
        compatibility_summary = "Codex binary metadata is known, but the broader runtime compatibility surface has only partial evidence."
    else:
        compatibility_summary = "AstraBridge does not yet have enough trustworthy evidence to classify this kernel."

    return {
        "compatibility_status": compatibility_status,
        "compatibility_summary": compatibility_summary,
        "kernel_upgrade_readiness": kernel_upgrade_readiness,
        "plugin_integration_readiness": plugin_integration_readiness,
        "skill_integration_readiness": skill_integration_readiness,
        "risk_flags": _dedupe_preserve_order(risk_flags),
        "required_follow_up_checks": _dedupe_preserve_order(required_follow_up_checks),
    }


def _binary_path_source(binary: dict[str, Any]) -> str:
    source = str(binary.get("path_source") or "unknown")
    return source if source in {"env_override", "which", "wsl_default", "runtime_status", "unknown"} else "unknown"


def _codex_home_source(runtime_status: dict[str, Any]) -> str:
    if os.environ.get("ASTRABRIDGE_CODEX_HOME"):
        return "ASTRABRIDGE_CODEX_HOME"
    current = str(runtime_status.get("codex_home") or "").strip()
    if not current:
        return "unknown"
    default_root = str(default_codex_home().resolve())
    return "astrabridge_default" if current == default_root else "resolver"


def _probe_activity_present(mcp: dict[str, Any], plugin: dict[str, Any], skill: dict[str, Any], initialize_status: str) -> bool:
    if initialize_status == "supported":
        return True
    for value in (
        mcp.get("reload_status"),
        mcp.get("server_status_list_status"),
        plugin.get("list_status"),
        plugin.get("read_status"),
        skill.get("list_status"),
    ):
        if str(value or "") not in {"", "unknown", "not_checked"}:
            return True
    return False


def _command_evidence(command: str, probe_status: Any) -> dict[str, Any] | None:
    status = str(probe_status or "").strip()
    if not status:
        return None
    if status in {"supported", "ok"}:
        command_status = "ok"
    elif status in {"not_checked", "skipped", "unknown", "declared"}:
        command_status = "skipped"
    else:
        command_status = "failed"
    return {"command": command, "status": command_status}


def _optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered
