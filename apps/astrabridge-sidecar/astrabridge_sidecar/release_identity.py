from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .common import now_iso, slugify, write_json


RELEASE_IDENTITY_SCHEMA_VERSION = "astrabridge-release-identity-v1"
RELEASE_STAGING_SCHEMA_VERSION = "astrabridge-release-staging-v1"
RELEASE_READINESS_SCHEMA_VERSION = "astrabridge-release-readiness-v1"
RELEASE_UPDATER_MANIFEST_SCHEMA_VERSION = "astrabridge-updater-release-v1"
RELEASE_UPDATER_KILL_SWITCH_SCHEMA_VERSION = "astrabridge-updater-kill-switch-v1"
FORMAL_SIDECAR_BUNDLE_SCHEMA_VERSION = "astrabridge-sidecar-formal-bundle-v1"
DESKTOP_UPDATE_STATUS_SCHEMA_VERSION = "astrabridge-desktop-update-status-v1"
WINDOWS_UPDATE_REHEARSAL_SCHEMA_VERSION = "astrabridge-windows-update-rehearsal-v1"
UPDATE_TRANSACTION_SCHEMA_VERSION = "astrabridge-update-transaction-v1"
UPDATE_GENERATION_POINTER_SCHEMA_VERSION = "astrabridge-update-generation-pointer-v1"
EXPECTED_UPDATER_CHANNELS = ("stable", "beta", "canary")
EXPECTED_UPDATER_ENDPOINT_TOKENS = ("{{target}}", "{{arch}}", "{{current_version}}")
TAURI_UPDATER_PLUGIN_SCHEMA_VERSION = "tauri-v2-updater-plugin-config"

_REPO_ROOT = Path(__file__).resolve().parents[3]
RELEASE_IDENTITY_PATH = _REPO_ROOT / "release" / "astrabridge-release-identity.json"
PROTOCOL_COMPATIBILITY_MANIFEST_PATH = (
    _REPO_ROOT / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "protocol" / "compatibility_manifest.json"
)

_VERSION_PATTERN = re.compile(r'(?m)^(?P<prefix>\s*(?:__version__|SERVER_VERSION)\s*=\s*["\'])(?P<value>[^"\']+)(?P<suffix>["\'])\s*$')
_CLIENT_VERSION_PATTERN = re.compile(
    r'(?P<prefix>"clientInfo"\s*:\s*\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"version"\s*:\s*")(?P<value>[^"]+)(?P<suffix>")'
)
_TOML_VERSION_PATTERN = re.compile(r'(?m)^(?P<prefix>\s*version\s*=\s*")(?P<value>[^"]+)(?P<suffix>")\s*$')
_TEST_FILE_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".smoke.ts",
    ".smoke.tsx",
)
_EXCLUDED_PARTS = {
    ".astrabridge",
    ".pnpm-store",
    ".pytest_cache",
    ".tmp",
    ".venv",
    "__pycache__",
    "PRIVATE",
    "dist",
    "node_modules",
    "output",
    "target",
    "tests",
    "tmp",
}
_STAGING_INCLUDE_RULES: tuple[dict[str, Any], ...] = (
    {"kind": "file", "path": "release/astrabridge-release-identity.json"},
    {"kind": "file", "path": "apps/astrabridge-desktop/index.html"},
    {"kind": "file", "path": "apps/astrabridge-desktop/package.json"},
    {"kind": "file", "path": "apps/astrabridge-desktop/package-lock.json"},
    {"kind": "file", "path": "apps/astrabridge-desktop/pnpm-lock.yaml"},
    {"kind": "file", "path": "apps/astrabridge-desktop/pnpm-workspace.yaml"},
    {"kind": "file", "path": "apps/astrabridge-desktop/tsconfig.json"},
    {"kind": "file", "path": "apps/astrabridge-desktop/tsconfig.node.json"},
    {"kind": "glob", "pattern": "apps/astrabridge-desktop/vite.config.*"},
    {"kind": "tree", "path": "apps/astrabridge-desktop/public"},
    {"kind": "tree", "path": "apps/astrabridge-desktop/src"},
    {"kind": "file", "path": "apps/astrabridge-desktop/src-tauri/build.rs"},
    {"kind": "file", "path": "apps/astrabridge-desktop/src-tauri/Cargo.toml"},
    {"kind": "file", "path": "apps/astrabridge-desktop/src-tauri/Cargo.lock"},
    {"kind": "file", "path": "apps/astrabridge-desktop/src-tauri/tauri.conf.json"},
    {"kind": "tree", "path": "apps/astrabridge-desktop/src-tauri/capabilities"},
    {"kind": "tree", "path": "apps/astrabridge-desktop/src-tauri/gen"},
    {"kind": "tree", "path": "apps/astrabridge-desktop/src-tauri/icons"},
    {"kind": "tree", "path": "apps/astrabridge-desktop/src-tauri/nsis"},
    {"kind": "tree", "path": "apps/astrabridge-desktop/src-tauri/src"},
    {"kind": "file", "path": "apps/astrabridge-sidecar/pyproject.toml"},
    {"kind": "file", "path": "apps/astrabridge-sidecar/README.md"},
    {"kind": "file", "path": "apps/astrabridge-sidecar/sidecar_server.py"},
    {"kind": "file", "path": "apps/astrabridge-sidecar/uv.lock"},
    {"kind": "tree", "path": "apps/astrabridge-sidecar/astrabridge_sidecar"},
    {"kind": "tree", "path": "apps/astrabridge-sidecar/skills"},
    {"kind": "file", "path": "scripts/run_promotion_gate.py"},
    {"kind": "file", "path": "scripts/run_release_readiness_gate.py"},
)


def load_release_identity(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path).resolve() if path else RELEASE_IDENTITY_PATH
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if str(payload.get("schema_version") or "") != RELEASE_IDENTITY_SCHEMA_VERSION:
        raise ValueError(f"Unexpected release identity schema version: {manifest_path}")
    return payload


def release_product_version(path: str | Path | None = None) -> str:
    return str(load_release_identity(path).get("release_version") or "").strip()


def release_protocol_schema_version(path: str | Path | None = None) -> str:
    identity = load_release_identity(path)
    return str(dict(identity.get("protocol") or {}).get("schema_version") or "").strip()


def collect_release_bindings(repo_root: str | Path | None = None, identity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    root = Path(repo_root).expanduser().resolve() if repo_root else _REPO_ROOT
    manifest = identity or load_release_identity(root / "release" / "astrabridge-release-identity.json")
    version = str(manifest.get("release_version") or "").strip()
    protocol_version = str(dict(manifest.get("protocol") or {}).get("schema_version") or "").strip()
    tauri_updater = expected_tauri_updater_config(manifest)
    formal_sidecar_bundle = expected_formal_sidecar_bundle(manifest)
    bindings = [
        _json_binding(root / "apps" / "astrabridge-desktop" / "package.json", ("version",), version, "desktop.package.json.version"),
        _json_binding(root / "apps" / "astrabridge-desktop" / "package-lock.json", ("version",), version, "desktop.package-lock.version"),
        _toml_binding(root / "apps" / "astrabridge-sidecar" / "pyproject.toml", ("project", "version"), version, "sidecar.pyproject.version"),
        _toml_binding(root / "apps" / "astrabridge-desktop" / "src-tauri" / "Cargo.toml", ("package", "version"), version, "desktop.cargo.version"),
        _json_binding(root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json", ("version",), version, "desktop.tauri.version"),
        _json_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json",
            ("bundle", "resources"),
            (
                {formal_sidecar_bundle["tauri_resource_source"]: formal_sidecar_bundle["resource_destination"]}
                if formal_sidecar_bundle
                else {}
            ),
            "desktop.tauri.bundle.resources",
        ),
        _json_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json",
            ("bundle", "createUpdaterArtifacts"),
            tauri_updater["create_updater_artifacts"],
            "desktop.tauri.bundle.create_updater_artifacts",
        ),
        _json_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json",
            ("plugins", "updater", "pubkey"),
            tauri_updater["pubkey"],
            "desktop.tauri.updater.pubkey",
        ),
        _json_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json",
            ("plugins", "updater", "endpoints"),
            tauri_updater["endpoints"],
            "desktop.tauri.updater.endpoints",
        ),
        _json_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json",
            ("plugins", "updater", "dangerousInsecureTransportProtocol"),
            tauri_updater["dangerous_insecure_transport_protocol"],
            "desktop.tauri.updater.dangerous_insecure_transport_protocol",
        ),
        _json_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json",
            ("plugins", "updater", "dangerousAcceptInvalidCerts"),
            tauri_updater["dangerous_accept_invalid_certs"],
            "desktop.tauri.updater.dangerous_accept_invalid_certs",
        ),
        _json_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json",
            ("plugins", "updater", "dangerousAcceptInvalidHostnames"),
            tauri_updater["dangerous_accept_invalid_hostnames"],
            "desktop.tauri.updater.dangerous_accept_invalid_hostnames",
        ),
        _json_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "tauri.conf.json",
            ("plugins", "updater", "windows", "installMode"),
            tauri_updater["windows_install_mode"],
            "desktop.tauri.updater.windows.install_mode",
        ),
        _text_marker_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "Cargo.toml",
            'tauri-plugin-updater = "2"',
            "present",
            "desktop.cargo.updater_dependency",
        ),
        _text_marker_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "src" / "main.rs",
            ".plugin(UpdaterPluginBuilder::new().build())",
            "present",
            "desktop.main_rs.updater_plugin_registered",
        ),
        _text_marker_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "src" / "main.rs",
            "bundled_sidecar_python(resource_dir)",
            "present",
            "desktop.main_rs.formal_bundle_python_runtime",
        ),
        _text_marker_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "src" / "main.rs",
            "ASTRABRIDGE_SIDECAR_ORIGIN",
            "present",
            "desktop.main_rs.formal_bundle_origin_env",
        ),
        _forbidden_text_marker_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "src" / "main.rs",
            'let bundled_script = bundled_dir.join("sidecar_server.py");',
            "desktop.main_rs.legacy_bundled_script_fallback_removed",
        ),
        _text_marker_binding(
            root / "apps" / "astrabridge-desktop" / "src-tauri" / "src" / "sidecar_supervision.rs",
            "pub launch_arguments: Vec<String>",
            "present",
            "desktop.sidecar_supervision.launch_arguments",
        ),
        _release_function_binding(root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "__init__.py", "__version__ = release_product_version()", version, "sidecar.__version__"),
        _release_function_binding(root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "astrabridge_capabilities_mcp_server.py", "SERVER_VERSION = release_product_version()", version, "mcp.capabilities.server_version"),
        _release_function_binding(root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "astrabridge_web_mcp_server.py", "SERVER_VERSION = release_product_version()", version, "mcp.web.server_version"),
        _release_function_binding(root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "yunwu_image_mcp_server.py", "SERVER_VERSION = release_product_version()", version, "mcp.yunwu.server_version"),
        _release_function_binding(root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "codex_mcp_probe_fixture_server.py", "SERVER_VERSION = release_product_version()", version, "mcp.probe.server_version"),
        _release_function_binding(root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "app_server_client.py", '"version": release_product_version()', version, "desktop.client_info.version"),
        _release_function_binding(root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "mcp_broker_service.py", '"version": release_product_version()', version, "broker.client_info.version"),
        _json_binding(
            root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "protocol" / "compatibility_manifest.json",
            ("target_schema",),
            protocol_version,
            "protocol.compatibility.target_schema",
        ),
        _json_binding(
            root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "protocol" / "compatibility_manifest.json",
            ("write_schema",),
            protocol_version,
            "protocol.compatibility.write_schema",
        ),
    ]
    if formal_sidecar_bundle:
        bundle_root = root / str(formal_sidecar_bundle["resource_path"])
        bundle_manifest = bundle_root / "bundle-manifest.json"
        launcher_path = bundle_root / str(formal_sidecar_bundle["launcher_path"])
        package_root = bundle_root / str(formal_sidecar_bundle["package_root"])
        if bundle_manifest.exists():
            bindings.extend(
                [
                    _json_binding(
                        bundle_manifest,
                        ("schema_version",),
                        formal_sidecar_bundle["schema_version"],
                        "sidecar.formal_bundle.manifest.schema_version",
                    ),
                    _json_binding(
                        bundle_manifest,
                        ("release_version",),
                        version,
                        "sidecar.formal_bundle.manifest.release_version",
                    ),
                    _json_binding(
                        bundle_manifest,
                        ("origin",),
                        formal_sidecar_bundle["origin"],
                        "sidecar.formal_bundle.manifest.origin",
                    ),
                    _json_binding(
                        bundle_manifest,
                        ("launcher_mode",),
                        formal_sidecar_bundle["launcher_mode"],
                        "sidecar.formal_bundle.manifest.launcher_mode",
                    ),
                    _json_binding(
                        bundle_manifest,
                        ("launch_arguments",),
                        formal_sidecar_bundle["launch_arguments"],
                        "sidecar.formal_bundle.manifest.launch_arguments",
                    ),
                    _path_exists_binding(
                        launcher_path,
                        True,
                        "sidecar.formal_bundle.launcher_exists",
                    ),
                    _path_exists_binding(
                        package_root,
                        True,
                        "sidecar.formal_bundle.package_root_exists",
                    ),
                ]
            )
    return bindings


def evaluate_release_bindings(bindings: Iterable[dict[str, Any]]) -> dict[str, Any]:
    binding_list = [dict(item) for item in bindings]
    mismatches = [
        {
            "binding_id": item["binding_id"],
            "path": item["path"],
            "expected": item["expected"],
            "actual": item["actual"],
        }
        for item in binding_list
        if str(item.get("actual") or "") != str(item.get("expected") or "")
    ]
    return {
        "status": "pass" if not mismatches else "fail",
        "binding_count": len(binding_list),
        "mismatch_count": len(mismatches),
        "bindings": binding_list,
        "mismatches": mismatches,
    }


def evaluate_updater_contract(identity: dict[str, Any]) -> dict[str, Any]:
    updater = dict(identity.get("updater") or {})
    normalized_channels = _normalize_updater_channels(identity)
    kill_switch = _normalize_updater_kill_switch(identity)
    tauri_updater = expected_tauri_updater_config(identity)
    errors: list[str] = []
    warnings: list[str] = []

    manifest_version = str(updater.get("manifest_version") or "").strip()
    if manifest_version != RELEASE_UPDATER_MANIFEST_SCHEMA_VERSION:
        errors.append(
            "updater.manifest_version must match the canonical updater manifest schema version."
        )

    if not normalized_channels:
        errors.append("updater.channels must declare at least one release channel.")

    channel_ids = [str(item["channel"]) for item in normalized_channels]
    duplicate_ids = sorted({channel_id for channel_id in channel_ids if channel_ids.count(channel_id) > 1})
    if duplicate_ids:
        errors.append(f"updater.channels contains duplicate channel ids: {', '.join(duplicate_ids)}.")

    missing_required_channels = [
        channel for channel in EXPECTED_UPDATER_CHANNELS if channel not in channel_ids
    ]
    if missing_required_channels:
        errors.append(
            "updater.channels must explicitly declare stable/beta/canary channels; missing "
            + ", ".join(missing_required_channels)
            + "."
        )

    default_channel = str(updater.get("default_channel") or "").strip()
    if not default_channel:
        errors.append("updater.default_channel is required.")
    elif default_channel not in channel_ids:
        errors.append("updater.default_channel must match one of the declared updater channels.")

    pubkey = str(updater.get("pubkey") or "").strip()
    if not pubkey:
        errors.append("updater.pubkey is required.")
    elif "\n" not in pubkey:
        warnings.append("updater.pubkey should carry the full publickey.pem contents, not just a single-line token.")

    if not isinstance(updater.get("create_updater_artifacts"), bool):
        errors.append("updater.create_updater_artifacts must be a boolean.")
    elif not bool(updater.get("create_updater_artifacts")):
        errors.append("updater.create_updater_artifacts must stay enabled for the formal release path.")

    for channel in normalized_channels:
        channel_id = str(channel["channel"])
        manifest_path = str(channel["manifest_path"])
        endpoint = str(channel["endpoint"])
        rollout = str(channel["rollout"])
        expected_manifest_path = f"release/updater/{channel_id}.json"

        if manifest_path != expected_manifest_path:
            errors.append(
                f"updater.channels[{channel_id}] manifest_path must be {expected_manifest_path}."
            )

        parsed = urlparse(endpoint)
        if parsed.scheme != "https":
            errors.append(
                f"updater.channels[{channel_id}] endpoint must use https."
            )
        for token in EXPECTED_UPDATER_ENDPOINT_TOKENS:
            if token not in endpoint:
                errors.append(
                    f"updater.channels[{channel_id}] endpoint must include {token}."
                )
        if not rollout:
            errors.append(
                f"updater.channels[{channel_id}] rollout is required."
            )

    if kill_switch["manifest_path"] != "release/updater/kill-switch.json":
        errors.append(
            "updater.kill_switch.manifest_path must be release/updater/kill-switch.json."
        )
    if not kill_switch["default_mode"]:
        errors.append("updater.kill_switch.default_mode is required.")
    if not isinstance(kill_switch["allow_disable_updates"], bool):
        errors.append("updater.kill_switch.allow_disable_updates must be a boolean.")

    if not tauri_updater["endpoints"]:
        errors.append("expected Tauri updater endpoints could not be derived from the release identity.")

    return {
        "status": "pass" if not errors else "fail",
        "manifest_version": manifest_version,
        "default_channel": default_channel,
        "channel_count": len(normalized_channels),
        "channels": normalized_channels,
        "kill_switch": kill_switch,
        "tauri_updater": tauri_updater,
        "errors": errors,
        "warnings": warnings,
    }


def desktop_update_status(
    *,
    repo_root: str | Path | None = None,
    project: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve() if repo_root else _REPO_ROOT
    identity = load_release_identity(root / "release" / "astrabridge-release-identity.json")
    updater_contract = evaluate_updater_contract(identity)
    selected_channel = _selected_updater_channel(identity, project)
    default_channel = str(updater_contract.get("default_channel") or "").strip()
    channels = []
    for channel in list(updater_contract.get("channels") or []):
        channel_id = str(channel.get("channel") or "").strip()
        if not channel_id:
            continue
        channels.append(
            {
                **channel,
                "selected": channel_id == selected_channel,
                "default": channel_id == default_channel,
            }
        )
    selected_record = next((channel for channel in channels if str(channel.get("channel") or "") == selected_channel), None)
    kill_switch = _projected_kill_switch_state(root=root, identity=identity, updater_contract=updater_contract)
    formal_bundle = _formal_bundle_runtime_status(root=root, identity=identity)
    bundle_contract = expected_formal_sidecar_bundle(identity)
    latest_rehearsal = _latest_windows_update_rehearsal(root)
    warnings = list(dict(updater_contract).get("warnings") or [])
    if str(updater_contract.get("status") or "fail") != "pass":
        warnings.append("updater_contract_not_ready")
    return {
        "schema_version": DESKTOP_UPDATE_STATUS_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "release_version": str(identity.get("release_version") or "").strip(),
        "selected_channel": selected_channel,
        "default_channel": default_channel,
        "channels": channels,
        "selected_endpoint": str((selected_record or {}).get("endpoint") or "").strip(),
        "updater_contract_status": str(updater_contract.get("status") or "fail"),
        "kill_switch": kill_switch,
        "formal_bundle": formal_bundle,
        "tauri_runtime": {
            **dict(updater_contract.get("tauri_updater") or {}),
            "default_channel": default_channel,
        },
        "latest_rehearsal": latest_rehearsal,
        "warnings": warnings,
        "project_update_channel": str(dict(dict(project or {}).get("ui_preferences") or {}).get("update_channel") or "").strip() or None,
    }


def stage_release_workspace(
    *,
    repo_root: str | Path | None = None,
    output_root: str | Path,
    stage_name: str,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve() if repo_root else _REPO_ROOT
    manifest = identity or load_release_identity(root / "release" / "astrabridge-release-identity.json")
    target_root = Path(output_root).expanduser().resolve() / stage_name
    stage_workspace = target_root / "workspace"
    reports_dir = target_root / "reports"
    for path in (stage_workspace, reports_dir):
        path.mkdir(parents=True, exist_ok=True)

    copied_files: list[dict[str, Any]] = []
    for source in sorted(_iter_release_staging_sources(root)):
        relative = source.relative_to(root)
        destination = stage_workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied_files.append(
            {
                "path": relative.as_posix(),
                "size_bytes": destination.stat().st_size,
                "sha256": _hash_file(destination),
            }
        )

    updater_manifests = _write_updater_manifests(
        stage_workspace=stage_workspace,
        identity=manifest,
    )
    sidecar_bundle = _write_formal_sidecar_bundle(
        stage_workspace=stage_workspace,
        repo_root=root,
        identity=manifest,
    )
    allowlist_manifest = {
        "schema_version": RELEASE_STAGING_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "rules": _STAGING_INCLUDE_RULES,
        "forbidden_paths": list(dict(manifest.get("staging") or {}).get("forbidden_paths") or []),
        "updater_manifest_paths": updater_manifests,
        "sidecar_bundle": sidecar_bundle,
    }
    allowlist_path = reports_dir / "allowlist-manifest.json"
    inventory_path = reports_dir / "inventory.json"
    sbom_input_path = reports_dir / "sbom-input.json"
    source_provenance_path = reports_dir / "source-provenance.json"
    write_json(allowlist_path, allowlist_manifest)
    write_json(inventory_path, {"files": copied_files})
    write_json(
        sbom_input_path,
        {
            "schema_version": "astrabridge-sbom-input-v1",
            "release_version": manifest.get("release_version"),
            "lockfiles": _lockfile_digests(root),
            "package_files": [item["path"] for item in copied_files if item["path"].endswith(("package.json", "Cargo.toml", "pyproject.toml"))],
        },
    )
    write_json(
        source_provenance_path,
        {
            "schema_version": "astrabridge-release-source-provenance-v1",
            "generated_at": now_iso(),
            "source_commit": _git_output(["git", "rev-parse", "HEAD"], root),
            "source_branch": _git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], root),
            "source_dirty": bool(_git_output(["git", "status", "--porcelain"], root)),
            "release_identity_sha256": _hash_file(root / "release" / "astrabridge-release-identity.json"),
        },
    )
    forbidden_violations = _scan_forbidden_stage_paths(
        stage_workspace=stage_workspace,
        forbidden_names={str(item) for item in list(dict(manifest.get("staging") or {}).get("forbidden_paths") or [])},
    )
    return {
        "schema_version": RELEASE_STAGING_SCHEMA_VERSION,
        "status": "pass" if not forbidden_violations and str(sidecar_bundle.get("status") or "pass") == "pass" else "fail",
        "stage_name": stage_name,
        "stage_workspace": str(stage_workspace),
        "file_count": len(copied_files),
        "copied_files": copied_files,
        "forbidden_path_violations": forbidden_violations,
        "sidecar_bundle": sidecar_bundle,
        "artifact_paths": {
            "allowlist_manifest_json": str(allowlist_path),
            "inventory_json": str(inventory_path),
            "sbom_input_json": str(sbom_input_path),
            "source_provenance_json": str(source_provenance_path),
        },
        "updater_manifests": updater_manifests,
    }


def compare_staging_runs(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    first_inventory = {str(item["path"]): str(item["sha256"]) for item in list(first.get("copied_files") or [])}
    second_inventory = {str(item["path"]): str(item["sha256"]) for item in list(second.get("copied_files") or [])}
    differing_paths = sorted(
        path
        for path in sorted(set(first_inventory) | set(second_inventory))
        if first_inventory.get(path) != second_inventory.get(path)
    )
    return {
        "status": "pass" if not differing_paths else "fail",
        "first_file_count": len(first_inventory),
        "second_file_count": len(second_inventory),
        "differing_paths": differing_paths,
    }


def run_release_readiness_gate(
    *,
    repo_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve() if repo_root else _REPO_ROOT
    identity = load_release_identity(root / "release" / "astrabridge-release-identity.json")
    created_at = now_iso()
    resolved_run_id = slugify(run_id or f"release-readiness-{created_at}", default="release-readiness")
    run_root = (Path(artifact_root).expanduser().resolve() / resolved_run_id) if artifact_root else (root / "PRIVATE" / "release-readiness" / resolved_run_id)
    reports_dir = run_root / "reports"
    stages_dir = run_root / "stages"
    validations_dir = run_root / "validations"
    for path in (reports_dir, stages_dir, validations_dir):
        path.mkdir(parents=True, exist_ok=True)

    bindings = collect_release_bindings(root, identity)
    binding_evaluation = evaluate_release_bindings(bindings)
    write_json(validations_dir / "binding-evaluation.json", binding_evaluation)

    updater_contract = evaluate_updater_contract(identity)
    write_json(validations_dir / "updater-contract.json", updater_contract)

    stage_a = stage_release_workspace(repo_root=root, output_root=stages_dir, stage_name="stage-a", identity=identity)
    stage_b = stage_release_workspace(repo_root=root, output_root=stages_dir, stage_name="stage-b", identity=identity)
    write_json(validations_dir / "stage-a.json", stage_a)
    write_json(validations_dir / "stage-b.json", stage_b)
    deterministic_comparison = compare_staging_runs(stage_a, stage_b)
    write_json(validations_dir / "deterministic-comparison.json", deterministic_comparison)

    staged_bindings = collect_release_bindings(Path(stage_a["stage_workspace"]), identity)
    staged_binding_evaluation = evaluate_release_bindings(staged_bindings)
    write_json(validations_dir / "staged-binding-evaluation.json", staged_binding_evaluation)

    checks = {
        "binding_evaluation": binding_evaluation["status"],
        "updater_contract": updater_contract["status"],
        "stage_a": stage_a["status"],
        "stage_b": stage_b["status"],
        "deterministic_comparison": deterministic_comparison["status"],
        "staged_binding_evaluation": staged_binding_evaluation["status"],
    }
    status = "pass" if all(value == "pass" for value in checks.values()) else "fail"
    summary_path = reports_dir / "summary.json"
    report_path = reports_dir / "report.md"
    summary = {
        "schema_version": RELEASE_READINESS_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": created_at,
        "status": status,
        "release_identity_path": str(root / "release" / "astrabridge-release-identity.json"),
        "release_version": identity.get("release_version"),
        "checks": checks,
        "binding_evaluation": binding_evaluation,
        "updater_contract": updater_contract,
        "staging_runs": {
            "stage_a": stage_a,
            "stage_b": stage_b,
        },
        "deterministic_comparison": deterministic_comparison,
        "staged_binding_evaluation": staged_binding_evaluation,
        "artifact_paths": {
            "run_root": str(run_root),
            "reports_dir": str(reports_dir),
            "validations_dir": str(validations_dir),
            "stages_dir": str(stages_dir),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
        },
    }
    write_json(summary_path, summary)
    report_path.write_text(render_release_readiness_report(summary), encoding="utf-8", newline="\n")
    return summary


def run_windows_update_rehearsal(
    *,
    repo_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
    project: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve() if repo_root else _REPO_ROOT
    identity = load_release_identity(root / "release" / "astrabridge-release-identity.json")
    created_at = now_iso()
    selected_channel = _selected_updater_channel(identity, project)
    resolved_run_id = slugify(
        run_id or f"windows-update-rehearsal-{selected_channel}-{created_at}",
        default="windows-update-rehearsal",
    )
    resolved_artifact_root = Path(artifact_root).expanduser().resolve() if artifact_root else (root / "PRIVATE" / "release-readiness")
    readiness = run_release_readiness_gate(
        repo_root=root,
        artifact_root=resolved_artifact_root,
        run_id=resolved_run_id,
    )
    run_root = Path(str(dict(readiness.get("artifact_paths") or {}).get("run_root") or resolved_artifact_root / resolved_run_id))
    rehearsal_root = run_root / "windows-update-rehearsal"
    isolated_root = rehearsal_root / "isolated-install-root"
    reports_dir = rehearsal_root / "reports"
    generations_dir = isolated_root / "generations"
    for path in (rehearsal_root, isolated_root, reports_dir, generations_dir):
        path.mkdir(parents=True, exist_ok=True)

    updater_contract = evaluate_updater_contract(identity)
    kill_switch = _projected_kill_switch_state(root=root, identity=identity, updater_contract=updater_contract)
    formal_bundle = _formal_bundle_runtime_status(root=root, identity=identity)
    bundle_contract = expected_formal_sidecar_bundle(identity)
    stage_a = dict(dict(readiness.get("staging_runs") or {}).get("stage_a") or {})
    stage_workspace = Path(str(stage_a.get("stage_workspace") or ""))
    errors: list[str] = []

    selected_record = next(
        (
            channel
            for channel in list(dict(updater_contract).get("channels") or [])
            if str(channel.get("channel") or "").strip() == selected_channel
        ),
        None,
    )
    if not selected_record:
        errors.append(f"selected updater channel is not declared: {selected_channel}")
    if str(readiness.get("status") or "fail") != "pass":
        errors.append("release_readiness_gate_failed")
    if not stage_workspace.exists():
        errors.append(f"missing staged workspace: {stage_workspace}")

    channel_manifest_path = stage_workspace / str((selected_record or {}).get("manifest_path") or "")
    kill_switch_manifest_path = stage_workspace / str(dict(dict(identity.get("updater") or {}).get("kill_switch") or {}).get("manifest_path") or "")
    bundle_root = stage_workspace / str(dict(bundle_contract).get("resource_path") or "")
    bundle_manifest_path = bundle_root / "bundle-manifest.json"
    launcher_path = bundle_root / str(dict(bundle_contract).get("launcher_path") or "")
    package_root = bundle_root / str(dict(bundle_contract).get("package_root") or "")
    skills_root = bundle_root / str(dict(bundle_contract).get("skills_root") or "")

    for required_path, label in (
        (channel_manifest_path, "selected channel manifest"),
        (kill_switch_manifest_path, "kill-switch manifest"),
        (bundle_manifest_path, "formal sidecar bundle manifest"),
        (launcher_path, "formal sidecar launcher"),
        (package_root, "formal sidecar package root"),
        (skills_root, "formal sidecar skills root"),
    ):
        if not required_path.exists():
            errors.append(f"missing {label}: {required_path}")

    channel_manifest = _read_json_if_exists(channel_manifest_path)
    kill_switch_manifest = _read_json_if_exists(kill_switch_manifest_path)
    bundle_manifest = _read_json_if_exists(bundle_manifest_path)
    updates_enabled = bool(kill_switch.get("updates_enabled"))
    active_kill_switch_mode = str(kill_switch.get("active_mode") or "").strip()

    clean_install_check = {
        "status": "pass",
        "staged_bundle_root": str(bundle_root),
        "bundle_manifest_path": str(bundle_manifest_path),
        "launcher_path": str(launcher_path),
        "package_root": str(package_root),
        "skills_root": str(skills_root),
        "selected_channel_manifest_path": str(channel_manifest_path),
        "kill_switch_manifest_path": str(kill_switch_manifest_path),
        "selected_channel_manifest_sha256": _hash_if_exists(channel_manifest_path),
        "kill_switch_manifest_sha256": _hash_if_exists(kill_switch_manifest_path),
        "bundle_manifest_sha256": _hash_if_exists(bundle_manifest_path),
        "checks": {
            "bundle_manifest_exists": bundle_manifest_path.exists(),
            "launcher_exists": launcher_path.exists(),
            "package_root_exists": package_root.exists(),
            "skills_root_exists": skills_root.exists(),
            "channel_manifest_exists": channel_manifest_path.exists(),
            "kill_switch_manifest_exists": kill_switch_manifest_path.exists(),
        },
        "notes": [],
    }
    if not all(bool(value) for value in dict(clean_install_check.get("checks") or {}).values()):
        clean_install_check["status"] = "fail"
        errors.append("clean_install_projection_missing_required_bundle_or_manifest")

    prior_generation_id = "generation-0000-prior"
    candidate_generation_id = "generation-0001-candidate"
    current_pointer_path = isolated_root / "current-generation.json"
    activation_journal_path = reports_dir / "activation-journal.json"
    recovery_matrix_root = reports_dir / "transaction-recovery"
    prior_manifest_path = generations_dir / prior_generation_id / "manifest.json"
    candidate_manifest_path = generations_dir / candidate_generation_id / "manifest.json"
    prior_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_manifest_path.parent.mkdir(parents=True, exist_ok=True)

    default_channel = str(updater_contract.get("default_channel") or "").strip() or selected_channel
    prior_manifest = {
        "schema_version": WINDOWS_UPDATE_REHEARSAL_SCHEMA_VERSION,
        "generation_id": prior_generation_id,
        "release_version": str(identity.get("release_version") or "").strip(),
        "channel": default_channel,
        "bundle_manifest_path": str(bundle_manifest_path),
        "bundle_manifest_sha256": _hash_if_exists(bundle_manifest_path),
        "selected_manifest_path": str(stage_workspace / f"release/updater/{default_channel}.json"),
        "selected_manifest_sha256": _hash_if_exists(stage_workspace / f"release/updater/{default_channel}.json"),
        "kill_switch_manifest_path": str(kill_switch_manifest_path),
        "kill_switch_manifest_sha256": _hash_if_exists(kill_switch_manifest_path),
    }
    candidate_manifest = {
        "schema_version": WINDOWS_UPDATE_REHEARSAL_SCHEMA_VERSION,
        "generation_id": candidate_generation_id,
        "release_version": str(identity.get("release_version") or "").strip(),
        "channel": selected_channel,
        "bundle_manifest_path": str(bundle_manifest_path),
        "bundle_manifest_sha256": _hash_if_exists(bundle_manifest_path),
        "selected_manifest_path": str(channel_manifest_path),
        "selected_manifest_sha256": _hash_if_exists(channel_manifest_path),
        "kill_switch_manifest_path": str(kill_switch_manifest_path),
        "kill_switch_manifest_sha256": _hash_if_exists(kill_switch_manifest_path),
    }
    write_json(prior_manifest_path, prior_manifest)
    write_json(candidate_manifest_path, candidate_manifest)
    health_checks = [
        {
            "check_id": "kill_switch_allows_updates",
            "status": "pass" if updates_enabled else "fail",
            "detail": active_kill_switch_mode or "unknown",
        },
        {
            "check_id": "formal_bundle_ready",
            "status": "pass" if clean_install_check["status"] == "pass" else "fail",
            "detail": str(bundle_manifest_path),
        },
    ]
    transaction = _execute_desktop_update_transaction(
        journal_path=activation_journal_path,
        current_pointer_path=current_pointer_path,
        prior_manifest=prior_manifest,
        candidate_manifest=candidate_manifest,
        updates_enabled=updates_enabled,
        health_checks=health_checks,
    )
    recovery_matrix = _exercise_desktop_update_transaction_recovery_matrix(
        output_root=recovery_matrix_root,
        prior_manifest=prior_manifest,
        candidate_manifest=candidate_manifest,
        updates_enabled=updates_enabled,
        health_checks=health_checks,
    )
    current_pointer = dict(_read_json_if_exists(current_pointer_path) or {})
    update_check_status = "pass"
    rollback_status = "pass"
    if not updates_enabled:
        update_check_status = "fail"
        rollback_status = "fail"
        errors.append(f"kill_switch_blocks_updates:{active_kill_switch_mode or 'unknown'}")
    if str(transaction.get("status") or "") != "committed":
        update_check_status = "fail"
        errors.append("desktop_update_transaction_did_not_commit")
    if str(current_pointer.get("generation_id") or "") != candidate_generation_id:
        update_check_status = "fail"
        errors.append("candidate_generation_activation_pointer_mismatch")
    rollback_candidate = next((item for item in list(recovery_matrix.get("scenarios") or []) if str(item.get("interrupted_stage") or "") == "activation_written"), None)
    if rollback_candidate is None or str(rollback_candidate.get("status") or "") != "pass":
        rollback_status = "fail"
        errors.append("interruption_recovery_matrix_missing_activation_rollback_proof")
    if str(recovery_matrix.get("status") or "fail") != "pass":
        rollback_status = "fail"
        errors.append("desktop_update_transaction_recovery_matrix_failed")

    update_check = {
        "status": update_check_status,
        "selected_channel": selected_channel,
        "selected_endpoint": str((selected_record or {}).get("endpoint") or "").strip(),
        "kill_switch_mode": active_kill_switch_mode,
        "updates_enabled": updates_enabled,
        "channel_manifest_path": str(channel_manifest_path),
        "channel_manifest_sha256": _hash_if_exists(channel_manifest_path),
        "activation_journal_path": str(activation_journal_path),
        "transaction_status": str(transaction.get("status") or ""),
    }
    rollback_check = {
        "status": rollback_status if update_check_status == "pass" else "fail",
        "current_pointer_path": str(current_pointer_path),
        "rollback_generation_id": prior_generation_id,
        "rollback_entry_manifest_path": str(prior_manifest_path),
        "rollback_entry_manifest_sha256": _hash_if_exists(prior_manifest_path),
        "recovery_matrix_path": str(recovery_matrix_root / "recovery-matrix.json"),
    }

    status = "pass" if not errors and clean_install_check["status"] == "pass" and update_check["status"] == "pass" and rollback_check["status"] == "pass" else "fail"
    summary_path = rehearsal_root / "summary.json"
    report_path = rehearsal_root / "report.md"
    summary = {
        "schema_version": WINDOWS_UPDATE_REHEARSAL_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": created_at,
        "status": status,
        "release_version": str(identity.get("release_version") or "").strip(),
        "selected_channel": selected_channel,
        "default_channel": default_channel,
        "kill_switch": kill_switch,
        "updater_contract_status": str(updater_contract.get("status") or "fail"),
        "release_readiness_run_root": str(run_root),
        "release_readiness_summary_json": str(dict(readiness.get("artifact_paths") or {}).get("summary_json") or ""),
        "clean_install_check": clean_install_check,
        "update_check": update_check,
        "rollback_check": rollback_check,
        "transaction": {
            "status": str(transaction.get("status") or "fail"),
            "current_stage": str(transaction.get("current_stage") or ""),
            "journal_path": str(activation_journal_path),
            "recovery_matrix_path": str(recovery_matrix_root / "recovery-matrix.json"),
        },
        "recovery_matrix": recovery_matrix,
        "bundle_manifest": bundle_manifest,
        "selected_channel_manifest": channel_manifest,
        "kill_switch_manifest": kill_switch_manifest,
        "artifact_paths": {
            "run_root": str(run_root),
            "rehearsal_root": str(rehearsal_root),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
            "activation_journal_json": str(activation_journal_path),
            "transaction_recovery_matrix_json": str(recovery_matrix_root / "recovery-matrix.json"),
            "current_pointer_json": str(current_pointer_path),
            "prior_generation_manifest_json": str(prior_manifest_path),
            "candidate_generation_manifest_json": str(candidate_manifest_path),
        },
        "errors": errors,
    }
    write_json(summary_path, summary)
    report_path.write_text(render_windows_update_rehearsal_report(summary), encoding="utf-8", newline="\n")
    return summary


def render_release_readiness_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Release Readiness",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Created: `{summary.get('created_at')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Release version: `{summary.get('release_version')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in dict(summary.get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    comparison = dict(summary.get("deterministic_comparison") or {})
    lines.extend(
        [
            "",
            "## Deterministic Staging",
            "",
            f"- first file count: `{comparison.get('first_file_count')}`",
            f"- second file count: `{comparison.get('second_file_count')}`",
            f"- differing paths: `{json.dumps(comparison.get('differing_paths') or [], ensure_ascii=False)}`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _iter_release_staging_sources(root: Path) -> Iterable[Path]:
    seen: set[str] = set()
    for rule in _STAGING_INCLUDE_RULES:
        kind = str(rule.get("kind") or "")
        if kind == "file":
            path = root / str(rule["path"])
            if path.exists() and path.is_file() and _include_stage_path(path.relative_to(root)):
                key = path.relative_to(root).as_posix()
                if key not in seen:
                    seen.add(key)
                    yield path
            continue
        if kind == "glob":
            for path in sorted(root.glob(str(rule["pattern"]))):
                if path.is_file() and _include_stage_path(path.relative_to(root)):
                    key = path.relative_to(root).as_posix()
                    if key not in seen:
                        seen.add(key)
                        yield path
            continue
        if kind == "tree":
            base = root / str(rule["path"])
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(root)
                if not _include_stage_path(relative):
                    continue
                key = relative.as_posix()
                if key not in seen:
                    seen.add(key)
                    yield path


def _include_stage_path(relative: Path) -> bool:
    text = relative.as_posix()
    if any(part in _EXCLUDED_PARTS for part in relative.parts):
        return False
    lowered = text.lower()
    if lowered.endswith(_TEST_FILE_SUFFIXES):
        return False
    if lowered.endswith((".pyc", ".pyo")):
        return False
    return True


def _scan_forbidden_stage_paths(*, stage_workspace: Path, forbidden_names: set[str]) -> list[str]:
    violations: list[str] = []
    normalized = {item for item in forbidden_names if item}
    for path in sorted(stage_workspace.rglob("*")):
        relative = path.relative_to(stage_workspace)
        if any(part in normalized for part in relative.parts):
            violations.append(relative.as_posix())
    return violations


def render_windows_update_rehearsal_report(summary: dict[str, Any]) -> str:
    clean_install = dict(summary.get("clean_install_check") or {})
    update_check = dict(summary.get("update_check") or {})
    rollback_check = dict(summary.get("rollback_check") or {})
    transaction = dict(summary.get("transaction") or {})
    recovery_matrix = dict(summary.get("recovery_matrix") or {})
    lines = [
        "# Windows Update Rehearsal",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Created: `{summary.get('created_at')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Release version: `{summary.get('release_version')}`",
        f"- Selected channel: `{summary.get('selected_channel')}`",
        "",
        "## Checks",
        "",
        f"- Clean install projection: `{clean_install.get('status')}`",
        f"- Channel-aware update activation: `{update_check.get('status')}`",
        f"- Rollback pointer restore: `{rollback_check.get('status')}`",
        "",
        "## Rollback Entry Points",
        "",
        f"- Current pointer: `{rollback_check.get('current_pointer_path')}`",
        f"- Rollback manifest: `{rollback_check.get('rollback_entry_manifest_path')}`",
        f"- Activation journal: `{update_check.get('activation_journal_path')}`",
    ]
    if transaction:
        lines.extend(
            [
                "",
                "## Transaction Journal",
                "",
                f"- Status: `{transaction.get('status')}`",
                f"- Current stage: `{transaction.get('current_stage')}`",
                f"- Journal path: `{transaction.get('journal_path')}`",
                f"- Recovery matrix path: `{transaction.get('recovery_matrix_path')}`",
            ]
        )
    if recovery_matrix:
        lines.extend(
            [
                "",
                "## Recovery Matrix",
                "",
                f"- Status: `{recovery_matrix.get('status')}`",
                f"- Scenario count: `{recovery_matrix.get('scenario_count')}`",
            ]
        )
    errors = list(summary.get("errors") or [])
    if errors:
        lines.extend(["", "## Errors", ""])
        for error in errors:
            lines.append(f"- `{error}`")
    return "\n".join(lines).rstrip() + "\n"


def _execute_desktop_update_transaction(
    *,
    journal_path: Path,
    current_pointer_path: Path,
    prior_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    updates_enabled: bool,
    health_checks: list[dict[str, Any]],
    interruption_stage: str | None = None,
) -> dict[str, Any]:
    transaction = {
        "schema_version": UPDATE_TRANSACTION_SCHEMA_VERSION,
        "transaction_id": slugify(f"{prior_manifest['generation_id']}-{candidate_manifest['generation_id']}", default="desktop-update-transaction"),
        "track_id": "desktop_formal_bundle",
        "status": "running",
        "current_stage": "initialized",
        "started_at": now_iso(),
        "completed_at": None,
        "current_pointer_path": str(current_pointer_path),
        "prior_generation": _generation_reference(prior_manifest),
        "candidate_generation": _generation_reference(candidate_manifest),
        "retained_old_generation_until_healthcheck": True,
        "health_checks": [],
        "history": [],
    }
    _write_generation_pointer(current_pointer_path, prior_manifest, reason="transaction_initialized")
    _advance_update_transaction(transaction, journal_path, "initialized", pointer_generation_id=str(prior_manifest.get("generation_id") or ""))
    if interruption_stage == "initialized":
        return _recover_desktop_update_transaction(
            journal_path=journal_path,
            current_pointer_path=current_pointer_path,
            prior_manifest=prior_manifest,
            candidate_manifest=candidate_manifest,
            interrupted_stage="initialized",
        )

    _advance_update_transaction(transaction, journal_path, "candidate_staged", pointer_generation_id=str(prior_manifest.get("generation_id") or ""))
    if interruption_stage == "candidate_staged":
        return _recover_desktop_update_transaction(
            journal_path=journal_path,
            current_pointer_path=current_pointer_path,
            prior_manifest=prior_manifest,
            candidate_manifest=candidate_manifest,
            interrupted_stage="candidate_staged",
        )

    _write_generation_pointer(current_pointer_path, candidate_manifest, reason="candidate_activation_written")
    _advance_update_transaction(transaction, journal_path, "activation_written", pointer_generation_id=str(candidate_manifest.get("generation_id") or ""))
    if interruption_stage == "activation_written":
        return _recover_desktop_update_transaction(
            journal_path=journal_path,
            current_pointer_path=current_pointer_path,
            prior_manifest=prior_manifest,
            candidate_manifest=candidate_manifest,
            interrupted_stage="activation_written",
        )

    transaction["health_checks"] = list(health_checks)
    if updates_enabled and all(str(item.get("status") or "fail") == "pass" for item in health_checks):
        _advance_update_transaction(transaction, journal_path, "healthcheck_passed", pointer_generation_id=str(candidate_manifest.get("generation_id") or ""))
        if interruption_stage == "healthcheck_passed":
            return _recover_desktop_update_transaction(
                journal_path=journal_path,
                current_pointer_path=current_pointer_path,
                prior_manifest=prior_manifest,
                candidate_manifest=candidate_manifest,
                interrupted_stage="healthcheck_passed",
            )
        transaction["status"] = "committed"
        transaction["completed_at"] = now_iso()
        _advance_update_transaction(transaction, journal_path, "committed", pointer_generation_id=str(candidate_manifest.get("generation_id") or ""))
        return transaction

    _write_generation_pointer(current_pointer_path, prior_manifest, reason="rollback_after_failed_healthcheck")
    transaction["status"] = "rolled_back"
    transaction["completed_at"] = now_iso()
    _advance_update_transaction(transaction, journal_path, "rolled_back", pointer_generation_id=str(prior_manifest.get("generation_id") or ""))
    return transaction


def _recover_desktop_update_transaction(
    *,
    journal_path: Path,
    current_pointer_path: Path,
    prior_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    interrupted_stage: str,
) -> dict[str, Any]:
    transaction = dict(_read_json_if_exists(journal_path) or {})
    if not transaction:
        raise ValueError(f"Missing update transaction journal: {journal_path}")
    transaction["interrupted_stage"] = interrupted_stage
    current_stage = str(transaction.get("current_stage") or interrupted_stage)
    if current_stage in {"healthcheck_passed", "committed"}:
        _write_generation_pointer(current_pointer_path, candidate_manifest, reason="recovered_commit_after_healthcheck")
        transaction["status"] = "committed"
        transaction["completed_at"] = now_iso()
        _advance_update_transaction(transaction, journal_path, "committed", pointer_generation_id=str(candidate_manifest.get("generation_id") or ""), note="recovered_after_interruption")
        return transaction
    _write_generation_pointer(current_pointer_path, prior_manifest, reason="recovered_rollback_before_healthcheck")
    transaction["status"] = "rolled_back"
    transaction["completed_at"] = now_iso()
    _advance_update_transaction(transaction, journal_path, "rolled_back", pointer_generation_id=str(prior_manifest.get("generation_id") or ""), note="recovered_after_interruption")
    return transaction


def _exercise_desktop_update_transaction_recovery_matrix(
    *,
    output_root: Path,
    prior_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    updates_enabled: bool,
    health_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    scenarios: list[dict[str, Any]] = []
    for stage in ("initialized", "candidate_staged", "activation_written", "healthcheck_passed"):
        scenario_root = output_root / stage
        scenario_root.mkdir(parents=True, exist_ok=True)
        journal_path = scenario_root / "transaction-journal.json"
        pointer_path = scenario_root / "current-generation.json"
        result = _execute_desktop_update_transaction(
            journal_path=journal_path,
            current_pointer_path=pointer_path,
            prior_manifest=prior_manifest,
            candidate_manifest=candidate_manifest,
            updates_enabled=updates_enabled,
            health_checks=health_checks,
            interruption_stage=stage,
        )
        pointer = dict(_read_json_if_exists(pointer_path) or {})
        expected_generation = (
            str(candidate_manifest.get("generation_id") or "")
            if stage == "healthcheck_passed"
            else str(prior_manifest.get("generation_id") or "")
        )
        scenarios.append(
            {
                "interrupted_stage": stage,
                "final_status": str(result.get("status") or "fail"),
                "final_stage": str(result.get("current_stage") or ""),
                "pointer_generation_id": str(pointer.get("generation_id") or ""),
                "expected_generation_id": expected_generation,
                "journal_path": str(journal_path),
                "pointer_path": str(pointer_path),
                "status": "pass"
                if str(pointer.get("generation_id") or "") == expected_generation
                and str(result.get("status") or "") in {"committed", "rolled_back"}
                else "fail",
            }
        )
    matrix = {
        "schema_version": UPDATE_TRANSACTION_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "scenario_count": len(scenarios),
        "status": "pass" if all(str(item.get("status") or "fail") == "pass" for item in scenarios) else "fail",
        "scenarios": scenarios,
    }
    _write_atomic_json(output_root / "recovery-matrix.json", matrix)
    return matrix


def _advance_update_transaction(
    transaction: dict[str, Any],
    journal_path: Path,
    stage: str,
    *,
    pointer_generation_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    transaction["current_stage"] = stage
    history = list(transaction.get("history") or [])
    history.append(
        {
            "stage": stage,
            "at": now_iso(),
            "pointer_generation_id": pointer_generation_id,
            "note": note,
        }
    )
    transaction["history"] = history
    _write_atomic_json(journal_path, transaction)
    return transaction


def _generation_reference(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "generation_id": str(manifest.get("generation_id") or "").strip(),
        "release_version": str(manifest.get("release_version") or "").strip(),
        "channel": str(manifest.get("channel") or "").strip(),
        "manifest_path": str(manifest.get("selected_manifest_path") or "").strip(),
        "manifest_sha256": manifest.get("selected_manifest_sha256"),
    }


def _generation_pointer_payload(manifest: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "schema_version": UPDATE_GENERATION_POINTER_SCHEMA_VERSION,
        "generation_id": str(manifest.get("generation_id") or "").strip(),
        "release_version": str(manifest.get("release_version") or "").strip(),
        "channel": str(manifest.get("channel") or "").strip(),
        "updated_at": now_iso(),
        "reason": reason,
    }


def _write_generation_pointer(path: Path, manifest: dict[str, Any], *, reason: str) -> None:
    _write_atomic_json(path, _generation_pointer_payload(manifest, reason=reason))


def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temp_path.replace(path)


def _write_updater_manifests(*, stage_workspace: Path, identity: dict[str, Any]) -> list[str]:
    # Generated updater manifests are staged under release/updater/ as the
    # canonical channel and kill-switch contract for future signed update flows.
    updater_root = stage_workspace / "release" / "updater"
    updater_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    updater = dict(identity.get("updater") or {})
    default_channel = str(updater.get("default_channel") or "").strip()
    kill_switch = _normalize_updater_kill_switch(identity)
    for channel in _normalize_updater_channels(identity):
        channel_id = str(channel["channel"])
        target = updater_root / f"{channel_id}.json"
        write_json(
            target,
            {
                "schema_version": RELEASE_UPDATER_MANIFEST_SCHEMA_VERSION,
                "channel": channel_id,
                "product_name": identity.get("product_name"),
                "package_identifier": identity.get("package_identifier"),
                "release_version": identity.get("release_version"),
                "protocol_schema_version": dict(identity.get("protocol") or {}).get("schema_version"),
                "manifest_path": channel["manifest_path"],
                "endpoint": channel["endpoint"],
                "rollout": channel["rollout"],
                "default_channel": channel_id == default_channel,
                "kill_switch_manifest_path": kill_switch["manifest_path"],
            },
        )
        written.append(str(target))
    kill_switch_target = updater_root / "kill-switch.json"
    write_json(
        kill_switch_target,
        {
            "schema_version": RELEASE_UPDATER_KILL_SWITCH_SCHEMA_VERSION,
            "product_name": identity.get("product_name"),
            "package_identifier": identity.get("package_identifier"),
            "default_channel": default_channel,
            "default_mode": kill_switch["default_mode"],
            "allow_disable_updates": kill_switch["allow_disable_updates"],
            "channels": [channel["channel"] for channel in _normalize_updater_channels(identity)],
        },
    )
    written.append(str(kill_switch_target))
    return written


def expected_tauri_updater_config(identity: dict[str, Any]) -> dict[str, Any]:
    updater = dict(identity.get("updater") or {})
    default_channel = str(updater.get("default_channel") or "").strip()
    channels = _normalize_updater_channels(identity)
    default_record = next((channel for channel in channels if str(channel["channel"]) == default_channel), None)
    endpoint = str(default_record["endpoint"]).strip() if default_record else ""
    return {
        "schema_version": TAURI_UPDATER_PLUGIN_SCHEMA_VERSION,
        "create_updater_artifacts": bool(updater.get("create_updater_artifacts")),
        "pubkey": str(updater.get("pubkey") or "").strip(),
        "endpoints": [endpoint] if endpoint else [],
        "dangerous_insecure_transport_protocol": False,
        "dangerous_accept_invalid_certs": False,
        "dangerous_accept_invalid_hostnames": False,
        "windows_install_mode": str(dict(updater.get("windows") or {}).get("install_mode") or "passive").strip(),
    }


def expected_formal_sidecar_bundle(identity: dict[str, Any]) -> dict[str, Any]:
    sidecar = dict(identity.get("sidecar") or {})
    bundle = dict(sidecar.get("formal_bundle") or {})
    if not bundle:
        return {}
    resource_path = str(bundle.get("resource_path") or "").strip()
    tauri_resource_source = str(bundle.get("tauri_resource_source") or "").strip()
    resource_destination = str(bundle.get("resource_destination") or "astrabridge-sidecar").strip()
    launcher_path = str(bundle.get("launcher_path") or "python-runtime/python.exe").strip()
    package_root = str(bundle.get("package_root") or "astrabridge_sidecar").strip()
    skills_root = str(bundle.get("skills_root") or "skills").strip()
    origin = str(bundle.get("origin") or "app_managed").strip()
    launcher_mode = str(bundle.get("launcher_mode") or "desktop-app-managed").strip()
    launch_arguments = list(bundle.get("launch_arguments") or ["-m", "astrabridge_sidecar.server"])
    pythonpath_entry = str(bundle.get("pythonpath_entry") or ".").strip() or "."
    allow_source_fallback = bool(bundle.get("allow_source_fallback_in_formal_package"))
    return {
        "schema_version": str(bundle.get("schema_version") or FORMAL_SIDECAR_BUNDLE_SCHEMA_VERSION).strip(),
        "resource_path": resource_path,
        "tauri_resource_source": tauri_resource_source,
        "resource_destination": resource_destination,
        "launcher_path": launcher_path,
        "launch_arguments": launch_arguments,
        "pythonpath_entry": pythonpath_entry,
        "package_root": package_root,
        "skills_root": skills_root,
        "origin": origin,
        "launcher_mode": launcher_mode,
        "allow_source_fallback_in_formal_package": allow_source_fallback,
    }


def _normalize_updater_channels(identity: dict[str, Any]) -> list[dict[str, str]]:
    updater = dict(identity.get("updater") or {})
    normalized: list[dict[str, str]] = []
    for raw_channel in list(updater.get("channels") or []):
        if isinstance(raw_channel, str):
            channel_id = raw_channel.strip()
            if not channel_id:
                continue
            normalized.append(
                {
                    "channel": channel_id,
                    "manifest_path": f"release/updater/{channel_id}.json",
                    "endpoint": "",
                    "rollout": "",
                }
            )
            continue
        if not isinstance(raw_channel, dict):
            continue
        channel_id = str(raw_channel.get("channel") or raw_channel.get("name") or "").strip()
        if not channel_id:
            continue
        normalized.append(
            {
                "channel": channel_id,
                "manifest_path": str(raw_channel.get("manifest_path") or f"release/updater/{channel_id}.json").strip(),
                "endpoint": str(raw_channel.get("endpoint") or "").strip(),
                "rollout": str(raw_channel.get("rollout") or "").strip(),
            }
        )
    return normalized


def _normalize_updater_kill_switch(identity: dict[str, Any]) -> dict[str, Any]:
    updater = dict(identity.get("updater") or {})
    kill_switch = dict(updater.get("kill_switch") or {})
    allow_disable_updates = kill_switch.get("allow_disable_updates")
    if isinstance(allow_disable_updates, bool):
        allow_disable = allow_disable_updates
    else:
        allow_disable = False
    return {
        "manifest_path": str(kill_switch.get("manifest_path") or "release/updater/kill-switch.json").strip(),
        "default_mode": str(kill_switch.get("default_mode") or "").strip(),
        "allow_disable_updates": allow_disable,
    }


def _selected_updater_channel(identity: dict[str, Any], project: dict[str, Any] | None) -> str:
    available = {str(channel["channel"]) for channel in _normalize_updater_channels(identity) if str(channel.get("channel") or "").strip()}
    requested = str(dict(dict(project or {}).get("ui_preferences") or {}).get("update_channel") or "").strip()
    if requested and requested in available:
        return requested
    return str(dict(identity.get("updater") or {}).get("default_channel") or "").strip() or "stable"


def _projected_kill_switch_state(
    *,
    root: Path,
    identity: dict[str, Any],
    updater_contract: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(updater_contract.get("kill_switch") or _normalize_updater_kill_switch(identity))
    manifest_path = str(normalized.get("manifest_path") or "").strip()
    disk_path = root / manifest_path if manifest_path else None
    disk_payload = _read_json_if_exists(disk_path)
    active_mode = str(
        dict(disk_payload or {}).get("active_mode")
        or dict(disk_payload or {}).get("mode")
        or dict(disk_payload or {}).get("default_mode")
        or normalized.get("default_mode")
        or ""
    ).strip()
    updates_enabled = active_mode.lower() not in {"deny", "disabled", "blocked", "off"}
    return {
        "manifest_path": manifest_path,
        "source_path": str(disk_path) if disk_path else manifest_path,
        "loaded_from_disk": bool(disk_payload),
        "default_mode": str(normalized.get("default_mode") or "").strip(),
        "active_mode": active_mode,
        "allow_disable_updates": bool(normalized.get("allow_disable_updates")),
        "updates_enabled": updates_enabled,
        "raw_manifest": disk_payload,
    }


def _formal_bundle_runtime_status(*, root: Path, identity: dict[str, Any]) -> dict[str, Any]:
    contract = expected_formal_sidecar_bundle(identity)
    if not contract:
        return {
            "status": "missing_contract",
            "resource_path": "",
            "launcher_path": "",
            "bundle_manifest_path": "",
        }
    bundle_root = root / str(contract["resource_path"])
    launcher_path = bundle_root / str(contract["launcher_path"])
    bundle_manifest_path = bundle_root / "bundle-manifest.json"
    package_root = bundle_root / str(contract["package_root"])
    skills_root = bundle_root / str(contract["skills_root"])
    return {
        "status": "ready" if bundle_manifest_path.exists() and launcher_path.exists() and package_root.exists() and skills_root.exists() else "incomplete",
        "resource_path": str(contract["resource_path"]),
        "launcher_path": str(launcher_path),
        "bundle_manifest_path": str(bundle_manifest_path),
        "bundle_manifest_exists": bundle_manifest_path.exists(),
        "launcher_exists": launcher_path.exists(),
        "package_root": str(package_root),
        "package_root_exists": package_root.exists(),
        "skills_root": str(skills_root),
        "skills_root_exists": skills_root.exists(),
        "package_root_contract": str(contract["package_root"]),
        "skills_root_contract": str(contract["skills_root"]),
    }


def _latest_windows_update_rehearsal(root: Path) -> dict[str, Any] | None:
    rehearsal_paths = sorted(
        (root / "PRIVATE" / "release-readiness").glob("*/windows-update-rehearsal/summary.json"),
        key=lambda item: item.stat().st_mtime if item.exists() else 0.0,
        reverse=True,
    )
    for summary_path in rehearsal_paths:
        payload = _read_json_if_exists(summary_path)
        if not payload:
            continue
        return {
            "status": str(payload.get("status") or "unknown"),
            "run_id": str(payload.get("run_id") or "").strip() or None,
            "selected_channel": str(payload.get("selected_channel") or "").strip() or None,
            "created_at": str(payload.get("created_at") or "").strip() or None,
            "summary_json": str(summary_path),
            "report_md": str(summary_path.with_name("report.md")),
            "run_root": str(summary_path.parents[1]),
        }
    return None


def _read_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _hash_if_exists(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    return _hash_file(path)


def _write_formal_sidecar_bundle(*, stage_workspace: Path, repo_root: Path, identity: dict[str, Any]) -> dict[str, Any]:
    contract = expected_formal_sidecar_bundle(identity)
    if not contract:
        return {
            "status": "pass",
            "skipped": True,
            "reason": "formal sidecar bundle contract not declared",
        }

    bundle_root = stage_workspace / str(contract["resource_path"])
    launcher_path = bundle_root / str(contract["launcher_path"])
    manifest_path = bundle_root / "bundle-manifest.json"
    source_venv = repo_root / "apps" / "astrabridge-sidecar" / ".venv"
    source_pyvenv = source_venv / "pyvenv.cfg"
    source_package_root = repo_root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar"
    source_skills_root = repo_root / "apps" / "astrabridge-sidecar" / "skills"
    sidecar_package_version = str(dict(identity.get("sidecar") or {}).get("package_version") or "").strip()

    errors: list[str] = []
    written_files: list[dict[str, Any]] = []
    if not source_pyvenv.exists():
        errors.append(f"missing sidecar bundle source venv config: {source_pyvenv}")
    if not source_package_root.exists():
        errors.append(f"missing sidecar package root: {source_package_root}")
    if errors:
        return {
            "status": "fail",
            "skipped": False,
            "bundle_root": str(bundle_root),
            "launcher_path": str(launcher_path),
            "manifest_path": str(manifest_path),
            "errors": errors,
            "written_files": written_files,
        }

    pyvenv = _read_pyvenv_cfg(source_pyvenv)
    python_home = Path(str(pyvenv.get("home") or "").strip())
    if not python_home.exists():
        errors.append(f"missing base python runtime referenced by {source_pyvenv}: {python_home}")
        return {
            "status": "fail",
            "skipped": False,
            "bundle_root": str(bundle_root),
            "launcher_path": str(launcher_path),
            "manifest_path": str(manifest_path),
            "errors": errors,
            "written_files": written_files,
        }

    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir(parents=True, exist_ok=True)

    python_runtime_root = bundle_root / "python-runtime"
    _copy_tree_filtered(
        python_home,
        python_runtime_root,
        excluded_parts={"__pycache__", "idlelib", "site-packages", "test", "tests", "tkinter", "ensurepip"},
        excluded_suffixes={".pyc", ".pyo"},
    )
    site_packages_source = source_venv / "Lib" / "site-packages"
    site_packages_destination = python_runtime_root / "Lib" / "site-packages"
    _copy_tree_filtered(
        site_packages_source,
        site_packages_destination,
        excluded_parts={"__pycache__", "test", "tests", "testing"},
        excluded_suffixes={".pyc", ".pyo"},
    )
    for path in list(site_packages_destination.glob("__editable__*")):
        if path.is_file():
            path.unlink()
    if sidecar_package_version:
        dist_info_root = site_packages_destination / f"astrabridge_sidecar-{sidecar_package_version}.dist-info"
        for path in [
            dist_info_root / "direct_url.json",
            dist_info_root / "uv_build.json",
            dist_info_root / "uv_cache.json",
        ]:
            if path.exists():
                path.unlink()

    _copy_tree_filtered(
        source_package_root,
        bundle_root / str(contract["package_root"]),
        excluded_parts={"__pycache__"},
        excluded_suffixes={".pyc", ".pyo"},
    )
    if source_skills_root.exists():
        _copy_tree_filtered(
            source_skills_root,
            bundle_root / str(contract["skills_root"]),
            excluded_parts={"__pycache__"},
            excluded_suffixes={".pyc", ".pyo"},
        )

    write_json(
        manifest_path,
        {
            "schema_version": contract["schema_version"],
            "generated_at": now_iso(),
            "release_version": identity.get("release_version"),
            "sidecar_package_version": sidecar_package_version,
            "python_entry": dict(identity.get("sidecar") or {}).get("python_entry"),
            "origin": contract["origin"],
            "launcher_mode": contract["launcher_mode"],
            "resource_destination": contract["resource_destination"],
            "launcher_path": contract["launcher_path"],
            "launch_arguments": contract["launch_arguments"],
            "pythonpath_entry": contract["pythonpath_entry"],
            "package_root": contract["package_root"],
            "skills_root": contract["skills_root"],
            "allow_source_fallback_in_formal_package": contract["allow_source_fallback_in_formal_package"],
        },
    )
    if not launcher_path.exists():
        errors.append(f"formal sidecar bundle launcher was not generated: {launcher_path}")

    for path in sorted(bundle_root.rglob("*")):
        if path.is_file():
            written_files.append(
                {
                    "path": path.relative_to(stage_workspace).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": _hash_file(path),
                }
            )

    return {
        "status": "pass" if not errors else "fail",
        "skipped": False,
        "bundle_root": str(bundle_root),
        "launcher_path": str(launcher_path),
        "manifest_path": str(manifest_path),
        "errors": errors,
        "written_files": written_files,
    }


def _json_binding(path: Path, key_path: tuple[str, ...], expected: str, binding_id: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    current: Any = payload
    for key in key_path:
        current = current[key]
    return {
        "binding_id": binding_id,
        "path": str(path),
        "expected": _canonical_binding_value(expected),
        "actual": _canonical_binding_value(current),
    }


def _toml_binding(path: Path, key_path: tuple[str, ...], expected: str, binding_id: str) -> dict[str, Any]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    current: Any = payload
    for key in key_path:
        current = current[key]
    return {
        "binding_id": binding_id,
        "path": str(path),
        "expected": _canonical_binding_value(expected),
        "actual": _canonical_binding_value(current),
    }


def _regex_binding(path: Path, pattern: re.Pattern[str], expected: str, binding_id: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = pattern.search(text)
    actual = match.group("value") if match else ""
    return {
        "binding_id": binding_id,
        "path": str(path),
        "expected": _canonical_binding_value(expected),
        "actual": _canonical_binding_value(actual),
    }


def _release_function_binding(path: Path, marker: str, expected: str, binding_id: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    has_import = (
        "from .release_identity import release_product_version" in text
        or "from astrabridge_sidecar.release_identity import release_product_version" in text
    )
    actual = expected if marker in text and has_import else ""
    return {
        "binding_id": binding_id,
        "path": str(path),
        "expected": _canonical_binding_value(expected),
        "actual": _canonical_binding_value(actual),
    }


def _text_marker_binding(path: Path, marker: str, expected: str, binding_id: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    actual = expected if marker in text else ""
    return {
        "binding_id": binding_id,
        "path": str(path),
        "expected": _canonical_binding_value(expected),
        "actual": _canonical_binding_value(actual),
    }


def _forbidden_text_marker_binding(path: Path, marker: str, binding_id: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    actual = marker if marker in text else ""
    return {
        "binding_id": binding_id,
        "path": str(path),
        "expected": "",
        "actual": actual,
    }


def _path_exists_binding(path: Path, expected: bool, binding_id: str) -> dict[str, Any]:
    return {
        "binding_id": binding_id,
        "path": str(path),
        "expected": _canonical_binding_value(expected),
        "actual": _canonical_binding_value(path.exists()),
    }


def _canonical_binding_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _lockfile_digests(root: Path) -> list[dict[str, Any]]:
    lockfiles = [
        root / "apps" / "astrabridge-desktop" / "package-lock.json",
        root / "apps" / "astrabridge-desktop" / "pnpm-lock.yaml",
        root / "apps" / "astrabridge-desktop" / "src-tauri" / "Cargo.lock",
        root / "apps" / "astrabridge-sidecar" / "uv.lock",
    ]
    return [
        {
            "path": str(path),
            "exists": path.exists(),
            "sha256": _hash_file(path) if path.exists() else None,
        }
        for path in lockfiles
    ]


def _git_output(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return str(completed.stdout or "").strip()


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_pyvenv_cfg(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def _copy_tree_filtered(
    source_root: Path,
    destination_root: Path,
    *,
    excluded_parts: set[str],
    excluded_suffixes: set[str],
) -> None:
    if not source_root.exists():
        return
    for path in sorted(source_root.rglob("*")):
        relative = path.relative_to(source_root)
        if any(part in excluded_parts for part in relative.parts):
            continue
        if path.is_dir():
            continue
        if path.suffix.lower() in excluded_suffixes:
            continue
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


__all__ = [
    "DESKTOP_UPDATE_STATUS_SCHEMA_VERSION",
    "RELEASE_IDENTITY_PATH",
    "RELEASE_IDENTITY_SCHEMA_VERSION",
    "RELEASE_READINESS_SCHEMA_VERSION",
    "RELEASE_STAGING_SCHEMA_VERSION",
    "RELEASE_UPDATER_MANIFEST_SCHEMA_VERSION",
    "WINDOWS_UPDATE_REHEARSAL_SCHEMA_VERSION",
    "collect_release_bindings",
    "compare_staging_runs",
    "desktop_update_status",
    "expected_formal_sidecar_bundle",
    "expected_tauri_updater_config",
    "evaluate_updater_contract",
    "evaluate_release_bindings",
    "load_release_identity",
    "release_product_version",
    "release_protocol_schema_version",
    "render_release_readiness_report",
    "render_windows_update_rehearsal_report",
    "run_release_readiness_gate",
    "run_windows_update_rehearsal",
    "stage_release_workspace",
]
