from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from typing import Any, Callable, Mapping

from .wsl_dependency_service import ASTRABRIDGE_WSL_BIN, ASTRABRIDGE_WSL_CODEX_HOME


VersionRunner = Callable[[list[str]], dict[str, Any]]
WhichResolver = Callable[[str], str | None]
_SEMVER_RE = re.compile(r"(?P<version>\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?)")


def resolve_codex_binary_metadata(
    *,
    execution_host: str,
    wsl_distro: str | None = None,
    environ: Mapping[str, str] | None = None,
    which_resolver: WhichResolver = shutil.which,
) -> dict[str, Any]:
    env = environ or os.environ
    host = "wsl" if str(execution_host or "").strip().lower() == "wsl" else "windows"
    if host == "wsl":
        override = str(env.get("ASTRABRIDGE_WSL_CODEX_BIN") or "").strip()
        binary_path = override or ASTRABRIDGE_WSL_BIN
        return {
            "execution_host": "wsl",
            "wsl_distro": str(wsl_distro or "").strip() or None,
            "path": binary_path,
            "path_source": "env_override" if override else "wsl_default",
            "launch_descriptor": f"wsl::{str(wsl_distro or '').strip() or 'default'}::{binary_path}",
        }
    override = str(env.get("ASTRABRIDGE_CODEX_BIN") or "").strip()
    if override:
        path = override
        source = "env_override"
    else:
        path = which_resolver("codex")
        source = "which" if path else "unknown"
    return {
        "execution_host": "windows",
        "wsl_distro": None,
        "path": path,
        "path_source": source,
        "launch_descriptor": path,
    }


def discover_codex_binary_and_version(
    *,
    execution_host: str,
    wsl_distro: str | None = None,
    environ: Mapping[str, str] | None = None,
    which_resolver: WhichResolver = shutil.which,
    run_version: VersionRunner | None = None,
) -> dict[str, Any]:
    metadata = resolve_codex_binary_metadata(
        execution_host=execution_host,
        wsl_distro=wsl_distro,
        environ=environ,
        which_resolver=which_resolver,
    )
    payload = {
        **metadata,
        "version_text": None,
        "version_semver": None,
        "version_parse_status": "not_checked",
        "version_error": None,
    }
    path = str(metadata.get("path") or "").strip()
    if not path:
        payload["version_parse_status"] = "missing"
        return payload
    runner = run_version or _default_run_version
    command = _version_command(metadata=metadata, environ=environ or os.environ, which_resolver=which_resolver)
    if not command:
        payload["version_parse_status"] = "error"
        payload["version_error"] = "version_command_unavailable"
        return payload
    result = runner(command)
    stdout = str(result.get("stdout") or "").strip()
    stderr = str(result.get("stderr") or "").strip()
    returncode = int(result.get("returncode") or 0)
    version_text = stdout or stderr or None
    payload["version_text"] = version_text
    if returncode != 0:
        payload["version_parse_status"] = "error"
        payload["version_error"] = version_text or f"codex --version failed with exit code {returncode}"
        return payload
    parsed = parse_codex_version_text(version_text)
    if parsed is None:
        payload["version_parse_status"] = "unparseable"
        return payload
    payload["version_semver"] = parsed
    payload["version_parse_status"] = "ok"
    return payload


def parse_codex_version_text(version_text: str | None) -> str | None:
    text = str(version_text or "").strip()
    if not text:
        return None
    match = _SEMVER_RE.search(text)
    if not match:
        return None
    return match.group("version")


def _version_command(
    *,
    metadata: Mapping[str, Any],
    environ: Mapping[str, str],
    which_resolver: WhichResolver,
) -> list[str] | None:
    path = str(metadata.get("path") or "").strip()
    if not path:
        return None
    if metadata.get("execution_host") != "wsl":
        return [path, "--version"]
    wsl_executable = which_resolver("wsl.exe") or which_resolver("wsl")
    if not wsl_executable:
        return None
    distro = str(metadata.get("wsl_distro") or "").strip()
    distro_args = ["-d", distro] if distro else []
    codex_home = str(environ.get("ASTRABRIDGE_WSL_CODEX_HOME") or ASTRABRIDGE_WSL_CODEX_HOME).strip() or ASTRABRIDGE_WSL_CODEX_HOME
    command = _wsl_version_command(path, codex_home)
    return [wsl_executable, *distro_args, "bash", "-lc", command]


def _wsl_version_command(binary_path: str, codex_home: str) -> str:
    return (
        f"export CODEX_HOME={_wsl_shell_value(codex_home)}; "
        'export PATH="$HOME/.local/share/astrabridge/bin:$PATH"; '
        f"{_wsl_shell_value(binary_path)} --version"
    )


def _wsl_shell_value(value: str) -> str:
    if value.startswith("$HOME/"):
        return f'"{value}"'
    return shlex.quote(value)


def _default_run_version(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", check=False)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
