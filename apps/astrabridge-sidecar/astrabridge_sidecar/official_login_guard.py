from __future__ import annotations

from pathlib import Path
from typing import Any


OFFICIAL_CODEX_DISABLED_ERROR = "official_codex_disabled"


def disabled_status() -> dict[str, Any]:
    return {
        "config_path": str((Path.home() / ".codex" / "config.toml").resolve()),
        "exists": (Path.home() / ".codex" / "config.toml").exists(),
        "router_configured": False,
        "managed_by_app": False,
        "backup_count": 0,
        "latest_backup": None,
        "router_env_key": "CODEX_ROUTER_API_KEY",
        "disabled": True,
        "error": OFFICIAL_CODEX_DISABLED_ERROR,
        "message": "AstraBridge only supports OpenAI API-key providers and does not patch official Codex account config.",
    }


def raise_if_official_codex_requested() -> None:
    raise PermissionError(disabled_status()["message"])
