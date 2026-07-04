from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .security import SECRET_QUERY_RE


SIDECAR_PROVENANCE_SCHEMA_VERSION = "astrabridge-sidecar-provenance-v1"
_PORT_OWNER_CACHE_SECONDS = 3.0
_PORT_OWNER_CACHE: dict[tuple[str, int], tuple[float, dict[str, Any]]] = {}
_SENSITIVE_ARG_MARKERS = (
    "api-key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "secret",
    "token",
)


def build_sidecar_provenance(
    *,
    listen_host: str = "127.0.0.1",
    listen_port: int | None = None,
    seed_root: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    argv: Sequence[str] | None = None,
    pid: int | None = None,
    cwd: str | Path | None = None,
    executable: str | None = None,
    source_root: str | Path | None = None,
    port_owner: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = environ or os.environ
    process_pid = int(pid if pid is not None else os.getpid())
    resolved_source_root = _resolve_path(source_root) or _default_source_root()
    repo_root = _detect_repo_root(resolved_source_root)
    current_source_match = _matches_current_source(resolved_source_root, repo_root)
    safe_argv = redact_command_argv(list(argv if argv is not None else sys.argv))
    resolved_executable = str(executable if executable is not None else sys.executable)
    origin = _sidecar_origin(env, current_source_match=current_source_match, executable=resolved_executable)
    launcher_mode = _launcher_mode(env, origin=origin, current_source_match=current_source_match)
    owner = port_owner or detect_port_owner(
        listen_host=listen_host,
        listen_port=listen_port,
        fallback_pid=process_pid,
    )
    return {
        "schema_version": SIDECAR_PROVENANCE_SCHEMA_VERSION,
        "origin": origin,
        "launcher_mode": launcher_mode,
        "pid": process_pid,
        "command_line": command_line_from_argv(safe_argv),
        "command_argv": safe_argv,
        "command_line_redaction": "secret_args_masked",
        "executable": _redact_text(resolved_executable),
        "cwd": str(_resolve_path(cwd) or Path.cwd().resolve()),
        "seed_root": str(_resolve_path(seed_root)) if seed_root is not None else None,
        "source_root": str(resolved_source_root),
        "repo_root": str(repo_root) if repo_root else None,
        "current_source_match": current_source_match,
        "listen_host": listen_host,
        "listen_port": listen_port,
        "port_owner": owner,
    }


def detect_port_owner(
    *,
    listen_host: str,
    listen_port: int | None,
    fallback_pid: int | None = None,
) -> dict[str, Any]:
    if not listen_port:
        return {
            "status": "unknown",
            "method": "missing_listen_port",
            "pid": fallback_pid,
            "listen_host": listen_host,
            "listen_port": listen_port,
        }
    key = (listen_host, int(listen_port))
    cached = _PORT_OWNER_CACHE.get(key)
    now = time.monotonic()
    if cached and now - cached[0] <= _PORT_OWNER_CACHE_SECONDS:
        return dict(cached[1])

    owner = _detect_port_owner_uncached(listen_host=listen_host, listen_port=int(listen_port), fallback_pid=fallback_pid)
    _PORT_OWNER_CACHE[key] = (now, dict(owner))
    return owner


def _detect_port_owner_uncached(*, listen_host: str, listen_port: int, fallback_pid: int | None) -> dict[str, Any]:
    detected_pid: int | None = None
    method = "self_reported"
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True,
                text=True,
                timeout=0.75,
                check=False,
            )
            if result.stdout:
                detected_pid = parse_windows_netstat_port_owner(result.stdout, listen_port=listen_port)
                method = "netstat"
        except Exception:
            detected_pid = None
            method = "self_reported"
    if detected_pid is None:
        detected_pid = fallback_pid
        status = "self_reported" if fallback_pid else "unknown"
    else:
        status = "self" if fallback_pid and int(detected_pid) == int(fallback_pid) else "different_process"
    return {
        "status": status,
        "method": method,
        "pid": detected_pid,
        "expected_pid": fallback_pid,
        "listen_host": listen_host,
        "listen_port": listen_port,
    }


def parse_windows_netstat_port_owner(output: str, *, listen_port: int) -> int | None:
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        state = parts[3].upper()
        pid_text = parts[4]
        if state != "LISTENING":
            continue
        if _address_port(local_address) != int(listen_port):
            continue
        try:
            return int(pid_text)
        except ValueError:
            return None
    return None


def redact_command_argv(argv: Sequence[str]) -> list[str]:
    safe: list[str] = []
    redact_next = False
    for raw in argv:
        token = _redact_text(str(raw))
        lowered = token.lower()
        if redact_next:
            safe.append("[REDACTED]")
            redact_next = False
            continue
        if _looks_sensitive_arg(lowered):
            if "=" in token:
                key, _separator, _value = token.partition("=")
                safe.append(f"{key}=[REDACTED]")
            elif token.startswith("-"):
                safe.append(token)
                redact_next = True
            else:
                safe.append("[REDACTED]")
            continue
        safe.append(token)
    return safe


def command_line_from_argv(argv: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(argv))
    return shlex.join(list(argv))


def _looks_sensitive_arg(lowered: str) -> bool:
    return any(marker in lowered for marker in _SENSITIVE_ARG_MARKERS)


def _redact_text(value: str) -> str:
    if SECRET_QUERY_RE.search(value):
        return SECRET_QUERY_RE.sub(r"\1[REDACTED]", value)
    if "authorization:" in value.lower() or "bearer " in value.lower():
        return "[REDACTED]"
    return value


def _address_port(address: str) -> int | None:
    text = address.strip()
    if not text:
        return None
    try:
        return int(text.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return None


def _resolve_path(value: str | Path | None) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Path(str(value)).expanduser().resolve()
    except OSError:
        return None


def _default_source_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _detect_repo_root(source_root: Path) -> Path | None:
    for candidate in [source_root, *source_root.parents]:
        if (candidate / ".git").exists() and (candidate / "apps" / "astrabridge-sidecar").exists():
            return candidate
    return None


def _matches_current_source(source_root: Path, repo_root: Path | None) -> bool:
    if repo_root is None:
        return False
    expected = (repo_root / "apps" / "astrabridge-sidecar").resolve()
    try:
        resolved = source_root.resolve()
    except OSError:
        return False
    return resolved == expected or expected in resolved.parents


def _sidecar_origin(env: Mapping[str, str], *, current_source_match: bool, executable: str) -> str:
    override = str(env.get("ASTRABRIDGE_SIDECAR_ORIGIN") or "").strip().lower().replace("-", "_")
    if override in {"current_source", "app_managed", "unknown"}:
        return override
    if current_source_match:
        return "current_source"
    lowered_executable = executable.lower().replace("\\", "/")
    if "astrabridge" in lowered_executable and not lowered_executable.endswith("/python.exe"):
        return "app_managed"
    return "unknown"


def _launcher_mode(env: Mapping[str, str], *, origin: str, current_source_match: bool) -> str:
    explicit = str(
        env.get("ASTRABRIDGE_LAUNCHER_MODE")
        or env.get("ASTRABRIDGE_LAUNCH_MODE")
        or ""
    ).strip()
    if explicit:
        return explicit
    if current_source_match:
        return "current_source"
    if origin == "app_managed":
        return "app_managed"
    return "unknown"
