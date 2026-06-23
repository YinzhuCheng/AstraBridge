from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .common import PROJECT_FILE_SUFFIX, WORKSPACE_STATE_DIRNAME
from .project_service import MANAGED_STATE_DIRS, STORAGE_POLICY_SCHEMA_VERSION
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
            storage_policy = workspace / WORKSPACE_STATE_DIRNAME / "storage_policy.json"
            storage_policy_payload = _read_storage_policy(storage_policy)
            checks.append(_check("workspace_astrabridge_state_exists", (workspace / WORKSPACE_STATE_DIRNAME).exists(), str(workspace / WORKSPACE_STATE_DIRNAME)))
            checks.append(_check("workspace_storage_policy_exists", storage_policy.exists(), str(storage_policy)))
            checks.append(
                _check(
                    "workspace_storage_policy_schema",
                    _storage_policy_schema_ok(storage_policy),
                    str(storage_policy),
                )
            )
            checks.append(_check("workspace_no_owned_codex_state", not (workspace / ".codex").exists(), str(workspace / ".codex")))
            checks.append(_check("workspace_no_old_lcr_state", not (workspace / ".lcr").exists(), str(workspace / ".lcr")))
            checks.append(_check("workspace_no_old_codex_shell_state", not (workspace / ".codex-shell").exists(), str(workspace / ".codex-shell")))
            for dirname in MANAGED_STATE_DIRS:
                checks.append(
                    _check(
                        f"managed_state_dir_{dirname}_exists",
                        (workspace / WORKSPACE_STATE_DIRNAME / dirname).is_dir(),
                        str(workspace / WORKSPACE_STATE_DIRNAME / dirname),
                    )
                )
            checks.append(
                _check(
                    "workspace_storage_policy_managed_dirs_match",
                    _storage_policy_managed_dirs_match(storage_policy, workspace),
                    str(storage_policy),
                )
            )
            checks.append(
                _check(
                    "workspace_storage_policy_runtime_codex_home_matches",
                    _expected_runtime_codex_home_matches(
                        storage_policy_payload,
                        actual_path=codex_home,
                        expected_override=expected_codex_home,
                    ),
                    str(storage_policy),
                )
            )
            checks.append(
                _check(
                    "workspace_storage_policy_runtime_root_outside_workspace",
                    _storage_policy_runtime_root_outside_workspace(storage_policy_payload, workspace),
                    str(storage_policy),
                )
            )
            checks.extend(
                _storage_policy_runtime_roots_outside_workspace_checks(
                    storage_policy_payload,
                    workspace,
                )
            )
            checks.append(
                _check(
                    "workspace_git_repo_excludes_astrabridge_state",
                    _workspace_git_repo_excludes_astrabridge_state(workspace),
                    _workspace_git_exclude_detail(workspace),
                )
            )
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
                "managed_state_roots": {
                    dirname: str(workspace / WORKSPACE_STATE_DIRNAME / dirname)
                    for dirname in MANAGED_STATE_DIRS
                } if workspace else {},
                "isolated_codex_home": str(codex_home) if codex_home else None,
                "project_runtime_root": _storage_policy_runtime_path(_read_storage_policy(workspace / WORKSPACE_STATE_DIRNAME / "storage_policy.json"), "project_runtime_root") if workspace else None,
                "downloads_root": _storage_policy_runtime_path(_read_storage_policy(workspace / WORKSPACE_STATE_DIRNAME / "storage_policy.json"), "downloads_root") if workspace else None,
                "caches_root": _storage_policy_runtime_path(_read_storage_policy(workspace / WORKSPACE_STATE_DIRNAME / "storage_policy.json"), "caches_root") if workspace else None,
                "tmp_root": _storage_policy_runtime_path(_read_storage_policy(workspace / WORKSPACE_STATE_DIRNAME / "storage_policy.json"), "tmp_root") if workspace else None,
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


def _storage_policy_schema_ok(path: Path) -> bool:
    payload = _read_storage_policy(path)
    return bool(payload) and str(payload.get("schema_version") or "") == STORAGE_POLICY_SCHEMA_VERSION


def _storage_policy_managed_dirs_match(path: Path, workspace: Path) -> bool:
    payload = _read_storage_policy(path)
    if not payload:
        return False
    managed = dict(payload.get("managed_dirs") or {})
    expected_root = (workspace / WORKSPACE_STATE_DIRNAME).resolve()
    for dirname in MANAGED_STATE_DIRS:
        actual = managed.get(dirname)
        if not actual:
            return False
        try:
            actual_path = Path(str(actual)).expanduser().resolve()
        except OSError:
            return False
        if actual_path != (expected_root / dirname):
            return False
    return True


def _read_storage_policy(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = path.read_text(encoding="utf-8")
        data = json.loads(payload)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _storage_policy_runtime_path(payload: dict[str, Any] | None, key: str) -> str | None:
    if not payload:
        return None
    runtime = dict(payload.get("runtime") or {})
    value = runtime.get(key)
    return str(value) if value else None


def _storage_policy_runtime_path_matches(payload: dict[str, Any] | None, key: str, actual_path: Path | None) -> bool:
    expected = _storage_policy_runtime_path(payload, key)
    if not expected:
        return False
    if actual_path is None:
        return False
    try:
        return Path(expected).expanduser().resolve() == actual_path.expanduser().resolve()
    except OSError:
        return False


def _storage_policy_runtime_roots_outside_workspace_checks(
    payload: dict[str, Any] | None,
    workspace: Path,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for key in ("project_runtime_root", "downloads_root", "caches_root", "tmp_root"):
        checks.append(
            _check(
                f"workspace_storage_policy_{key}_outside_workspace",
                _storage_policy_runtime_root_outside_workspace(payload, workspace, key=key),
                str(payload.get("runtime", {}).get(key, "")) if isinstance(payload, dict) else None,
            )
        )
    return checks


def _storage_policy_runtime_root_outside_workspace(payload: dict[str, Any] | None, workspace: Path, *, key: str = "project_runtime_root") -> bool:
    expected = _storage_policy_runtime_path(payload, key)
    if not expected:
        return False
    try:
        runtime_root = Path(expected).expanduser().resolve()
        workspace_root = workspace.expanduser().resolve()
    except OSError:
        return False
    return runtime_root != workspace_root and workspace_root not in runtime_root.parents


def _expected_runtime_codex_home_matches(
    payload: dict[str, Any] | None,
    *,
    actual_path: Path | None,
    expected_override: Path | None,
) -> bool:
    if actual_path is None:
        return False
    if expected_override is not None:
        try:
            return actual_path.expanduser().resolve() == expected_override.expanduser().resolve()
        except OSError:
            return False
    return _storage_policy_runtime_path_matches(payload, "codex_home_root", actual_path)


def _workspace_git_repo_excludes_astrabridge_state(workspace: Path) -> bool:
    repo_root = _git_repo_root_for_workspace(workspace)
    if repo_root is None:
        return True
    exclude_file = repo_root / ".git" / "info" / "exclude"
    if not exclude_file.exists() or not exclude_file.is_file():
        return False
    try:
        content = exclude_file.read_text(encoding="utf-8")
    except OSError:
        return False
    pattern = _workspace_git_exclude_pattern(repo_root, workspace)
    return bool(pattern) and pattern in content


def _workspace_git_exclude_detail(workspace: Path) -> dict[str, str] | None:
    repo_root = _git_repo_root_for_workspace(workspace)
    if repo_root is None:
        return None
    return {
        "repo_root": str(repo_root),
        "expected_pattern": _workspace_git_exclude_pattern(repo_root, workspace),
        "exclude_file": str(repo_root / ".git" / "info" / "exclude"),
    }


def _git_repo_root_for_workspace(workspace: Path) -> Path | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=5,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    candidate = str(completed.stdout or "").strip()
    if not candidate:
        return None
    try:
        return Path(candidate).expanduser().resolve()
    except OSError:
        return None


def _workspace_git_exclude_pattern(repo_root: Path, workspace: Path) -> str:
    try:
        relative_workspace = workspace.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return f"{WORKSPACE_STATE_DIRNAME}/"
    if not relative_workspace or relative_workspace == ".":
        return f"{WORKSPACE_STATE_DIRNAME}/"
    return f"{relative_workspace}/{WORKSPACE_STATE_DIRNAME}/"

