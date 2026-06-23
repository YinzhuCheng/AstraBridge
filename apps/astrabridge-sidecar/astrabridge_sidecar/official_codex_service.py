from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from .common import app_data_dir, now_iso, write_json
from .model_catalog import catalog_entry_from_record, effective_model_records, known_context_window, model_catalog_entry
from .model_catalog import preferred_provider_model_record


MANAGED_BLOCK_START = "# BEGIN LOCAL CODEX ROUTER MANAGED BLOCK"
MANAGED_BLOCK_END = "# END LOCAL CODEX ROUTER MANAGED BLOCK"
ROUTER_SECTION_RE = re.compile(r"^\[model_providers\.router\]\s*$")
TOP_LEVEL_ROUTER_KEYS = ("model_provider", "model", "model_catalog_json")


class OfficialCodexService:
    def __init__(self, profiles_service, router_config_service=None, backups_root: Path | None = None) -> None:
        if backups_root is None and isinstance(router_config_service, Path):
            backups_root = router_config_service
            router_config_service = None
        self._profiles = profiles_service
        self._router_config = router_config_service
        self._backups_root = backups_root or (app_data_dir() / "official-codex-backups")

    def status(self) -> dict[str, Any]:
        config_path = self._config_path()
        text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        backups = sorted(self._backups_root.glob("config-*.toml"), reverse=True)
        return {
            "config_path": str(config_path),
            "exists": config_path.exists(),
            "router_configured": "[model_providers.router]" in text and 'model_provider = "router"' in text,
            "managed_by_app": MANAGED_BLOCK_START in text,
            "backup_count": len(backups),
            "latest_backup": str(backups[0]) if backups else None,
            "router_env_key": "CODEX_ROUTER_API_KEY",
        }

    def apply_router_config(self, *, router_base_url: str, default_model: str | None = None) -> dict[str, Any]:
        config_path = self._config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        self._backups_root.mkdir(parents=True, exist_ok=True)
        previous = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        if previous:
            backup_path = self._backups_root / f"config-{now_iso().replace(':', '').replace('.', '')}.toml"
            shutil.copy2(config_path, backup_path)
        profiles = self._profiles.list_profiles().get("profiles") or []
        chosen_model = default_model or self._default_router_model()
        catalog_path = self._write_model_catalog(profiles)
        managed_block = self._render_managed_block(
            model=chosen_model,
            model_catalog_json=str(catalog_path),
            router_base_url=router_base_url.rstrip("/"),
        )
        preserved = self._strip_router_entries(previous)
        final_text = managed_block if not preserved.strip() else f"{managed_block}\n\n{preserved.strip()}\n"
        config_path.write_text(final_text, encoding="utf-8", newline="\n")
        return self.status()

    def restore_latest_backup(self) -> dict[str, Any]:
        backups = sorted(self._backups_root.glob("config-*.toml"), reverse=True)
        if not backups:
            raise FileNotFoundError("No official Codex config backup is available.")
        config_path = self._config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backups[0], config_path)
        return self.status()

    def _config_path(self) -> Path:
        root = os.environ.get("ASTRABRIDGE_OFFICIAL_CODEX_HOME")
        if root:
            return Path(root).expanduser().resolve() / "config.toml"
        return Path.home() / ".codex" / "config.toml"

    def _write_model_catalog(self, profiles: list[dict[str, Any]]) -> Path:
        catalog_dir = self._config_path().parent / "model-catalogs"
        catalog_dir.mkdir(parents=True, exist_ok=True)
        models = []
        configured_models = self._router_config.models() if self._router_config is not None else []
        if configured_models:
            for model in effective_model_records(configured_models, include_disabled=False):
                models.append(catalog_entry_from_record(model))
        else:
            for profile in profiles:
                model = str(profile.get("model") or "").strip()
                provider = str(profile.get("provider_id") or "").strip()
                if not model or not provider:
                    continue
                context_window = int(profile.get("context_window") or known_context_window(provider, model) or 128_000)
                models.append(
                    model_catalog_entry(
                        model_id=f"{provider}/{model}",
                        provider_id=provider,
                        native_model=model,
                        display_name=str(profile.get("label") or model),
                        context_window=context_window,
                        reasoning_effort=profile.get("reasoning_effort"),
                        configured_model=profile,
                    )
                )
        target = catalog_dir / "router.json"
        write_json(target, {"models": models})
        return target

    def _default_router_model(self) -> str:
        preferred = preferred_provider_model_record("openai", include_deprecated=False)
        native_model = str((preferred or {}).get("native_model") or "").strip()
        if native_model:
            return f"openai/{native_model}"
        if self._router_config is not None:
            for model in self._router_config.models():
                if model.get("enabled", True):
                    return str(model.get("id"))
        for profile in self._profiles.list_profiles().get("profiles") or []:
            provider = str(profile.get("provider_id") or "").strip()
            model = str(profile.get("model") or "").strip()
            if provider and model:
                return f"{provider}/{model}"
        return "openai/gpt-5.5"

    def _render_managed_block(self, *, model: str, model_catalog_json: str, router_base_url: str) -> str:
        lines = [
            MANAGED_BLOCK_START,
            "# Provider API keys are NOT stored here.",
            'model_provider = "router"',
            f'model = "{_toml_escape(model)}"',
            f'model_catalog_json = "{_toml_escape(model_catalog_json)}"',
            "",
            "[model_providers.router]",
            'name = "Local Multi-Provider Router"',
            f'base_url = "{_toml_escape(router_base_url)}"',
            'env_key = "CODEX_ROUTER_API_KEY"',
            'wire_api = "responses"',
            "stream_idle_timeout_ms = 300000",
            "stream_max_retries = 5",
            "request_max_retries = 2",
            MANAGED_BLOCK_END,
        ]
        return "\n".join(lines)

    def _strip_router_entries(self, text: str) -> str:
        if not text.strip():
            return ""
        lines = text.splitlines()
        output: list[str] = []
        skipping_managed = False
        skipping_router_section = False
        for line in lines:
            stripped = line.strip()
            if stripped == MANAGED_BLOCK_START:
                skipping_managed = True
                continue
            if skipping_managed:
                if stripped == MANAGED_BLOCK_END:
                    skipping_managed = False
                continue
            if ROUTER_SECTION_RE.match(stripped):
                skipping_router_section = True
                continue
            if skipping_router_section:
                if stripped.startswith("[") and stripped.endswith("]"):
                    skipping_router_section = False
                else:
                    continue
            if any(stripped.startswith(f"{key} =") for key in TOP_LEVEL_ROUTER_KEYS):
                continue
            output.append(line)
        return "\n".join(output).strip()


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

