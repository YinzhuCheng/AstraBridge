from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .common import app_data_dir, now_iso
from .security import redact_sensitive


DEFAULT_WSL_DISTRO = "Ubuntu-24.04"
ASTRABRIDGE_WSL_ROOT = "$HOME/.local/share/astrabridge"
ASTRABRIDGE_WSL_BIN = f"{ASTRABRIDGE_WSL_ROOT}/bin/codex"
ASTRABRIDGE_WSL_CODEX_HOME = f"{ASTRABRIDGE_WSL_ROOT}/codex-home"


class WslDependencyService:
    """Detect and bootstrap the optional WSL runtime used by AstraBridge."""

    def __init__(self, script_root: Path | None = None) -> None:
        self.script_root = (script_root or app_data_dir() / "bootstrap" / "wsl").resolve()

    def status(self, distro: str | None = None) -> dict[str, Any]:
        distro_name = (distro or DEFAULT_WSL_DISTRO).strip() or DEFAULT_WSL_DISTRO
        wsl_exe = shutil.which("wsl.exe") or shutil.which("wsl")
        checks: list[dict[str, Any]] = []
        distros: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        if not wsl_exe:
            checks.append(self._check("wsl", "WSL executable", "missing", "wsl.exe was not found on PATH.", required=True, remediation="Run the generated Windows bootstrap script as administrator."))
            return self._snapshot(distro_name, wsl_exe, distros, checks)

        checks.append(self._check("wsl", "WSL executable", "ok", wsl_exe, required=True))
        distros = self._list_distros(wsl_exe)
        selected = next((item for item in distros if item.get("name") == distro_name), None)
        if not selected:
            checks.append(self._check("distro", f"WSL distro {distro_name}", "missing", f"{distro_name} is not installed.", required=True, remediation="Run the generated Windows bootstrap script to install the distro."))
            return self._snapshot(distro_name, wsl_exe, distros, checks)

        checks.append(self._check("distro", f"WSL distro {distro_name}", "ok", f"{selected.get('name')} / WSL {selected.get('version') or 'unknown'} / {selected.get('state') or 'unknown'}", required=True))
        os_release = self._wsl(wsl_exe, distro_name, "cat /etc/os-release 2>/dev/null | grep '^PRETTY_NAME=' || true")
        checks.append(self._check("ubuntu", "Linux distribution", "ok" if "Ubuntu" in os_release["stdout"] else "warning", self._clean_os_release(os_release["stdout"]) or "Could not read /etc/os-release.", required=False))

        for command, label, required in [
            ("python3 --version", "Python 3", False),
            ("git --version", "Git", False),
            ("node --version", "Node.js", True),
            ("npm --version", "npm", True),
            ("npx --version", "npx", True),
            ("bwrap --version", "bubblewrap", True),
        ]:
            result = self._wsl(wsl_exe, distro_name, command)
            checks.append(
                self._check(
                    command.split()[0],
                    label,
                    "ok" if result["returncode"] == 0 else "missing",
                    (result["stdout"] or result["stderr"] or f"{label} not found.").strip(),
                    required=required,
                    remediation="Run the generated WSL bootstrap script.",
                )
            )

        codex_path = self._wsl(wsl_exe, distro_name, self._with_astrabridge_path("command -v codex || true"))
        codex_detail = (codex_path["stdout"] or codex_path["stderr"]).strip()
        if self._looks_like_windows_codex(codex_detail):
            checks.append(
                self._check(
                    "codex_path",
                    "Codex path",
                    "misconfigured",
                    f"codex resolves to a Windows path inside WSL: {codex_detail}",
                    required=True,
                    remediation="Install the AstraBridge-managed Linux Codex CLI in WSL.",
                )
            )
        else:
            checks.append(self._check("codex_path", "Codex path", "ok" if codex_detail else "missing", codex_detail or "No codex executable found in WSL.", required=True, remediation="Run the generated WSL bootstrap script."))

        codex_version = self._wsl(wsl_exe, distro_name, self._with_astrabridge_path("codex --version"))
        checks.append(
            self._check(
                "codex_version",
                "Codex CLI",
                "ok" if codex_version["returncode"] == 0 and not self._looks_like_windows_codex(codex_detail) else "missing",
                (codex_version["stdout"] or codex_version["stderr"] or "codex --version failed.").strip(),
                required=True,
                remediation="Run the generated WSL bootstrap script.",
            )
        )

        app_server = self._wsl(wsl_exe, distro_name, self._app_server_smoke_command())
        checks.append(
            self._check(
                "app_server",
                "Codex app-server smoke",
                "ok" if app_server["returncode"] == 0 else "failed",
                (app_server["stdout"] or app_server["stderr"] or "app-server smoke failed.").strip()[:1200],
                required=True,
                remediation="Re-run the WSL bootstrap script, then restart AstraBridge runtime.",
            )
        )
        return self._snapshot(distro_name, wsl_exe, distros, checks)

    def write_scripts(self, distro: str | None = None) -> dict[str, Any]:
        distro_name = (distro or DEFAULT_WSL_DISTRO).strip() or DEFAULT_WSL_DISTRO
        self.script_root.mkdir(parents=True, exist_ok=True)
        windows_path = self.script_root / "install-astrabridge-wsl-runtime.ps1"
        wsl_path = self.script_root / "install-astrabridge-wsl-runtime.sh"
        windows_path.write_text(self._windows_bootstrap_script(distro_name), encoding="utf-8")
        wsl_path.write_text(self._wsl_bootstrap_script(), encoding="utf-8", newline="\n")
        return {
            "ok": True,
            "distro": distro_name,
            "windows_script_path": str(windows_path),
            "wsl_script_path": str(wsl_path),
            "run_command": f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{windows_path}"',
        }

    def launch_installer(self, distro: str | None = None) -> dict[str, Any]:
        scripts = self.write_scripts(distro)
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(scripts["windows_script_path"])],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        return {**scripts, "launched": True}

    def _snapshot(self, distro: str, wsl_exe: str | None, distros: list[dict[str, Any]], checks: list[dict[str, Any]]) -> dict[str, Any]:
        required = [item for item in checks if item.get("required")]
        ok = bool(required) and all(item.get("status") == "ok" for item in required)
        return {
            "ok": ok,
            "generated_at": now_iso(),
            "default_distro": DEFAULT_WSL_DISTRO,
            "selected_distro": distro,
            "wsl_executable": wsl_exe,
            "distros": distros,
            "checks": [redact_sensitive(item) for item in checks],
            "paths": {
                "astrabridge_wsl_codex_bin": ASTRABRIDGE_WSL_BIN,
                "astrabridge_wsl_codex_home": ASTRABRIDGE_WSL_CODEX_HOME,
                "script_root": str(self.script_root),
            },
        }

    def _list_distros(self, wsl_exe: str) -> list[dict[str, Any]]:
        result = self._run([wsl_exe, "-l", "-v"])
        lines = [line.strip() for line in str(result["stdout"] or "").splitlines() if line.strip()]
        distros: list[dict[str, Any]] = []
        for line in lines:
            cleaned = line.replace("\x00", "").replace("*", "").strip()
            if not cleaned or cleaned.upper().startswith("NAME"):
                continue
            parts = re.split(r"\s{2,}", cleaned)
            if len(parts) >= 3:
                distros.append({"name": parts[0], "state": parts[1], "version": parts[2]})
            else:
                distros.append({"name": cleaned.split()[0], "state": "", "version": ""})
        if distros:
            return distros
        quiet = self._run([wsl_exe, "-l", "-q"])
        return [{"name": line.strip().replace("\x00", ""), "state": "", "version": ""} for line in str(quiet["stdout"] or "").splitlines() if line.strip()]

    def _wsl(self, wsl_exe: str, distro: str, command: str) -> dict[str, Any]:
        return self._run([wsl_exe, "-d", distro, "bash", "-lc", command])

    def _run(self, command: list[str]) -> dict[str, Any]:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return {
            "returncode": completed.returncode,
            "stdout": self._decode(completed.stdout),
            "stderr": self._decode(completed.stderr),
        }

    def _decode(self, payload: bytes) -> str:
        if not payload:
            return ""
        for encoding in ("utf-8", "utf-16-le", "gbk", "cp936"):
            try:
                return payload.decode(encoding).replace("\x00", "").strip()
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="replace").replace("\x00", "").strip()

    def _check(self, check_id: str, label: str, status: str, detail: str, *, required: bool, remediation: str | None = None) -> dict[str, Any]:
        return {
            "id": check_id,
            "label": label,
            "status": status,
            "detail": detail,
            "required": required,
            "remediation": remediation,
        }

    def _with_astrabridge_path(self, command: str) -> str:
        return (
            f'export CODEX_HOME="{ASTRABRIDGE_WSL_CODEX_HOME}"; '
            f'export PATH="{ASTRABRIDGE_WSL_ROOT}/bin:$PATH"; '
            f"{command}"
        )

    def _app_server_smoke_command(self) -> str:
        payload = (
            '{"method":"initialize","id":1,"params":{"clientInfo":{"name":"astrabridge-dependency-check","version":"0.1.0"},'
            '"capabilities":{"experimentalApi":true,"requestAttestation":false}}}\\n'
        )
        return self._with_astrabridge_path(
            f"mkdir -p {self._wsl_shell_value(ASTRABRIDGE_WSL_CODEX_HOME)}; "
            f"printf {payload!r} | timeout 8s codex app-server --listen stdio:// --disable plugins --disable plugin_sharing --disable remote_plugin | head -20 | grep -q '\"id\"'"
        )

    def _wsl_shell_value(self, value: str) -> str:
        if value.startswith("$HOME/"):
            return f'"{value}"'
        return repr(value)

    def _looks_like_windows_codex(self, value: str) -> bool:
        normalized = value.replace("\\", "/").lower()
        return normalized.startswith("/mnt/c/") and "windowsapps" in normalized

    def _clean_os_release(self, value: str) -> str:
        return value.replace("PRETTY_NAME=", "").strip().strip('"')

    def _windows_bootstrap_script(self, distro: str) -> str:
        wsl_script_path = self.script_root / "install-astrabridge-wsl-runtime.sh"
        return f"""# AstraBridge WSL bootstrap
$ErrorActionPreference = "Stop"
$Distro = "{distro}"
$ScriptPath = "{str(wsl_script_path)}"
Write-Host "AstraBridge WSL bootstrap for $Distro"
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {{
  Write-Host "WSL is missing. Requesting Windows to install WSL and $Distro. This may require administrator approval and a reboot."
  Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command wsl.exe --install -d $Distro"
  exit 0
}}
$distros = (& wsl.exe -l -q) -join "`n"
if ($distros -notmatch [regex]::Escape($Distro)) {{
  Write-Host "$Distro is not installed. Installing through wsl.exe --install."
  Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command wsl.exe --install -d $Distro"
  exit 0
}}
Write-Host "Running WSL-side bootstrap. You may be prompted for your Linux sudo password."
$WslScriptPath = (& wsl.exe -d $Distro -- wslpath -a "$ScriptPath").Trim()
wsl.exe -d $Distro -- bash -lc "chmod +x '$WslScriptPath' && '$WslScriptPath'"
Write-Host "Bootstrap finished. Return to AstraBridge and click Recheck."
Read-Host "Press Enter to close"
"""

    def _wsl_bootstrap_script(self) -> str:
        return """#!/usr/bin/env bash
set -euo pipefail
echo "[AstraBridge] Installing WSL runtime dependencies"
sudo apt-get update
sudo apt-get install -y curl ca-certificates git bubblewrap apparmor-profiles apparmor-utils nodejs npm
if [ -f /usr/share/apparmor/extra-profiles/bwrap-userns-restrict ]; then
  sudo install -m 0644 /usr/share/apparmor/extra-profiles/bwrap-userns-restrict /etc/apparmor.d/bwrap-userns-restrict || true
  sudo apparmor_parser -r /etc/apparmor.d/bwrap-userns-restrict || true
fi
export LCR_ROOT="$HOME/.local/share/astrabridge"
export CODEX_HOME="$LCR_ROOT/codex-home"
export CODEX_INSTALL_DIR="$LCR_ROOT/bin"
mkdir -p "$CODEX_HOME" "$CODEX_INSTALL_DIR"
echo "[AstraBridge] Installing Codex CLI into $CODEX_INSTALL_DIR"
curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 CODEX_HOME="$CODEX_HOME" CODEX_INSTALL_DIR="$CODEX_INSTALL_DIR" sh
export PATH="$CODEX_INSTALL_DIR:$PATH"
echo "[AstraBridge] Verifying Codex"
codex --version
printf '{"method":"initialize","id":1,"params":{"clientInfo":{"name":"lcr-bootstrap-check","version":"0.1.0"},"capabilities":{"experimentalApi":true,"requestAttestation":false}}}\n' | timeout 10s codex app-server --listen stdio:// --disable plugins --disable plugin_sharing --disable remote_plugin | head -20 | grep -q '"id"'
echo "[AstraBridge] WSL runtime is ready"
"""

