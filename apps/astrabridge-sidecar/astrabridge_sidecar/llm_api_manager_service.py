from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from .common import app_data_dir, new_id, now_iso, read_json, write_json
from .model_catalog import current_generated_catalog, effective_model_records, resolved_web_capability_fields


VAULT_SCHEMA = "astrabridge-llm-vault-v1"
ENCRYPTED_VAULT_SCHEMA = "astrabridge-llm-vault-encrypted-v1"
SESSION_MODES = {"anonymous", "managed_user"}
SENSITIVE_FIELD_NAMES = {"secret", "api_key", "key", "token", "authorization", "password"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class LlmApiManagerService:
    def __init__(self, router_config, router, root_path: Path | None = None) -> None:
        self._router_config = router_config
        self._router = router
        self.root_path = root_path or (app_data_dir() / "llm_api_manager")
        self.users_root = self.root_path / "users"
        self.health_path = self.root_path / "health_results.json"
        self._session: dict[str, Any] = self._anonymous_session()
        self._vault_plain: dict[str, Any] | None = None
        self._injected_env: dict[str, str | None] = {}

    def session(self) -> dict[str, Any]:
        users = self.list_users()["users"]
        public_session = {key: value for key, value in self._session.items() if not str(key).startswith("_")}
        current_profile = self._user_profile(str(public_session.get("username") or "")) if public_session.get("username") else {}
        return {
            **public_session,
            "users": users,
            "profile": current_profile,
            "key_count": len(self._vault_plain.get("keys", [])) if self._vault_plain else 0,
            "active_key_ids": dict((self._vault_plain or {}).get("active_key_ids") or {}),
        }

    def list_users(self) -> dict[str, Any]:
        users = []
        if self.users_root.exists():
            for path in sorted(self.users_root.iterdir()):
                if path.is_dir() and (path / "vault.abvault").exists():
                    profile = self._user_profile(path.name)
                    users.append({"username": path.name, "has_vault": True, **profile})
        return {"users": users}

    def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        username = self._normalize_username(payload.get("username") or "user")
        password = self._password_from_payload(payload, allow_desktop_default=username == "user")
        user_dir = self._user_dir(username)
        vault_path = user_dir / "vault.abvault"
        if vault_path.exists():
            raise ValueError(f"User vault already exists: {username}")
        vault = self._new_vault(username)
        unlock_key = self._write_encrypted_vault(username, vault, password)
        self._vault_plain = vault
        self._session = {
            "mode": "managed_user",
            "username": username,
            "unlocked": True,
            "started_at": now_iso(),
            "auth_surface": "llm_api_manager_vault",
            "_unlock_key": unlock_key,
        }
        return {"session": self.session(), "user": {"username": username, "created": True}}

    def login(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = str(payload.get("mode") or "managed_user").strip()
        if mode not in SESSION_MODES:
            raise ValueError(f"Unsupported login mode: {mode}")
        if mode == "anonymous":
            self.logout()
            return {"session": self.session()}
        username = self._normalize_username(payload.get("username") or "user")
        password = self._password_from_payload(payload, allow_desktop_default=False)
        vault, unlock_key = self._read_encrypted_vault(username, password)
        self._vault_plain = vault
        self._session = {
            "mode": "managed_user",
            "username": username,
            "unlocked": True,
            "started_at": now_iso(),
            "auth_surface": "llm_api_manager_vault",
            "_unlock_key": unlock_key,
        }
        return {"session": self.session()}

    def logout(self) -> dict[str, Any]:
        self._clear_injected_env()
        self._vault_plain = None
        self._session = self._anonymous_session()
        return {"session": self.session()}

    def switch_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.logout()
        return self.login({"mode": "managed_user", **payload})

    def change_password(self, payload: dict[str, Any]) -> dict[str, Any]:
        username = self._normalize_username(payload.get("username") or self._session.get("username") or "user")
        old_password = str(payload.get("old_password") or "")
        new_password = str(payload.get("new_password") or "")
        if not old_password or not new_password:
            raise ValueError("Both old_password and new_password are required.")
        vault, _ = self._read_encrypted_vault(username, old_password)
        unlock_key = self._write_encrypted_vault(username, vault, new_password)
        if self._session.get("mode") == "managed_user" and self._session.get("username") == username:
            self._vault_plain = vault
            self._session["_unlock_key"] = unlock_key
        return {"changed": True, "session": self.session()}

    def save_user_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        username = self._normalize_username(payload.get("username") or self._session.get("username") or "user")
        if self._session.get("mode") == "managed_user" and self._session.get("username") != username:
            raise ValueError("Cannot update a different user's profile while another managed user is active.")
        profile = {
            "display_name": str(payload.get("display_name") or username).strip()[:80],
            "avatar_path": str(payload.get("avatar_path") or "").strip()[:1000],
            "updated_at": now_iso(),
        }
        if profile["avatar_path"] and any(marker in profile["avatar_path"].lower() for marker in ("authorization", "bearer ", "api_key", "token", "cookie")):
            raise ValueError("avatar_path cannot contain secret-like values.")
        user_dir = self._user_dir(username)
        if not user_dir.exists():
            raise ValueError(f"User does not exist: {username}")
        write_json(user_dir / "profile.json", profile)
        return {"profile": self._user_profile(username), "session": self.session()}

    def list_keys(self) -> dict[str, Any]:
        if not self._vault_plain or self._session.get("mode") != "managed_user":
            return {"keys": [], "active_key_ids": {}, "locked": True}
        vault = self._vault_plain
        return {
            "keys": [self._redact_key_record(item) for item in list(vault.get("keys") or []) if isinstance(item, dict)],
            "active_key_ids": dict(vault.get("active_key_ids") or {}),
            "locked": False,
        }

    def save_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        vault = self._require_vault()
        provider_id = str(payload.get("provider_id") or "").strip()
        if not provider_id:
            raise ValueError("provider_id is required.")
        secret = str(payload.get("secret") or payload.get("api_key") or "").strip()
        if len(secret) < 8:
            raise ValueError("A plausible provider key is required.")
        env_key = str(payload.get("env_key") or self._provider_env_key(provider_id) or f"{provider_id.upper()}_API_KEY").strip()
        if not ENV_KEY_RE.match(env_key):
            raise ValueError("env_key must be an uppercase environment variable name.")
        key_id = str(payload.get("key_id") or "").strip() or new_id("KEY")
        now = now_iso()
        keys = [dict(item) for item in list(vault.get("keys") or []) if isinstance(item, dict)]
        existing = next((item for item in keys if str(item.get("key_id")) == key_id), None)
        label = str(payload.get("label") or (existing.get("label") if existing else "") or f"{provider_id} key").strip()
        record = {
            "key_id": key_id,
            "provider_id": provider_id,
            "label": label,
            "env_key": env_key,
            "fingerprint": self._fingerprint(secret),
            "enabled": bool(payload.get("enabled", True)),
            "last_test_status": existing.get("last_test_status") if existing else None,
            "last_test_at": existing.get("last_test_at") if existing else None,
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
            "secret": secret,
        }
        keys = [item for item in keys if str(item.get("key_id")) != key_id]
        keys.append(record)
        vault["keys"] = sorted(keys, key=lambda item: (str(item.get("provider_id")), str(item.get("label"))))
        active = dict(vault.get("active_key_ids") or {})
        if payload.get("make_default", True):
            active[provider_id] = key_id
        vault["active_key_ids"] = active
        self._save_current_vault()
        return {"key": self._redact_key_record(record), "keys": self.list_keys()["keys"]}

    def delete_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        vault = self._require_vault()
        key_id = str(payload.get("key_id") or "").strip()
        if not key_id:
            raise ValueError("key_id is required.")
        deleted_record = next((item for item in list(vault.get("keys") or []) if str(item.get("key_id")) == key_id), None)
        vault["keys"] = [item for item in list(vault.get("keys") or []) if str(item.get("key_id")) != key_id]
        active = dict(vault.get("active_key_ids") or {})
        for provider, active_id in list(active.items()):
            if active_id == key_id:
                active.pop(provider, None)
        vault["active_key_ids"] = active
        if deleted_record:
            env_key = str(deleted_record.get("env_key") or "")
            if env_key in self._injected_env:
                self._restore_injected_env(env_key)
        self._save_current_vault()
        return {"deleted": key_id, "keys": self.list_keys()["keys"]}

    def test_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        vault = self._require_vault()
        provider_id = str(payload.get("provider_id") or "").strip()
        key_id = str(payload.get("key_id") or "").strip()
        record = self._find_key(provider_id=provider_id, key_id=key_id or None)
        if not record:
            raise ValueError("No matching managed key is available.")
        model_id = str(payload.get("model_id") or "").strip() or None
        stream = bool(payload.get("stream"))
        env_key = str(record.get("env_key") or self._provider_env_key(str(record.get("provider_id") or "")))
        original = os.environ.get(env_key)
        try:
            os.environ[env_key] = str(record.get("secret") or "")
            result = self._router.test_provider(str(record.get("provider_id")), model_id, stream=stream)
        finally:
            if original is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original
        status = "pass" if result.get("ok") else "fail"
        record["last_test_status"] = status
        record["last_test_at"] = now_iso()
        record["updated_at"] = now_iso()
        self._save_current_vault()
        return {"ok": result.get("ok"), "result": self._sanitize_result(result), "key": self._redact_key_record(record), "keys": [self._redact_key_record(item) for item in vault.get("keys", [])]}

    def effective_catalog(self) -> dict[str, Any]:
        mode = str(self._session.get("mode") or "anonymous")
        providers = self._effective_providers()
        models = effective_model_records(self._router_config.models(), include_disabled=False)
        health = self.health_results()
        model_health = dict(health.get("model_health") or {})
        key_provider_ids = self._enabled_key_provider_ids()
        if mode == "managed_user":
            providers = [item for item in providers if str(item.get("id")) in key_provider_ids and item.get("enabled", True)]
            provider_ids = {str(item.get("id")) for item in providers}
            models = [
                self._annotate_model(item, model_health)
                for item in models
                if item.get("enabled", True)
                and str(item.get("provider")) in provider_ids
                and self._model_health_passes(str(item.get("id")), model_health)
            ]
            warnings = [] if models else ["Managed mode is unlocked, but no key-backed model has a passing health check yet."]
        else:
            models = [self._annotate_model(item, model_health) for item in models if item.get("enabled", True)]
            warnings = ["Anonymous mode can use public metadata only; provide a pasted key or environment variable before sending turns."]
        return {
            "mode": mode,
            "username": self._session.get("username"),
            "providers": [self._redact_provider(item, key_provider_ids) for item in providers],
            "models": models,
            "model_count": len(models),
            "verified_model_ids": sorted([model_id for model_id, item in model_health.items() if self._health_record_passes(item)]),
            "warnings": warnings,
            "generated_at": now_iso(),
        }

    def _effective_providers(self) -> list[dict[str, Any]]:
        generated = current_generated_catalog()
        generated_by_id = {str(item.get("id") or item.get("provider_id") or ""): dict(item) for item in generated.providers if isinstance(item, dict)}
        configured = [dict(item) for item in self._router_config.providers() if isinstance(item, dict)]
        configured_by_id = {str(item.get("id") or item.get("provider_id") or ""): item for item in configured}
        provider_ids: list[str] = []
        for item in generated.providers:
            provider_id = str(item.get("id") or item.get("provider_id") or "")
            if provider_id and provider_id not in provider_ids:
                provider_ids.append(provider_id)
        for item in configured:
            provider_id = str(item.get("id") or item.get("provider_id") or "")
            if provider_id and provider_id not in provider_ids:
                provider_ids.append(provider_id)
        merged: list[dict[str, Any]] = []
        for provider_id in provider_ids:
            combined = self._merge_provider_record(generated_by_id.get(provider_id, {}), configured_by_id.get(provider_id, {}))
            if combined:
                merged.append(combined)
        return merged

    def _merge_provider_record(self, baseline: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = dict(baseline)
        for key, value in override.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            merged[key] = value
        return merged

    def health_results(self) -> dict[str, Any]:
        payload = read_json(self.health_path, {})
        if not isinstance(payload, dict):
            payload = {}
        return {
            "updated_at": payload.get("updated_at"),
            "results": list(payload.get("results") or []),
            "model_health": dict(payload.get("model_health") or {}),
        }

    def run_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_ids = [str(item) for item in list(payload.get("model_ids") or []) if str(item).strip()]
        if not model_ids and payload.get("model_id"):
            model_ids = [str(payload.get("model_id"))]
        efforts = [str(item) for item in list(payload.get("efforts") or ["high"]) if str(item).strip()]
        temperatures = [self._optional_float(item) for item in list(payload.get("temperatures") or [0])]
        temperatures = [item for item in temperatures if item is not None]
        include_web_smoke = bool(payload.get("web_smoke", False))
        if not model_ids:
            model_ids = [str(item.get("id")) for item in self._router_config.models() if item.get("enabled", True)][:4]

        providers = {str(item.get("id")): item for item in self._router_config.providers()}
        models = {str(item.get("id")): item for item in self._router_config.models()}
        stored = self.health_results()
        results = list(stored.get("results") or [])
        model_health = dict(stored.get("model_health") or {})
        run_id = new_id("HEALTH")
        for model_id in model_ids:
            model = models.get(model_id)
            if not model:
                result = self._health_skip(run_id, model_id, "model_not_found", "Model is not in metadata.")
                results.append(result)
                continue
            provider_id = str(model.get("provider") or "")
            provider = providers.get(provider_id)
            if not provider:
                result = self._health_skip(run_id, model_id, "provider_not_found", "Provider is not configured.")
                results.append(result)
                model_health[model_id] = self._health_record(result)
                continue
            key = self._find_key(provider_id=provider_id) if self._session.get("mode") == "managed_user" else None
            env_key = str(provider.get("env_key") or "")
            original = os.environ.get(env_key)
            if key:
                os.environ[env_key] = str(key.get("secret") or "")
            elif not os.environ.get(env_key):
                result = self._health_skip(run_id, model_id, "missing_key", f"No managed key or environment value for {env_key}.")
                results.append(result)
                model_health[model_id] = self._health_record(result)
                continue
            try:
                for effort in efforts:
                    for temperature in temperatures:
                        try:
                            raw = self._router.test_model_case(
                                provider_id=provider_id,
                                model_id=model_id,
                                effort=effort,
                                temperature=float(temperature),
                                stream=bool(payload.get("stream", False)),
                            )
                            web_result = self._web_smoke(model, provider) if include_web_smoke else self._web_metadata_only(model)
                            result = {
                                "run_id": run_id,
                                "ok": bool(raw.get("ok")),
                                "provider": provider_id,
                                "model": model_id,
                                "effort": effort,
                                "temperature": temperature,
                                "status": raw.get("status"),
                                "connectivity": "pass" if raw.get("ok") else "fail",
                                "streaming": "pass" if payload.get("stream", False) and raw.get("ok") else "fail" if payload.get("stream", False) else "not_requested",
                                "reasoning_effort": "pass" if raw.get("ok") else "fail",
                                "temperature_policy": "pass" if not (raw.get("preview_warnings") or raw.get("warnings")) else "warn",
                                "modalities": "metadata_only",
                                "mcp_tools": str(model.get("mcp_smoke_status") or "untested"),
                                "codex_builtin_tools": "metadata_only",
                                "plan": str((model.get("planner_support") or {}).get("plan_mode") or "conservative"),
                                "request_user_input": str((model.get("planner_support") or {}).get("request_user_input") or "conservative"),
                                "goal": str((model.get("goal_support") or {}).get("thread_goal") or "app_server_native"),
                                "manual_compact": str((model.get("context_compaction_support") or {}).get("manual_compact") or "app_server_native"),
                                "auto_compact": str((model.get("context_compaction_support") or {}).get("auto_compact") or "configured_unverified"),
                                "compact_summary_quality": str((model.get("context_compaction_support") or {}).get("structured_summary_quality") or "untested"),
                                **web_result,
                                "preview_warnings": list(raw.get("preview_warnings") or raw.get("warnings") or []),
                                "response_diagnostics": dict(raw.get("response_diagnostics") or {}),
                                "failure_notice": dict(raw.get("failure_notice") or {}),
                                "adapter_warnings": list((raw.get("response_diagnostics") or {}).get("warnings") or raw.get("adapter_warnings") or []),
                                "response_excerpt": str(
                                    (raw.get("response_diagnostics") or {}).get("text_excerpt")
                                    or (raw.get("failure_notice") or {}).get("summary")
                                    or raw.get("response_excerpt")
                                    or ""
                                )[:300],
                                "last_verified_at": now_iso(),
                            }
                        except Exception as exc:  # noqa: BLE001
                            result = {
                                "run_id": run_id,
                                "ok": False,
                                "provider": provider_id,
                                "model": model_id,
                                "effort": effort,
                                "temperature": temperature,
                                "connectivity": "fail",
                                "error": str(exc)[:500],
                                "last_verified_at": now_iso(),
                            }
                        result = self._sanitize_result(result)
                        results.append(result)
                        model_health[model_id] = self._health_record(result)
                        if result.get("ok"):
                            self._mark_model_health(model, result)
                if key:
                    key["last_test_status"] = "pass" if self._model_health_passes(model_id, model_health) else "fail"
                    key["last_test_at"] = now_iso()
                    key["updated_at"] = now_iso()
            finally:
                if key:
                    if original is None:
                        os.environ.pop(env_key, None)
                    else:
                        os.environ[env_key] = original
        health_payload = {"updated_at": now_iso(), "results": results[-200:], "model_health": model_health}
        write_json(self.health_path, health_payload)
        if self._vault_plain:
            self._save_current_vault()
        return health_payload

    def inject_profile_key(self, profile: dict[str, Any]) -> dict[str, Any]:
        if self._session.get("mode") != "managed_user" or not self._vault_plain:
            return {"injected": False, "reason": "not_managed"}
        provider_id = str(profile.get("provider_id") or "").strip()
        record = self._find_key(provider_id=provider_id)
        if not record:
            return {"injected": False, "reason": "no_key"}
        env_key = str(profile.get("env_key") or record.get("env_key") or "")
        if not ENV_KEY_RE.match(env_key):
            return {"injected": False, "reason": "invalid_env_key"}
        if env_key not in self._injected_env:
            self._injected_env[env_key] = os.environ.get(env_key)
        os.environ[env_key] = str(record.get("secret") or "")
        return {"injected": True, "provider_id": provider_id, "env_key": env_key, "fingerprint": record.get("fingerprint")}

    def _new_vault(self, username: str) -> dict[str, Any]:
        return {
            "schema_version": VAULT_SCHEMA,
            "username": username,
            "keys": [],
            "active_key_ids": {},
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

    def _write_encrypted_vault(self, username: str, vault: dict[str, Any], password: str) -> str:
        user_dir = self._user_dir(username)
        user_dir.mkdir(parents=True, exist_ok=True)
        salt = os.urandom(16)
        nonce = os.urandom(12)
        kdf = {"kdf": "scrypt", "n": 32768, "r": 8, "p": 1, "salt": _b64(salt), "aead": "AES-256-GCM", "nonce": _b64(nonce)}
        key = self._derive_key(password, salt, kdf)
        payload = json.dumps({**vault, "updated_at": now_iso()}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ciphertext = self._aesgcm_encrypt(key, nonce, payload, username.encode("utf-8"))
        encrypted = {
            "schema_version": ENCRYPTED_VAULT_SCHEMA,
            "username": username,
            "crypto": kdf,
            "ciphertext": _b64(ciphertext),
            "created_at": vault.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        write_json(user_dir / "vault.abvault", encrypted)
        return key.hex()

    def _read_encrypted_vault(self, username: str, password: str) -> tuple[dict[str, Any], str]:
        path = self._user_dir(username) / "vault.abvault"
        if not path.exists():
            raise ValueError(f"No vault exists for user: {username}")
        payload = read_json(path, {})
        if payload.get("schema_version") != ENCRYPTED_VAULT_SCHEMA:
            raise ValueError("Unsupported vault file schema.")
        crypto = dict(payload.get("crypto") or {})
        salt = _unb64(str(crypto.get("salt") or ""))
        nonce = _unb64(str(crypto.get("nonce") or ""))
        key = self._derive_key(password, salt, crypto)
        try:
            plaintext = self._aesgcm_decrypt(key, nonce, _unb64(str(payload.get("ciphertext") or "")), username.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise PermissionError("Vault password is invalid or the vault is corrupted.") from exc
        vault = json.loads(plaintext.decode("utf-8"))
        if vault.get("schema_version") != VAULT_SCHEMA:
            raise ValueError("Unsupported decrypted vault schema.")
        return vault, key.hex()

    def _save_current_vault(self) -> None:
        if not self._vault_plain or self._session.get("mode") != "managed_user":
            return
        password = self._session.get("_password")
        username = str(self._session.get("username") or self._vault_plain.get("username") or "")
        if not username:
            raise ValueError("No active user.")
        current = read_json(self._user_dir(username) / "vault.abvault", {})
        crypto = dict(current.get("crypto") or {})
        if not crypto:
            raise ValueError("Active vault cannot be saved because the encrypted header is missing.")
        # Reuse the current encrypted header by requiring the caller to keep the plaintext in memory only.
        # Passwords are deliberately not stored in the session; derive by asking callers to use update helpers.
        # For normal unlocked sessions, re-encrypt with the transient unlock key kept below.
        unlock_key = self._session.get("_unlock_key")
        if not unlock_key:
            raise RuntimeError("Vault unlock key is unavailable; log in again before saving keys.")
        nonce = os.urandom(12)
        crypto["nonce"] = _b64(nonce)
        plaintext = json.dumps({**self._vault_plain, "updated_at": now_iso()}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ciphertext = self._aesgcm_encrypt(bytes.fromhex(str(unlock_key)), nonce, plaintext, username.encode("utf-8"))
        write_json(
            self._user_dir(username) / "vault.abvault",
            {
                "schema_version": ENCRYPTED_VAULT_SCHEMA,
                "username": username,
                "crypto": crypto,
                "ciphertext": _b64(ciphertext),
                "created_at": current.get("created_at") or self._vault_plain.get("created_at") or now_iso(),
                "updated_at": now_iso(),
            },
        )

    def _derive_key(self, password: str, salt: bytes, crypto: dict[str, Any]) -> bytes:
        if not password:
            raise ValueError("Vault password is required.")
        if str(crypto.get("kdf") or "scrypt") != "scrypt":
            raise ValueError("Unsupported KDF.")
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(crypto.get("n") or 32768),
            r=int(crypto.get("r") or 8),
            p=int(crypto.get("p") or 1),
            dklen=32,
            maxmem=128 * 1024 * 1024,
        )

    def _aesgcm_encrypt(self, key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        return AESGCM(key).encrypt(nonce, plaintext, aad)

    def _aesgcm_decrypt(self, key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        return AESGCM(key).decrypt(nonce, ciphertext, aad)

    def _password_from_payload(self, payload: dict[str, Any], *, allow_desktop_default: bool) -> str:
        password = str(payload.get("password") or "")
        if password:
            return password
        if allow_desktop_default and bool(payload.get("use_desktop_key_file")):
            path = Path.home() / "Desktop" / "key.txt"
            if not path.exists():
                raise FileNotFoundError("Desktop key.txt was not found.")
            return path.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
        raise ValueError("password is required.")

    def _require_vault(self) -> dict[str, Any]:
        if self._session.get("mode") != "managed_user" or not self._vault_plain:
            raise PermissionError("Unlock LLM API Manager first.")
        return self._vault_plain

    def _find_key(self, *, provider_id: str, key_id: str | None = None) -> dict[str, Any] | None:
        vault = self._vault_plain
        if not vault:
            return None
        keys = [item for item in list(vault.get("keys") or []) if isinstance(item, dict) and item.get("enabled", True)]
        if key_id:
            return next((item for item in keys if str(item.get("key_id")) == key_id), None)
        active = dict(vault.get("active_key_ids") or {})
        active_id = active.get(provider_id)
        if active_id:
            found = next((item for item in keys if str(item.get("key_id")) == str(active_id) and str(item.get("provider_id")) == provider_id), None)
            if found:
                return found
        return next((item for item in keys if str(item.get("provider_id")) == provider_id), None)

    def _enabled_key_provider_ids(self) -> set[str]:
        if not self._vault_plain:
            return set()
        return {str(item.get("provider_id")) for item in list(self._vault_plain.get("keys") or []) if item.get("enabled", True)}

    def _redact_key_record(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "key_id": item.get("key_id"),
            "provider_id": item.get("provider_id"),
            "label": item.get("label"),
            "env_key": item.get("env_key"),
            "fingerprint": item.get("fingerprint"),
            "enabled": bool(item.get("enabled", True)),
            "last_test_status": item.get("last_test_status"),
            "last_test_at": item.get("last_test_at"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }

    def _redact_provider(self, provider: dict[str, Any], key_provider_ids: set[str]) -> dict[str, Any]:
        return {
            **provider,
            "auth_key_ref": None,
            "managed_key_available": str(provider.get("id")) in key_provider_ids,
        }

    def _annotate_model(self, model: dict[str, Any], model_health: dict[str, Any]) -> dict[str, Any]:
        model_id = str(model.get("id") or "")
        health = dict(model_health.get(model_id) or {})
        return {
            **model,
            "verified": self._health_record_passes(health),
            "health": health,
        }

    def _model_health_passes(self, model_id: str, model_health: dict[str, Any]) -> bool:
        return self._health_record_passes(dict(model_health.get(model_id) or {}))

    def _health_record_passes(self, health: dict[str, Any]) -> bool:
        return bool(health.get("ok")) or str(health.get("connectivity") or "").lower() == "pass"

    def _health_record(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": bool(result.get("ok")),
            "connectivity": result.get("connectivity") or ("pass" if result.get("ok") else "fail"),
            "streaming": result.get("streaming", "untested"),
            "reasoning_effort": result.get("reasoning_effort", "untested"),
            "temperature_policy": result.get("temperature_policy", "untested"),
            "modalities": result.get("modalities", "metadata_only"),
            "mcp_tools": result.get("mcp_tools", "untested"),
            "codex_builtin_tools": result.get("codex_builtin_tools", "metadata_only"),
            "plan": result.get("plan", "conservative"),
            "request_user_input": result.get("request_user_input", "conservative"),
            "goal": result.get("goal", "app_server_native"),
            "manual_compact": result.get("manual_compact", "app_server_native"),
            "auto_compact": result.get("auto_compact", "configured_unverified"),
            "compact_summary_quality": result.get("compact_summary_quality", "untested"),
            "native_web_search_support": result.get("native_web_search_support", "unverified"),
            "tool_web_search_support": result.get("tool_web_search_support", "unverified"),
            "mcp_web_support": result.get("mcp_web_support", "unverified"),
            "web_smoke_status": result.get("web_smoke_status", "untested"),
            "citation_quality": result.get("citation_quality", "untested"),
            "last_web_verified_at": result.get("last_web_verified_at"),
            "adapter_warnings": list(result.get("adapter_warnings") or []),
            "response_diagnostics": dict(result.get("response_diagnostics") or {}),
            "failure_notice": dict(result.get("failure_notice") or {}),
            "last_verified_at": result.get("last_verified_at") or now_iso(),
            "reason": result.get("reason"),
        }

    def _mark_model_health(self, model: dict[str, Any], result: dict[str, Any]) -> None:
        defaults = resolved_web_capability_fields(model)
        updated = {
            **model,
            "native_web_search_support": result.get("native_web_search_support", defaults["native_web_search_support"]),
            "tool_web_search_support": result.get("tool_web_search_support", defaults["tool_web_search_support"]),
            "mcp_web_support": result.get("mcp_web_support", defaults["mcp_web_support"]),
            "web_smoke_status": result.get("web_smoke_status", defaults["web_smoke_status"]),
            "citation_quality": result.get("citation_quality", defaults["citation_quality"]),
            "last_web_verified_at": result.get("last_web_verified_at") or defaults.get("last_web_verified_at"),
            "last_verified_at": result.get("last_verified_at") or now_iso(),
            "verification_notes": f"LLM API Manager health check passed for connectivity/effort/temperature at {now_iso()}.",
        }
        self._router_config.upsert_model(updated)

    def _web_metadata_only(self, model: dict[str, Any]) -> dict[str, Any]:
        return resolved_web_capability_fields(
            model,
            tool_default="not_requested",
            smoke_default="not_requested",
            citation_default="not_requested",
            mcp_fallback_to_smoke=True,
        )

    def _web_smoke(self, model: dict[str, Any], provider: dict[str, Any]) -> dict[str, Any]:
        urls = [str(item) for item in list(model.get("source_urls") or []) if str(item).startswith(("http://", "https://"))]
        if not urls:
            provider_id = str(provider.get("id") or provider.get("provider_id") or "")
            urls = self._source_urls_for_provider(provider_id)
        status = "blocked_no_source"
        detail = ""
        for url in urls[:3]:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "AstraBridge/web-health"})
                with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310 - curated public docs only.
                    response.read(50_000)
                    status = "pass" if response.status < 400 else "fail"
                    detail = f"{url} -> HTTP {response.status}"
                    break
            except Exception as exc:  # noqa: BLE001
                status = "fail"
                detail = f"{url} -> {str(exc)[:160]}"
        defaults = resolved_web_capability_fields(model, mcp_fallback_to_smoke=True)
        return {
            "native_web_search_support": defaults["native_web_search_support"],
            "tool_web_search_support": "verified" if status == "pass" else status,
            "mcp_web_support": defaults["mcp_web_support"],
            "web_smoke_status": status,
            "citation_quality": "source_url_verified" if status == "pass" else "untested",
            "last_web_verified_at": now_iso(),
            "web_smoke_detail": detail,
        }

    def _source_urls_for_provider(self, provider_id: str) -> list[str]:
        lowered = provider_id.lower()
        if "deepseek" in lowered:
            return ["https://api-docs.deepseek.com/zh-cn/"]
        if "kimi" in lowered or "moonshot" in lowered:
            return [
                "https://platform.moonshot.ai/docs/overview",
                "https://platform.moonshot.ai/docs/guide/start-using-kimi-api",
                "https://platform.kimi.com/docs/pricing/chat",
            ]
        if "qwen" in lowered or "dashscope" in lowered:
            return ["https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions", "https://qwen.ai/apiplatform"]
        if "glm" in lowered or "zai" in lowered or "zhipu" in lowered:
            return ["https://open.bigmodel.cn/dev/api", "https://open.bigmodel.cn/pricing"]
        if "yunwu" in lowered:
            return ["https://yunwu.ai/pricing?group=Codex%E4%B8%93%E5%B1%9E"]
        return []

    def _health_skip(self, run_id: str, model_id: str, code: str, reason: str) -> dict[str, Any]:
        provider = model_id.split("/", 1)[0] if "/" in model_id else ""
        return {
            "run_id": run_id,
            "ok": False,
            "skipped": True,
            "provider": provider,
            "model": model_id,
            "connectivity": "blocked",
            "reason": code,
            "detail": reason,
            "last_verified_at": now_iso(),
        }

    def _sanitize_result(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in SENSITIVE_FIELD_NAMES or "authorization" in lowered:
                    sanitized[key] = "[redacted]"
                else:
                    sanitized[key] = self._sanitize_result(item)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_result(item) for item in value]
        if isinstance(value, str):
            return _redact_secret_like(value)
        return value

    def _provider_env_key(self, provider_id: str) -> str:
        provider = next((item for item in self._router_config.providers() if str(item.get("id")) == provider_id), None)
        return str((provider or {}).get("env_key") or f"{provider_id.upper()}_API_KEY")

    def _clear_injected_env(self) -> None:
        for key in list(self._injected_env):
            self._restore_injected_env(key)

    def _restore_injected_env(self, key: str) -> None:
        original = self._injected_env.pop(key, None)
        if original is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original

    def _anonymous_session(self) -> dict[str, Any]:
        return {
            "mode": "anonymous",
            "username": None,
            "unlocked": False,
            "started_at": now_iso(),
            "auth_surface": "session_or_environment_key",
        }

    def _user_dir(self, username: str) -> Path:
        return self.users_root / username

    def _user_profile(self, username: str) -> dict[str, Any]:
        if not username:
            return {}
        profile = read_json(self._user_dir(username) / "profile.json", {})
        return {
            "display_name": str(profile.get("display_name") or username),
            "avatar_path": str(profile.get("avatar_path") or ""),
            "updated_at": profile.get("updated_at"),
        }

    def _normalize_username(self, username: Any) -> str:
        value = str(username or "").strip()
        if not USERNAME_RE.match(value):
            raise ValueError("Username may contain only letters, numbers, dot, dash, and underscore.")
        return value

    def _optional_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _fingerprint(self, secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


SECRET_LIKE_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,}|[A-Za-z0-9_\-]{24,})")


def _redact_secret_like(value: str) -> str:
    return SECRET_LIKE_RE.sub("[redacted]", value)



