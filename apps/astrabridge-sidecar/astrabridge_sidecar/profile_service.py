from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import app_data_dir, now_iso, read_json, write_json
from .providers import default_profiles, get_provider_profile, resolve_provider_id


PROFILE_TYPES = {"openai_api_key", "custom_provider"}
AUTH_MODES = {"session_paste", "env_ref", "key_file", "os_keychain"}
SECRET_FIELDS = {"api_key", "token", "secret", "password", "authorization", "cookie"}
REFERENCE_FIELDS = {"secret_ref", "env_key", "env_key_instructions"}
ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
ALLOWED_PROXY_MODES = {"direct", "system", "custom"}
PROXY_URL_RE = re.compile(r"^(https?|socks5)://(127\.0\.0\.1|localhost):([1-9][0-9]{0,4})$")
PROVIDER_DEFAULT_METADATA_FIELDS = (
    "supported_reasoning_levels",
    "default_reasoning_level",
    "reasoning_policy_mode",
    "input_modalities",
    "capabilities",
    "edit_policy",
    "apply_patch_tool_type",
    "web_search_tool_type",
    "supports_search_tool",
    "supports_mcp_tools",
    "mcp_tool_call_policy",
    "mcp_verified_servers",
    "mcp_smoke_status",
    "mcp_tool_argument_validation",
    "native_web_search_support",
    "tool_web_search_support",
    "mcp_web_support",
    "web_smoke_status",
    "citation_quality",
    "codex_builtin_tools",
    "planner_support",
    "goal_support",
    "context_compaction_support",
    "temperature_default",
    "temperature_ui_min",
    "temperature_ui_max",
    "provider_temperature_min",
    "provider_temperature_max",
    "temperature_adapter_policy",
    "effective_context_window_percent",
    "supports_image_detail_original",
    "fallback_models",
    "downgrade_reasoning_levels",
    "drop_unsupported_modalities",
)
PROVIDER_DEFAULT_CORE_FIELDS = (
    "wire_api",
    "execution_backend",
)


def _metadata_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _looks_like_secret_field(key: str) -> bool:
    lowered = str(key).lower()
    if lowered in REFERENCE_FIELDS:
        return False
    if lowered in SECRET_FIELDS:
        return True
    if "authorization" in lowered or "bearer" in lowered:
        return True
    for suffix in ("_secret", "_password", "_cookie", "_authorization", "_bearer", "_api_key", "_token"):
        if lowered.endswith(suffix):
            return True
    return False


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
        for profile_id, profile in list(existing.items()):
            normalized_profile, normalized_changed = self._apply_provider_defaults(dict(profile))
            if normalized_changed or normalized_profile != profile:
                existing[profile_id] = normalized_profile
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
        merged, _ = self._apply_provider_defaults(merged)
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
            canonical_provider = None
            try:
                canonical_provider = resolve_provider_id(chosen)
            except ValueError:
                canonical_provider = chosen
            profiles = self.list_profiles()["profiles"]
            provider_matches = [
                item
                for item in profiles
                if str(item.get("provider_id") or "").strip() == canonical_provider
            ]
            if not provider_matches:
                raise

            default_profile_id = "openai-compatible" if canonical_provider == "openai" else f"{canonical_provider}-default"
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
                f"Unknown profile: {chosen}. Provider '{canonical_provider}' has multiple profiles; use one of: {suggestions}"
            ) from exc

    def _assert_no_secret(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if _looks_like_secret_field(str(key)):
                    raise ValueError(f"Profile metadata must not store secret field: {key}")
                self._assert_no_secret(nested)
        elif isinstance(value, list):
            for item in value:
                self._assert_no_secret(item)

    def _default_profiles(self) -> list[dict[str, Any]]:
        created_at = now_iso()
        profiles: list[dict[str, Any]] = []
        for profile in default_profiles():
            item = dict(profile)
            item.setdefault("created_at", created_at)
            item.setdefault("updated_at", created_at)
            normalized_item, _ = self._apply_provider_defaults(item)
            profiles.append(normalized_item)
        return profiles

    @staticmethod
    def _provider_defaults(provider_id: str) -> dict[str, Any]:
        candidate = str(provider_id or "").strip()
        if not candidate:
            return {}
        try:
            profile = get_provider_profile(candidate)
        except ValueError:
            return {}
        defaults = dict(profile.profile_metadata_payload())
        defaults.setdefault("supported_reasoning_levels", list(profile.reasoning_levels()))
        defaults.setdefault("default_reasoning_level", profile.default_reasoning_level())
        defaults.setdefault("wire_api", profile.adapter_type())
        defaults.setdefault("execution_backend", profile.runtime_backend)
        return defaults

    def _apply_provider_defaults(self, profile: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        changed = False
        provider_defaults = self._provider_defaults(str(profile.get("provider_id") or ""))
        resolved_reasoning_effort = (
            str(profile.get("reasoning_effort") or "").strip()
            or str(profile.get("default_reasoning_level") or "").strip()
            or str(provider_defaults.get("default_reasoning_level") or "").strip()
            or "high"
        )
        if str(profile.get("reasoning_effort") or "").strip() != resolved_reasoning_effort:
            profile["reasoning_effort"] = resolved_reasoning_effort
            changed = True
        for field in PROVIDER_DEFAULT_METADATA_FIELDS:
            if _metadata_value_present(profile.get(field)):
                continue
            value = provider_defaults.get(field)
            if not _metadata_value_present(value):
                continue
            profile[field] = dict(value) if isinstance(value, dict) else list(value) if isinstance(value, list) else value
            changed = True
        for field, fallback in (("wire_api", "responses"), ("execution_backend", "app_server")):
            if _metadata_value_present(profile.get(field)):
                continue
            value = provider_defaults.get(field)
            profile[field] = value if _metadata_value_present(value) else fallback
            changed = True
        return profile, changed


