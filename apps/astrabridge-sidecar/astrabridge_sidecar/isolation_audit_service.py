from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from .common import PROJECT_FILE_SUFFIX, WORKSPACE_STATE_DIRNAME
from .security import SECRET_RE


SAFE_CONFIG_SECRET_FALSE_POSITIVES = {
    "env_key",
    "router_env_key",
    "model_auto_compact_token_limit",
    "tool_output_token_limit",
}


class IsolationAuditService:
    def snapshot(
        self,
        *,
        current_project: dict[str, Any] | None,
        runtime_environment: dict[str, Any],
        router_status: dict[str, Any],
        official_codex_status: dict[str, Any],
        sidecar_port: int | None = None,
    ) -> dict[str, Any]:
        project = current_project or {}
        workspace = _optional_path(project.get("workspace_root"))
        project_file = _optional_path(project.get("project_file"))
        runtime_config = dict(runtime_environment.get("runtime_config") or {})
        codex_home = _optional_path(runtime_config.get("codex_home"))
        official_config = _optional_path(official_codex_status.get("config_path"))
        expected_appdata = _optional_path(os.environ.get("ASTRABRIDGE_APPDATA"))
        expected_codex_home = _optional_path(os.environ.get("ASTRABRIDGE_CODEX_HOME"))
        checks = []
        checks.append(_check("project_file_suffix", project_file is None or project_file.suffix == PROJECT_FILE_SUFFIX, str(project_file) if project_file else None))
        if workspace:
            checks.append(_check("workspace_astrabridge_state_exists", (workspace / WORKSPACE_STATE_DIRNAME).exists(), str(workspace / WORKSPACE_STATE_DIRNAME)))
            checks.append(_check("workspace_no_owned_codex_state", not (workspace / ".codex").exists(), str(workspace / ".codex")))
            checks.append(_check("workspace_no_old_lcr_state", not (workspace / ".lcr").exists(), str(workspace / ".lcr")))
            checks.append(_check("workspace_no_old_codex_shell_state", not (workspace / ".codex-shell").exists(), str(workspace / ".codex-shell")))
        checks.append(_check("isolated_codex_home_present", codex_home is not None and codex_home.exists(), str(codex_home) if codex_home else None))
        checks.append(
            _check(
                "isolated_codex_home_not_official_home",
                codex_home is None or codex_home.resolve() != (Path.home() / ".codex").resolve(),
                str(codex_home) if codex_home else None,
            )
        )
        if expected_codex_home is not None:
            checks.append(
                _check(
                    "isolated_codex_home_matches_expected_override",
                    codex_home is not None and codex_home.resolve() == expected_codex_home.resolve(),
                    {
                        "expected": str(expected_codex_home),
                        "actual": str(codex_home) if codex_home else None,
                    },
                )
            )
        checks.append(
            _check(
                "isolated_codex_config_has_no_secret",
                codex_home is None or not _path_contains_secret(codex_home / "config.toml"),
                str(codex_home / "config.toml") if codex_home else None,
            )
        )
        secret_scan = _scan_astrabridge_state(project_file, workspace)
        checks.append(_check("project_and_astrabridge_state_have_no_secret_like_content", not secret_scan, secret_scan[:10]))
        return {
            "ok": all(item["ok"] for item in checks),
            "checks": checks,
            "paths": {
                "project_file": str(project_file) if project_file else None,
                "workspace_root": str(workspace) if workspace else None,
                "astrabridge_state": str(workspace / WORKSPACE_STATE_DIRNAME) if workspace else None,
                "isolated_codex_home": str(codex_home) if codex_home else None,
                "official_codex_config": str(official_config) if official_config else None,
                "expected_appdata": str(expected_appdata) if expected_appdata else None,
                "expected_codex_home": str(expected_codex_home) if expected_codex_home else None,
            },
            "official_codex": {
                "exists": bool(official_codex_status.get("exists")),
                "managed_by_app": bool(official_codex_status.get("managed_by_app")),
                "router_configured": bool(official_codex_status.get("router_configured")),
                "config_sha256": _sha256(official_config) if official_config and official_config.exists() else None,
            },
            "ports": {
                "sidecar": sidecar_port,
                "router": router_status.get("listen_port"),
                "router_base_url": router_status.get("base_url"),
            },
            "process_boundary": {
                "app_server_running": bool(runtime_environment.get("running")),
                "codex_cli": runtime_environment.get("codex_cli"),
                "execution_host": runtime_environment.get("execution_host"),
            },
        }


def _optional_path(value: Any) -> Path | None:
    if value in {None, ""}:
        return None
    try:
        return Path(str(value)).expanduser().resolve()
    except OSError:
        return None


def _check(name: str, ok: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _path_contains_secret(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip().strip("\"'").lower()
            if key in SAFE_CONFIG_SECRET_FALSE_POSITIVES:
                continue
        if SECRET_RE.search(stripped):
            return True
    return False


def _scan_astrabridge_state(project_file: Path | None, workspace: Path | None) -> list[str]:
    candidates: list[Path] = []
    if project_file and project_file.exists():
        candidates.append(project_file)
    if workspace:
        state_root = workspace / WORKSPACE_STATE_DIRNAME
        if state_root.exists():
            candidates.extend(path for path in state_root.rglob("*") if path.is_file() and path.stat().st_size <= 1_000_000)
    return [str(path) for path in candidates if _path_contains_secret(path)]


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

