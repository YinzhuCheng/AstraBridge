from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any


APP_NAME = "AstraBridge"
PROJECT_SCHEMA_VERSION = "astrabridge-project-v1"
DEFAULT_PORT = 8790
DEFAULT_CODEX_HOME_NAME = "embedded_codex_home"
SHORT_CODEX_HOME_DIR = ("AstraBridge", "cx")
PROJECT_FILE_SUFFIX = ".abproj"
WORKSPACE_STATE_DIRNAME = ".astrabridge"
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
    root = os.environ.get("ASTRABRIDGE_APPDATA")
    if root:
        return Path(root).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return (Path(base) / APP_NAME).resolve()
    return Path.home() / ".astrabridge"


def default_codex_home() -> Path:
    override = os.environ.get("ASTRABRIDGE_CODEX_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base).joinpath(*SHORT_CODEX_HOME_DIR)
    return app_data_dir() / DEFAULT_CODEX_HOME_NAME


def app_runtime_dir(*parts: str) -> Path:
    root = app_data_dir() / "runtime"
    path = root.joinpath(*parts) if parts else root
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


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
        temp_path = path.with_name(f".tmp-{uuid.uuid4().hex[:8]}")
        try:
            temp_path.write_text(text, encoding="utf-8")
            os.replace(temp_path, path)
            return
        except OSError as exc:
            # Windows file watchers and concurrent readers can briefly hold the
            # destination or remove a just-created temp file. Use a fresh temp
            # file on each retry so failed replacements never leak into later
            # attempts.
            last_error = exc
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            path.parent.mkdir(parents=True, exist_ok=True)
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


