from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any


APP_NAME = "AstraBridge"
LEGACY_APPDATA_DIRNAME = "LocalCodexRouter"
PROJECT_SCHEMA_VERSION = "astrabridge-project-v1"
LEGACY_PROJECT_SCHEMA_VERSION = "local-codex-router-project-v1"
DEFAULT_PORT = 8790
DEFAULT_CODEX_HOME_NAME = "embedded_codex_home"
SHORT_CODEX_HOME_DIR = ("AstraBridge", "cx")
PROJECT_FILE_SUFFIX = ".abproj"
LEGACY_PROJECT_FILE_SUFFIX = ".lcrproj"
WORKSPACE_STATE_DIRNAME = ".astrabridge"
LEGACY_WORKSPACE_STATE_DIRNAME = ".lcr"
_WINDOWS_DRIVE_PATH_RE = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")
_WSL_MOUNT_PATH_RE = re.compile(r"^/mnt/(?P<drive>[A-Za-z])/(?P<rest>.*)$")
_WINDOWS_DRIVE_PATH_ANYWHERE_RE = re.compile(r"(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")
_WSL_MOUNT_PATH_ANYWHERE_RE = re.compile(r"(?P<full>/mnt/(?P<drive>[A-Za-z])/(?P<rest>.*))$")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat()


def new_id(prefix: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y%m%dT%H%M%S%f")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:6]}"


def app_data_dir() -> Path:
    root = os.environ.get("ASTRABRIDGE_APPDATA") or os.environ.get("ASTRABRIDGE_APPDATA")
    if root:
        return Path(root).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        target = (Path(base) / APP_NAME).resolve()
        _migrate_legacy_app_data(target)
        return target
    return Path.home() / ".astrabridge"


def legacy_app_data_dir() -> Path | None:
    if os.name != "nt":
        return None
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return (Path(base) / LEGACY_APPDATA_DIRNAME).resolve()


def _migrate_legacy_app_data(target: Path) -> None:
    legacy = legacy_app_data_dir()
    if legacy is None or not legacy.exists():
        return
    try:
        if legacy.samefile(target):
            return
    except OSError:
        pass
    copy_names = (
        "projects.json",
        "current_project.json",
        "recent_projects.json",
        "profiles.json",
        "router_config.json",
        "mcp_servers.json",
        "metadata_sources.json",
        "bootstrap",
        "official-codex-backups",
        "llm_api_manager",
    )
    for name in copy_names:
        source = legacy / name
        destination = target / name
        if not source.exists() or destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


def default_codex_home() -> Path:
    override = os.environ.get("ASTRABRIDGE_CODEX_HOME") or os.environ.get("ASTRABRIDGE_CODEX_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base).joinpath(*SHORT_CODEX_HOME_DIR)
    return app_data_dir() / DEFAULT_CODEX_HOME_NAME


def slugify(value: str, default: str = "astrabridge-project") -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", value.strip()).strip("-._")
    return cleaned[:80] or default


def ensure_suffix(path: Path, suffix: str) -> Path:
    return path if path.suffix.lower() == suffix.lower() else path.with_suffix(suffix)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    last_error: Exception | None = None
    for attempt in range(10):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except PermissionError as exc:
            # On Windows, a concurrent atomic replace or scanner can briefly
            # deny access to a JSON state file. Retry before surfacing failure.
            last_error = exc
            time.sleep(min(0.03 * (attempt + 1), 0.3))
    if last_error is not None:
        raise last_error
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        if path.exists() and path.read_text(encoding="utf-8-sig") == text:
            return
    except OSError:
        # Fall through to the normal atomic write path. A transient read error
        # should not prevent a later successful write.
        pass
    last_error: Exception | None = None
    for attempt in range(10):
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(text, encoding="utf-8")
            os.replace(temp_path, path)
            return
        except PermissionError as exc:
            # Windows file watchers and concurrent readers can briefly hold the
            # destination after another atomic write. Use a fresh temp file on
            # each retry so failed replacements never leak into later attempts.
            last_error = exc
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(min(0.05 * (attempt + 1), 0.5))
    if last_error is not None:
        raise last_error


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def normalize_path_for_host(path: str | Path, host_os_name: str | None = None) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    host = host_os_name or os.name
    text = _repair_embedded_cross_host_path(text, host)
    if host == "nt":
        normalized = text.replace("\\", "/")
        match = _WSL_MOUNT_PATH_RE.match(normalized)
        if match:
            drive = match.group("drive").upper()
            rest = match.group("rest").replace("/", "\\")
            return f"{drive}:\\{rest}"
        return text
    match = _WINDOWS_DRIVE_PATH_RE.match(text)
    if match:
        drive = match.group("drive").lower()
        rest = match.group("rest").replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return text


def _repair_embedded_cross_host_path(text: str, host: str) -> str:
    """Recover the real host path when a bad caller prefixed cwd to it.

    Historical broken values looked like:
    /mnt/d/repo/apps/astrabridge-sidecar/D:\workflow\project
    If we see an embedded cross-host absolute path, prefer that suffix.
    """
    if host == "nt":
        normalized = text.replace("\\", "/")
        marker = normalized.find("/mnt/")
        if marker > 0:
            candidate = normalized[marker:]
            if _WSL_MOUNT_PATH_RE.match(candidate):
                return candidate
        return text
    match = _WINDOWS_DRIVE_PATH_ANYWHERE_RE.search(text)
    if match and match.start() > 0:
        return text[match.start() :]
    normalized = text.replace("\\", "/")
    match = _WSL_MOUNT_PATH_ANYWHERE_RE.search(normalized)
    if match and match.start("full") > 0:
        return match.group("full")
    return text


def path_for_host(path: str | Path, host_os_name: str | None = None) -> Path:
    return Path(normalize_path_for_host(path, host_os_name=host_os_name)).expanduser()


def public_error(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": str(exc), "error_type": exc.__class__.__name__}


