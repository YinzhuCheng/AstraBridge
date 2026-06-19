from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import app_data_dir, now_iso, read_json, write_json


PROFILE_TYPES = {"openai_api_key", "custom_provider"}
AUTH_MODES = {"session_paste", "env_ref", "key_file", "os_keychain"}
SECRET_FIELDS = {"api_key", "token", "secret", "password", "authorization", "cookie"}
REFERENCE_FIELDS = {"secret_ref", "env_key", "env_key_instructions"}
ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
ALLOWED_PROXY_MODES = {"direct", "system", "custom"}
PROXY_URL_RE = re.compile(r"^(https?|socks5)://(127\.0\.0\.1|localhost):([1-9][0-9]{0,4})$")


class ProfileService:
    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or (app_data_dir() / "profiles.json")

    def list_profiles(self) -> dict[str, Any]:
        payload = read_json(self.store_path, {"profiles": []})
        profiles = [item for item in payload.get("profiles") or [] if isinstance(item, dict)]
        existing = {str(item.get("profile_id")): item for item in profiles}
        changed = False
        for profile in self._default_profiles():
            profile_id = str(profile["profile_id"])
            if profile_id not in existing:
                existing[profile_id] = profile
                changed = True
        ordered = sorted(existing.values(), key=lambda item: str(item.get("profile_id")))
        if changed or profiles != ordered:
            payload["profiles"] = ordered
            write_json(self.store_path, payload)
        return payload

    def upsert_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        self._assert_no_secret(profile)
        profile_type = str(profile.get("type") or "").strip()
        if profile_type not in PROFILE_TYPES:
            raise ValueError(f"Unsupported profile type: {profile_type}")
        profile_id = str(profile.get("profile_id") or "").strip()
        if not profile_id:
            raise ValueError("profile_id is required.")
        label = str(profile.get("label") or "").strip()
        if not label:
            raise ValueError("label is required.")
        auth_mode = str(profile.get("auth_mode") or "env_ref").strip()
        if auth_mode not in AUTH_MODES:
            raise ValueError(f"Unsupported auth_mode: {auth_mode}")
        env_key = str(profile.get("env_key") or "").strip() or "OPENAI_API_KEY"
        if not ENV_KEY_RE.match(env_key):
            raise ValueError("env_key must be a valid environment variable name.")
        proxy_mode = str(profile.get("proxy_mode") or "direct").strip().lower()
        if proxy_mode not in ALLOWED_PROXY_MODES:
            raise ValueError("proxy_mode must be direct, system, or custom.")
        proxy_url = str(profile.get("proxy_url") or "").strip()
        if proxy_url:
            if "@" in proxy_url or not PROXY_URL_RE.match(proxy_url):
                raise ValueError("proxy_url must be a credential-free local HTTP(S) or SOCKS5 URL.")
        payload = self.list_profiles()
        existing = {item["profile_id"]: item for item in payload["profiles"]}
        current = existing.get(profile_id, {})
        merged = {
            **current,
            **profile,
            "profile_id": profile_id,
            "label": label,
            "auth_mode": auth_mode,
            "env_key": env_key,
            "proxy_mode": proxy_mode,
            "proxy_url": proxy_url,
            "updated_at": now_iso(),
        }
        merged.setdefault("created_at", now_iso())
        merged.setdefault("reasoning_effort", "high")
        merged.setdefault("wire_api", "responses")
        merged.setdefault("secret_ref", None)
        existing[profile_id] = merged
        payload["profiles"] = sorted(existing.values(), key=lambda item: item["profile_id"])
        write_json(self.store_path, payload)
        return merged

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        payload = self.list_profiles()
        payload["profiles"] = [item for item in payload["profiles"] if item.get("profile_id") != profile_id]
        write_json(self.store_path, payload)
        return {"deleted": profile_id}

    def get_profile(self, profile_id: str | None) -> dict[str, Any]:
        profiles = self.list_profiles()["profiles"]
        if profile_id:
            for item in profiles:
                if item.get("profile_id") == profile_id:
                    return item
            raise ValueError(f"Unknown profile: {profile_id}")
        return profiles[0]

    def resolve_runtime_profile(self, profile_id_or_provider: str | None) -> dict[str, Any]:
        """Resolve runtime-facing profile aliases without weakening profile CRUD.

        UI and automation often pass a provider id such as ``deepseek`` when the
        intended profile is the provider's default profile. Runtime entry points
        can accept that convenience alias, while settings/editing APIs stay
        strict and continue to require concrete ``profile_id`` values.
        """

        chosen = str(profile_id_or_provider or "").strip()
        if not chosen:
            return self.get_profile(None)
        try:
            return self.get_profile(chosen)
        except ValueError as exc:
            profiles = self.list_profiles()["profiles"]
            provider_matches = [
                item
                for item in profiles
                if str(item.get("provider_id") or "").strip() == chosen
            ]
            if not provider_matches:
                raise

            default_profile_id = f"{chosen}-default"
            for item in provider_matches:
                if item.get("profile_id") == default_profile_id:
                    return item

            sorted_matches = sorted(provider_matches, key=lambda item: str(item.get("profile_id") or ""))
            if len(sorted_matches) == 1:
                return sorted_matches[0]

            env_ref_matches = [item for item in sorted_matches if item.get("auth_mode") == "env_ref"]
            if len(env_ref_matches) == 1:
                return env_ref_matches[0]

            suggestions = ", ".join(str(item.get("profile_id") or "") for item in sorted_matches)
            raise ValueError(
                f"Unknown profile: {chosen}. Provider '{chosen}' has multiple profiles; use one of: {suggestions}"
            ) from exc

    def _assert_no_secret(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                lowered = str(key).lower()
                if lowered in REFERENCE_FIELDS:
                    continue
                if lowered in SECRET_FIELDS or any(part in lowered for part in SECRET_FIELDS):
                    raise ValueError(f"Profile metadata must not store secret field: {key}")
                self._assert_no_secret(nested)
        elif isinstance(value, list):
            for item in value:
                self._assert_no_secret(item)

    def _default_profiles(self) -> list[dict[str, Any]]:
        created_at = now_iso()
        return [
            {
                "profile_id": "openai-compatible",
                "label": "OpenAI Compatible",
                "type": "custom_provider",
                "provider_id": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5.3-codex",
                "reasoning_effort": "high",
                "wire_api": "responses",
                "env_key": "OPENAI_API_KEY",
                "auth_mode": "env_ref",
                "secret_ref": "env:OPENAI_API_KEY",
                "proxy_mode": "direct",
                "proxy_url": "",
                "created_at": created_at,
                "updated_at": created_at,
            },
            {
                "profile_id": "yunwu-gpt-55-xhigh",
                "label": "Yunwu GPT-5.5 xhigh",
                "type": "custom_provider",
                "provider_id": "yunwu",
                "base_url": "https://yunwu.ai/v1",
                "model": "gpt-5.5",
                "reasoning_effort": "xhigh",
                "wire_api": "responses",
                "env_key": "YUNWU_API_KEY",
                "auth_mode": "env_ref",
                "secret_ref": "env:YUNWU_API_KEY",
                "proxy_mode": "direct",
                "proxy_url": "",
                "created_at": created_at,
                "updated_at": created_at,
            },
        ]


