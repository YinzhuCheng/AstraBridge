from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import re
import secrets
import socket
import ssl
import struct
import threading
import time
import urllib.parse
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any

from .model_catalog import effective_model_record, known_context_window, model_catalog_entry
from .providers import classify_runtime_failure, get_provider_profile, resolve_execution_route, resolve_provider_id, summarize_response_diagnostics
from .providers.transports import (
    ChatCompletionsTransport as RegistryChatCompletionsTransport,
    ProviderTransport as RegistryProviderTransport,
    transport_class_for_profile,
)
from .reasoning_policy import normalize_reasoning_effort
from .security import redact_sensitive
from .usage_signal import normalize_usage_signal, usage_not_available


ROUTER_PORT = 8787
ROUTER_ENV_KEY = "CODEX_ROUTER_API_KEY"


# Active provider transports are selected exclusively through
# astrabridge_sidecar.providers.transports.transport_class_for_profile(...).
class RouterService:
    def __init__(self, profiles_service, router_config_service=None, *, host: str = "127.0.0.1", port: int = ROUTER_PORT) -> None:
        self._profiles = profiles_service
        self._router_config = router_config_service
        self._host = host
        self._requested_port = port
        self._port = port
        self._port_auto_selected = False
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._events: list[dict[str, Any]] = []
        self._token = secrets.token_urlsafe(24)
        self._ensure_token()

    def start(self) -> None:
        with self._lock:
            if self._server is not None:
                return
            bind_port = self._port
            self._port_auto_selected = False
            if bind_port and self._port_in_use(bind_port):
                bind_port = 0
                self._port_auto_selected = True
                self._record(
                    "router_port_auto_selected",
                    {
                        "host": self._host,
                        "requested_port": self._requested_port,
                        "selected_port": "auto",
                    },
                )
            service = self

            class Handler(BaseHTTPRequestHandler):
                def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)

                def do_GET(self) -> None:  # noqa: N802
                    parsed = urllib.parse.urlparse(self.path)
                    if parsed.path == "/healthz":
                        self._send_json(200, {"ok": True, "service": "astrabridge", "ready": True})
                        return
                    if parsed.path == "/readyz":
                        self._send_json(200, service.status())
                        return
                    if parsed.path == "/v1/models":
                        authorization = self.headers.get("Authorization")
                        if not service._authorized(authorization):
                            service._record_auth_failure(parsed.path, authorization)
                            self._send_json(401, {"error": {"type": "auth_error", "message": "Missing or invalid router token."}})
                            return
                        self._send_json(200, {"object": "list", "data": service.list_models()})
                        return
                    self._send_json(404, {"error": {"type": "not_found", "message": "Not found."}})

                def do_POST(self) -> None:  # noqa: N802
                    parsed = urllib.parse.urlparse(self.path)
                    if parsed.path != "/v1/responses":
                        self._send_json(404, {"error": {"type": "not_found", "message": "Not found."}})
                        return
                    authorization = self.headers.get("Authorization")
                    if not service._authorized(authorization):
                        service._record_auth_failure(parsed.path, authorization)
                        self._send_json(401, {"error": {"type": "auth_error", "message": "Missing or invalid router token."}})
                        return
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                        service.forward_response(payload, self)
                    except Exception as exc:  # noqa: BLE001
                        payload_for_error = locals().get("payload") if isinstance(locals().get("payload"), dict) else {}
                        if isinstance(exc, urllib.error.HTTPError):
                            try:
                                profile = service._resolve_profile(payload_for_error)
                                normalized = service._normalize_provider_error(profile, exc.code, exc.read().decode("utf-8", errors="replace"))
                                envelope = normalized
                            except Exception:
                                context = service._error_context_for_payload(payload_for_error)
                                envelope = {
                                    "error": {
                                        "type": "provider_error",
                                        **context,
                                        "message": str(exc),
                                        "actionable_hint": service._provider_error_hint(str(exc), fallback="Check provider auth, request shape, router state, or upstream connectivity."),
                                    }
                                }
                        else:
                            context = service._error_context_for_payload(payload_for_error)
                            envelope = {
                                "error": {
                                    "type": "provider_error",
                                    **context,
                                    "message": str(exc),
                                    "actionable_hint": service._provider_error_hint(str(exc), fallback="Check provider auth, request shape, router state, or upstream connectivity."),
                                }
                            }
                        service._record("router_error", {"error": envelope["error"]})
                        self._send_json(400, envelope)

                def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                    service._record("router_http", {"message": format % args})

            try:
                self._server = ThreadingHTTPServer((self._host, bind_port), Handler)
            except OSError as exc:
                if not self._port_auto_selected and bind_port:
                    fallback_port = 0
                    if fallback_port != bind_port:
                        self._record(
                            "router_port_auto_selected_after_bind_failure",
                            {
                                "host": self._host,
                                "requested_port": self._requested_port,
                                "selected_port": "auto",
                                "error": str(exc),
                            },
                        )
                        self._server = ThreadingHTTPServer((self._host, fallback_port), Handler)
                        self._port_auto_selected = True
                    else:
                        self._record("router_bind_failed", {"host": self._host, "port": bind_port, "error": str(exc)})
                        raise RuntimeError(
                            f"Local router port is already in use or cannot be bound: {self._host}:{bind_port}. "
                            "Stop the stale AstraBridge sidecar or choose a different ASTRABRIDGE_PORT."
                        ) from exc
                else:
                    self._record("router_bind_failed", {"host": self._host, "port": bind_port, "error": str(exc)})
                    raise RuntimeError(
                        f"Local router port is already in use or cannot be bound: {self._host}:{bind_port}. "
                        "Stop the stale AstraBridge sidecar or choose a different ASTRABRIDGE_PORT."
                    ) from exc
            self._port = int(self._server.server_address[1])
            self._thread = threading.Thread(target=self._server.serve_forever, name="astrabridge", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            server = self._server
            self._server = None
            self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()

    def status(self) -> dict[str, Any]:
        profiles = self._router_profiles()
        enabled = [profile for profile in profiles if profile.get("enabled", True)]
        available_models = self.list_models()
        latest_test = self._router_config.snapshot().get("latest_test") if self._router_config is not None else None
        advertised_host = "127.0.0.1" if self._host in {"", "0.0.0.0"} else self._host
        return {
            "ok": True,
            "service": "astrabridge",
            "running": self._server is not None,
            "listen_host": self._host,
            "requested_port": self._requested_port,
            "listen_port": self._port,
            "port_auto_selected": self._port_auto_selected,
            "base_url": f"http://{advertised_host}:{self._port}/v1",
            "router_env_key": ROUTER_ENV_KEY,
            "token_loaded": bool(self._token),
            "token_fingerprint": hashlib.sha256(self._token.encode("utf-8")).hexdigest()[:12] if self._token else None,
            "provider_count": len(enabled),
            "model_count": len(available_models),
            "latest_test": latest_test,
            "providers": [
                {
                    "provider_id": profile.get("provider_id"),
                    "label": profile.get("label"),
                    "base_url": profile.get("base_url"),
                    "model": profile.get("model"),
                    "wire_api": profile.get("wire_api"),
                    "secret_loaded": bool(os.environ.get(str(profile.get("env_key") or ""))),
                }
                for profile in enabled
            ],
        }

    def health_status(self) -> dict[str, Any]:
        advertised_host = "127.0.0.1" if self._host in {"", "0.0.0.0"} else self._host
        config_snapshot = self._router_config.health_snapshot() if self._router_config is not None else {}
        raw_providers = [item for item in list(config_snapshot.get("providers") or []) if isinstance(item, dict)]
        providers = [
            {
                "provider_id": str(item.get("id") or item.get("provider_id") or ""),
                "label": str(item.get("display_name") or item.get("label") or item.get("id") or item.get("provider_id") or ""),
                "base_url": str(item.get("base_url") or ""),
                "model": str(item.get("default_model") or item.get("model") or ""),
                "wire_api": str(item.get("adapter_type") or item.get("wire_api") or ""),
                "secret_loaded": bool(os.environ.get(str(item.get("env_key") or ""))),
            }
            for item in raw_providers
            if item.get("enabled", True)
        ]
        provider_count = int(config_snapshot.get("provider_count") or len(providers))
        model_count = int(config_snapshot.get("model_count") or 0)
        latest_test = config_snapshot.get("latest_test")
        return {
            "ok": True,
            "service": "astrabridge",
            "running": self._server is not None,
            "listen_host": self._host,
            "requested_port": self._requested_port,
            "listen_port": self._port,
            "port_auto_selected": self._port_auto_selected,
            "base_url": f"http://{advertised_host}:{self._port}/v1",
            "router_env_key": ROUTER_ENV_KEY,
            "token_loaded": bool(self._token),
            "token_fingerprint": hashlib.sha256(self._token.encode("utf-8")).hexdigest()[:12] if self._token else None,
            "provider_count": provider_count,
            "model_count": model_count,
            "latest_test": latest_test,
            "providers": providers,
        }

    def runtime_environment(self) -> dict[str, str]:
        """Return the private router launch contract for this service instance.

        This must only be passed to a child app-server environment. It is kept
        separate from ``status`` so diagnostics never expose the router token.
        """
        with self._lock:
            advertised_host = "127.0.0.1" if self._host in {"", "0.0.0.0"} else self._host
            return {
                "ASTRABRIDGE_BASE_URL": f"http://{advertised_host}:{self._port}/v1",
                "ASTRABRIDGE_PORT": str(self._port),
                ROUTER_ENV_KEY: self._token,
            }

    def events(self, *, limit: int = 50) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit or 50), 200))
        with self._lock:
            events = list(self._events[-safe_limit:])
        return {"events": events, "count": len(events)}

    def list_models(self) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        configured = self._router_config.models() if self._router_config is not None else []
        if configured:
            for model in configured:
                if not model.get("enabled", True):
                    continue
                provider = self._provider_by_id(str(model.get("provider") or ""))
                profile = {**provider, "model": model.get("native_model"), "adapter_profile": model.get("adapter_profile")}
                models.append(self._model_metadata(str(model.get("id") or ""), profile, model))
            return models
        for profile in self._router_profiles():
            if not profile.get("enabled", True):
                continue
            provider = str(profile.get("provider_id") or "").strip()
            model = str(profile.get("model") or "").strip()
            if not provider or not model:
                continue
            models.append(self._model_metadata(f"{provider}/{model}", profile, {}))
        return models

    def forward_response(self, payload: dict[str, Any], handler: BaseHTTPRequestHandler) -> None:
        chosen, adapter, _warnings, upstream_payload = self._prepare_request(payload)
        secret = os.environ.get(str(chosen.get("env_key") or ""))
        if not secret:
            raise RuntimeError(f"Provider secret is not loaded for env key {chosen.get('env_key')}.")
        base_url = str(chosen.get("base_url") or "").rstrip("/")
        wire_api = adapter.wire_api()
        parsed = urllib.parse.urlparse(f"{base_url}{adapter.endpoint_path()}")
        stream = bool(payload.get("stream"))
        upstream_stream = stream and (adapter.supports_passthrough_stream() or wire_api == "chat")
        response = self._request_upstream(
            parsed=parsed,
            payload=upstream_payload,
            bearer=secret,
            stream=upstream_stream,
        )
        retry_attempt = 0
        error_text = ""
        while response.status >= 400:
            error_text = response.read().decode("utf-8", errors="replace")
            if not self._should_retry_provider_error(chosen, response.status, error_text, retry_attempt):
                break
            retry_attempt += 1
            self._record(
                "provider_retry",
                {
                    "provider": chosen.get("provider_id"),
                    "status": response.status,
                    "attempt": retry_attempt,
                    "reason": self._provider_error_code(error_text) or "transient_provider_error",
                },
            )
            response.close()
            time.sleep(min(1.5 * retry_attempt, 4.0))
            response = self._request_upstream(
                parsed=parsed,
                payload=upstream_payload,
                bearer=secret,
                stream=upstream_stream,
            )
        if response.status >= 400:
            normalized = self._normalize_provider_error(chosen, response.status, error_text)
            encoded = json.dumps(normalized, ensure_ascii=False).encode("utf-8")
            handler.send_response(response.status)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            handler.wfile.write(encoded)
            self._record("provider_error", {"provider": chosen.get("provider_id"), "status": response.status, "error": normalized})
            response.close()
            return
        if wire_api == "responses":
            handler.send_response(response.status)
            handler.send_header("Content-Type", response.getheader("Content-Type", "application/json; charset=utf-8"))
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            if stream:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
            else:
                body = response.read()
                handler.wfile.write(body)
        else:
            if stream:
                self._stream_chat_completion(adapter, response, payload, handler)
            else:
                body = response.read()
                upstream_json = json.loads(body.decode("utf-8") or "{}")
                client_response = adapter.client_response_from_upstream_json(upstream_json, payload)
                encoded = json.dumps(client_response, ensure_ascii=False).encode("utf-8")
                handler.send_response(response.status)
                handler.send_header("Content-Type", "application/json; charset=utf-8")
                handler.send_header("Content-Length", str(len(encoded)))
                handler.send_header("Cache-Control", "no-store")
                handler.end_headers()
                handler.wfile.write(encoded)
        self._record(
            "responses_forwarded",
            {
                "provider": chosen.get("provider_id"),
                "model": upstream_payload.get("model"),
                "stream": stream,
                "wire_api": wire_api,
                "adapter": adapter.describe(),
                "request": redact_sensitive(payload),
                "upstream_request": redact_sensitive(upstream_payload),
                "status": response.status,
            },
        )
        response.close()

    def complete_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        chosen, adapter, _warnings, upstream_payload = self._prepare_request(payload)
        secret = os.environ.get(str(chosen.get("env_key") or ""))
        if not secret:
            raise RuntimeError(f"Provider secret is not loaded for env key {chosen.get('env_key')}.")
        base_url = str(chosen.get("base_url") or "").rstrip("/")
        parsed = urllib.parse.urlparse(f"{base_url}{adapter.endpoint_path()}")
        response = self._request_upstream(
            parsed=parsed,
            payload=upstream_payload,
            bearer=secret,
            stream=False,
        )
        retry_attempt = 0
        error_text = ""
        while response.status >= 400:
            error_text = response.read().decode("utf-8", errors="replace")
            if not self._should_retry_provider_error(chosen, response.status, error_text, retry_attempt):
                break
            retry_attempt += 1
            self._record(
                "provider_retry",
                {
                    "provider": chosen.get("provider_id"),
                    "status": response.status,
                    "attempt": retry_attempt,
                    "reason": self._provider_error_code(error_text) or "transient_provider_error",
                },
            )
            response.close()
            time.sleep(min(1.5 * retry_attempt, 4.0))
            response = self._request_upstream(
                parsed=parsed,
                payload=upstream_payload,
                bearer=secret,
                stream=False,
            )
        if response.status >= 400:
            normalized = self._normalize_provider_error(chosen, response.status, error_text)
            self._record("provider_error", {"provider": chosen.get("provider_id"), "status": response.status, "error": normalized})
            response.close()
            raise RuntimeError(json.dumps(normalized, ensure_ascii=False))
        body = response.read()
        response.close()
        raw = json.loads(body.decode("utf-8") or "{}")
        normalized = adapter.normalize_response(raw, payload)
        semantic_conformance = self._semantic_conformance(adapter, chosen)
        semantic_conformance["response_observation"] = adapter.response_semantic_status(normalized)
        diagnostics = summarize_response_diagnostics(normalized)
        self._record(
            "responses_completed",
            {
                "provider": chosen.get("provider_id"),
                "model": upstream_payload.get("model"),
                "wire_api": adapter.wire_api(),
                "adapter": adapter.describe(),
                "request": redact_sensitive(payload),
                "upstream_request": redact_sensitive(upstream_payload),
                "response_diagnostics": diagnostics,
                "semantic_response_status": semantic_conformance["response_observation"].get("status"),
            },
        )
        return {
            "profile": {
                "profile_id": chosen.get("profile_id"),
                "provider_id": chosen.get("provider_id"),
                "model": chosen.get("model"),
                "wire_api": chosen.get("wire_api"),
                "adapter_profile": chosen.get("adapter_profile"),
                "execution_backend": chosen.get("execution_backend"),
                "execution_route_status": chosen.get("execution_route_status"),
            },
            "adapter": adapter.describe(),
            "normalized": normalized,
            "semantic_conformance": semantic_conformance,
        }

    def _resolve_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_model = str(payload.get("model") or "").strip()
        if "/" not in raw_model:
            raise RuntimeError("Router models must be prefixed as provider/model.")
        raw_provider_id, native_model = raw_model.split("/", 1)
        provider_family = _provider_family(raw_provider_id)
        canonical_model = f"{provider_family}/{native_model}" if provider_family else raw_model
        configured_models = self._router_config.models() if self._router_config is not None else []
        if configured_models:
            for item in configured_models:
                if not item.get("enabled", True):
                    continue
                if str(item.get("id") or "") in {raw_model, canonical_model}:
                    provider = self._provider_by_id(str(item.get("provider") or raw_provider_id))
                    return self._route_bound_profile(provider, model=item, native_model=native_model)
        family_match: dict[str, Any] | None = None
        for profile in self._router_profiles():
            if not profile.get("enabled", True):
                continue
            if str(profile.get("provider_id") or "").strip() == raw_provider_id and str(profile.get("model") or "").strip() == native_model:
                return self._route_bound_profile(profile, model={}, native_model=native_model)
            if (
                family_match is None
                and provider_family
                and str(profile.get("provider_family") or "").strip() == provider_family
                and str(profile.get("model") or "").strip() == native_model
            ):
                family_match = profile
        if family_match is not None:
            return self._route_bound_profile(family_match, model={}, native_model=native_model)
        raise RuntimeError(f"No router profile matches model {raw_model}.")

    def _route_bound_profile(
        self,
        provider: dict[str, Any],
        *,
        model: dict[str, Any],
        native_model: str,
    ) -> dict[str, Any]:
        provider_id = str(provider.get("provider_id") or provider.get("id") or model.get("provider") or "").strip()
        model_record = {
            **provider,
            **model,
            "id": str(model.get("id") or f"{provider_id}/{native_model}"),
            "provider": str(model.get("provider") or provider_id),
            "native_model": str(model.get("native_model") or native_model),
            "adapter_profile": model.get("adapter_profile") or provider.get("adapter_profile"),
        }
        evidence = model.get("execution_route_evidence")
        if not isinstance(evidence, dict):
            evidence = provider.get("execution_route_evidence")
        route = resolve_execution_route(
            model_record,
            provider=provider,
            evidence=dict(evidence) if isinstance(evidence, dict) else None,
        )
        driver = dict(route.get("driver") or {})
        authority = dict(route.get("authority") or {})
        tool_mode = dict(route.get("tool_mode") or {})
        return {
            **provider,
            "model": native_model,
            "adapter_profile": model_record.get("adapter_profile"),
            "configured_execution_backend": str(
                driver.get("configured_id")
                or provider.get("execution_backend")
                or provider.get("runtime_backend")
                or "app_server"
            ),
            "execution_backend": str(driver.get("execution_id") or "preview_review"),
            "execution_route": route,
            "execution_route_status": str(driver.get("admission") or "review_only"),
            "authority_tier": str(authority.get("effective_tier") or "C"),
            "declared_authority_tier": str(authority.get("declared_tier") or "C"),
            "tool_mode": str(tool_mode.get("effective") or "review_only"),
        }

    def _router_profiles(self) -> list[dict[str, Any]]:
        if self._router_config is not None:
            providers = self._router_config.providers()
            if providers:
                return [
                    self._registry_enriched_provider(
                        {
                            "enabled": item.get("enabled", True),
                            "provider_id": str(item.get("id") or item.get("provider_id") or ""),
                            "provider_family": item.get("provider_family") or item.get("adapter_profile"),
                            "label": item.get("display_name"),
                            "base_url": item.get("base_url"),
                            "model": item.get("default_model"),
                            "wire_api": item.get("adapter_type"),
                            "adapter_profile": item.get("adapter_profile"),
                            "execution_backend": item.get("runtime_backend") or item.get("execution_backend"),
                            "env_key": item.get("env_key"),
                            "auth_mode": item.get("auth_mode"),
                            "secret_ref": item.get("auth_key_ref"),
                            "proxy_mode": item.get("proxy_mode"),
                            "proxy_url": item.get("proxy_url"),
                        }
                    )
                    for item in providers
                ]
        profiles = self._profiles.list_profiles().get("profiles") or []
        router_profiles: list[dict[str, Any]] = []
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            if not profile.get("base_url"):
                continue
            router_profiles.append(self._registry_enriched_provider({"enabled": True, **profile, "provider_id": str(profile.get("provider_id") or "openai")}))
        deduped: dict[tuple[str, str], dict[str, Any]] = {}
        for profile in router_profiles:
            key = (str(profile.get("provider_id") or ""), str(profile.get("model") or ""))
            existing = deduped.get(key)
            if existing is None or _profile_priority(profile) < _profile_priority(existing):
                deduped[key] = profile
        return list(deduped.values())

    def _adapter_for(self, profile: dict[str, Any]) -> RegistryProviderTransport:
        provider_family = (
            _provider_family(
                profile.get("adapter_profile"),
                provider_family=profile.get("provider_family"),
                source_provider_id=profile.get("provider_id"),
                base_url=profile.get("base_url"),
                model=profile.get("model"),
            )
            or "openai"
        )
        transport_class = transport_class_for_profile(profile, provider_family=provider_family)
        return transport_class(self, profile)

    def _adapter_for_provider(self, provider_id: str) -> RegistryProviderTransport:
        return self._adapter_for({"provider_id": provider_id, "provider_family": _provider_family(provider_id)})

    def _provider_by_id(self, provider_id: str) -> dict[str, Any]:
        for profile in self._router_profiles():
            if str(profile.get("provider_id") or "") == provider_id:
                return profile
        provider_family = _provider_family(provider_id)
        if provider_family:
            for profile in self._router_profiles():
                if str(profile.get("provider_family") or "") == provider_family:
                    return profile
        raise RuntimeError(f"Unknown provider {provider_id}.")

    def _registry_enriched_provider(self, provider: dict[str, Any]) -> dict[str, Any]:
        provider_family = _provider_family(
            provider.get("provider_family") or provider.get("adapter_profile") or provider.get("provider_id"),
            base_url=provider.get("base_url"),
            model=provider.get("model"),
        ) or "openai"
        profile = get_provider_profile(provider_family)
        return {
            **provider,
            "provider_family": profile.id,
            "aliases": list(profile.aliases),
            "capabilities": profile.capability_payload(),
            "reasoning_policy_mode": profile.reasoning_policy.mode,
            "edit_policy": {
                "small": profile.edit_policy.small,
                "medium": profile.edit_policy.medium,
                "large": profile.edit_policy.large,
            },
        }

    def _model_metadata(self, model_id: str, profile: dict[str, Any], configured_model: dict[str, Any]) -> dict[str, Any]:
        context_window = int(configured_model.get("advertised_context_window") or _fallback_context_window(profile) or 128000)
        native_model = str(profile.get("model") or model_id.split("/", 1)[-1])
        display_name = str(configured_model.get("display_name") or model_id)
        entry = model_catalog_entry(
            model_id=model_id,
            provider_id=str(profile.get("provider_id") or ""),
            native_model=native_model,
            display_name=display_name,
            context_window=context_window,
            reasoning_effort=profile.get("reasoning_effort"),
            configured_model=configured_model,
            auto_compact_token_limit=_optional_positive_int(configured_model.get("auto_compact_token_limit")),
        )
        return {
            **entry,
            "id": model_id,
            "object": "model",
            "created": 0,
            "owned_by": profile.get("provider_id"),
            "adapter": self._adapter_for(profile).describe(),
        }

    def _authorized(self, authorization: str | None) -> bool:
        token = self._token
        if not token:
            return False
        prefix = "Bearer "
        return bool(authorization and authorization.startswith(prefix) and secrets.compare_digest(authorization[len(prefix):], token))

    def _record_auth_failure(self, path: str, authorization: str | None) -> None:
        prefix = "Bearer "
        provided = authorization[len(prefix):] if authorization and authorization.startswith(prefix) else ""
        self._record(
            "router_auth_failed",
            {
                "path": path,
                "authorization_present": bool(authorization),
                "provided_fingerprint": hashlib.sha256(provided.encode("utf-8")).hexdigest()[:12] if provided else None,
                "expected_fingerprint": hashlib.sha256(self._token.encode("utf-8")).hexdigest()[:12] if self._token else None,
            },
        )

    def _ensure_token(self) -> None:
        os.environ[ROUTER_ENV_KEY] = self._token

    def rotate_token(self) -> dict[str, Any]:
        self._token = secrets.token_urlsafe(24)
        os.environ[ROUTER_ENV_KEY] = self._token
        return self.status()

    def resolve_reasoning_effort(self, profile: dict[str, Any], model_id: Any) -> str | None:
        if self._router_config is None:
            return normalize_reasoning_effort(profile.get("reasoning_effort"))
        reasoning = self._router_config.reasoning()
        model_overrides = dict(reasoning.get("model_overrides") or {})
        provider_overrides = dict(reasoning.get("provider_overrides") or {})
        model_key = str(model_id or "")
        provider_key = str(profile.get("provider_id") or "")
        for candidate in (
            model_overrides.get(model_key),
            provider_overrides.get(provider_key),
            reasoning.get("global_effort"),
            profile.get("reasoning_effort"),
        ):
            normalized = normalize_reasoning_effort(candidate)
            if normalized is not None:
                return normalized
        return None

    def _prepare_request(
        self,
        payload: dict[str, Any],
        *,
        include_warnings: bool = False,
    ) -> tuple[dict[str, Any], RegistryProviderTransport, list[str], dict[str, Any]]:
        profile = self._resolve_profile(payload)
        adapter = self._adapter_for(profile)
        warnings = (
            [
                *self.reasoning_warnings(payload),
                *self.temperature_warnings(profile, payload.get("model"), payload.get("temperature")),
            ]
            if include_warnings
            else []
        )
        self._validate_request_shape(profile, payload)
        self._validate_execution_route_request(profile, payload)
        adapter.validate_semantic_request(payload)
        upstream_payload = adapter.upstream_payload(payload)
        return profile, adapter, warnings, upstream_payload

    def _validate_request_shape(self, profile: dict[str, Any], payload: dict[str, Any]) -> None:
        provider_family = (
            _provider_family(
                profile.get("adapter_profile"),
                provider_family=profile.get("provider_family"),
                source_provider_id=profile.get("provider_id"),
                base_url=profile.get("base_url"),
                model=profile.get("model"),
            )
            or str(profile.get("provider_id") or "").strip()
        )
        if provider_family == "kimi":
            self._validate_kimi_request_shape(profile, payload)

    def _validate_execution_route_request(self, profile: dict[str, Any], payload: dict[str, Any]) -> None:
        """Prevent a review/proposal route from acquiring a tool surface.

        The Router still permits plain-text review requests on an unverified
        provider route. It must not forward an active tool definition merely
        because a caller supplied one; that would turn ProviderProfile defaults
        into implicit execution authority before route evidence exists.
        """

        tool_mode = str(profile.get("tool_mode") or "review_only").strip().lower()
        if tool_mode not in {"review_only", "propose_only"}:
            return
        tools = payload.get("tools")
        has_tools = bool(tools) if isinstance(tools, (list, tuple, dict)) else bool(tools)
        # A provider-specific preview can contain a tool_choice hint without
        # tool definitions (for example to validate a fixed request shape).
        # That is not an executable tool surface. Definitions are the boundary
        # that would let an unverified route issue a callable action.
        if not has_tools:
            return
        admission = str(profile.get("execution_route_status") or "review_only")
        raise ValueError(
            f"Execution route is {admission} with {tool_mode} tool policy; "
            "model-and-endpoint route evidence is required before forwarding tool calls."
        )

    def _validate_kimi_request_shape(self, profile: dict[str, Any], payload: dict[str, Any]) -> None:
        raw_model = str(payload.get("model") or profile.get("model") or "").strip()
        native_model = raw_model.split("/", 1)[1] if "/" in raw_model else raw_model
        if native_model not in {"kimi-k3", "kimi-k2.6", "kimi-k2.7-code", "kimi-k2.7-code-highspeed"}:
            return
        reasoning_effort = self._effective_reasoning_effort(profile, payload)
        if native_model == "kimi-k3" and reasoning_effort == "off":
            raise ValueError("kimi-k3 is always-thinking and does not support reasoning effort 'off'; use low, high, or xhigh.")
        if native_model in {"kimi-k2.7-code", "kimi-k2.7-code-highspeed"} and reasoning_effort == "off":
            raise ValueError(f"{native_model} does not support reasoning effort 'off'; use low, medium, high, or xhigh.")
        if _contains_non_data_image_reference(payload.get("input")):
            raise ValueError("Kimi image inputs must use base64 data URLs or localImage paths; remote image URLs are not supported.")
        if native_model == "kimi-k3":
            temperature = _optional_float(payload.get("temperature"))
            if temperature is not None and abs(temperature - 1.0) > 0.000001:
                raise ValueError("kimi-k3 only supports temperature=1.0; omit the field to use the provider-fixed value.")
            top_p = _optional_float(payload.get("top_p"))
            if top_p is not None and abs(top_p - 0.95) > 0.000001:
                raise ValueError("kimi-k3 only supports top_p=0.95; omit the field to use the provider-fixed value.")
            n = _optional_int(payload.get("n"))
            if n is not None and n != 1:
                raise ValueError("kimi-k3 only supports n=1.")
            for field in ("presence_penalty", "frequency_penalty"):
                penalty = _optional_float(payload.get(field))
                if penalty is not None and abs(penalty) > 0.000001:
                    raise ValueError(f"kimi-k3 only supports {field}=0; omit the field to use the provider-fixed value.")
            return
        thinking_restricted = native_model in {"kimi-k2.7-code", "kimi-k2.7-code-highspeed"} or reasoning_effort != "off"
        if not thinking_restricted:
            return
        tool_choice = payload.get("tool_choice")
        if tool_choice not in {None, "auto", "none"}:
            raise ValueError(f"{native_model} only supports tool_choice 'auto' or 'none' for the current thinking mode.")
        top_p = _optional_float(payload.get("top_p"))
        if top_p is not None and abs(top_p - 0.95) > 0.000001:
            raise ValueError(f"{native_model} only supports top_p=0.95 for the current thinking mode.")
        n = _optional_int(payload.get("n"))
        if n is not None and n != 1:
            raise ValueError(f"{native_model} only supports n=1 for the current thinking mode.")
        presence_penalty = _optional_float(payload.get("presence_penalty"))
        if presence_penalty is not None and abs(presence_penalty) > 0.000001:
            raise ValueError(f"{native_model} only supports presence_penalty=0 for the current thinking mode.")
        frequency_penalty = _optional_float(payload.get("frequency_penalty"))
        if frequency_penalty is not None and abs(frequency_penalty) > 0.000001:
            raise ValueError(f"{native_model} only supports frequency_penalty=0 for the current thinking mode.")

    def _effective_reasoning_effort(self, profile: dict[str, Any], payload: dict[str, Any]) -> str | None:
        reasoning = payload.get("reasoning")
        if isinstance(reasoning, dict):
            explicit = normalize_reasoning_effort(reasoning.get("effort"))
            if explicit is not None:
                return explicit
        return normalize_reasoning_effort(self.resolve_reasoning_effort(profile, payload.get("model")))

    def preview_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile, adapter, warnings, upstream_payload = self._prepare_request(payload, include_warnings=True)
        provider_id = str(profile.get("provider_id") or "")
        model_id = self._normalize_model_id(provider_id, payload.get("model") or profile.get("model"))
        return {
            "provider": provider_id,
            "model": payload.get("model"),
            "adapter": adapter.describe(),
            "execution_route": dict(profile.get("execution_route") or {}),
            "execution_route_status": str(profile.get("execution_route_status") or "review_only"),
            "semantic_conformance": self._semantic_conformance(adapter, profile),
            "warnings": warnings,
            "upstream_payload": redact_sensitive(upstream_payload),
            "usage_signal": usage_not_available(
                source="router_preview",
                reason="preview_only_no_provider_call",
                provider_id=provider_id,
                model=model_id,
                request_kind=adapter.describe(),
                pricing=self._model_usage_pricing(provider_id, model_id),
            ),
        }

    @staticmethod
    def _semantic_conformance(adapter: RegistryProviderTransport, profile: dict[str, Any]) -> dict[str, Any]:
        contract = adapter.semantic_conformance_contract()
        route_status = str(profile.get("execution_route_status") or "review_only")
        admitted = route_status in {"verified_non_default", "default_eligible"}
        route = dict(profile.get("execution_route") or {})
        evidence = dict(route.get("evidence") or {})
        contract["execution_route"] = {
            "status": route_status,
            "driver": str(profile.get("execution_backend") or "preview_review"),
            "authority_tier": str(profile.get("authority_tier") or "C"),
            "evidence_state": str(evidence.get("effective_state") or "documented"),
            "coding_agent_semantics": "admitted" if admitted else "review_only",
            "action": (
                "The route has current coding-route evidence; native tool policy and task admission still apply."
                if admitted
                else "Do not treat protocol/text success as coding-agent readiness; record exact model-and-endpoint route evidence first."
            ),
        }
        return contract

    def reasoning_warnings(self, payload: dict[str, Any]) -> list[str]:
        reasoning = payload.get("reasoning")
        if not isinstance(reasoning, dict):
            return []
        raw_effort = str(reasoning.get("effort") or "").strip().lower()
        if not raw_effort:
            return []
        normalized = normalize_reasoning_effort(raw_effort)
        if normalized is None:
            return [f"Unsupported reasoning effort '{raw_effort}' is omitted from the upstream payload; provider defaults will apply."]
        if normalized != raw_effort:
            return [f"Reasoning effort '{raw_effort}' is normalized to '{normalized}' for Codex/runtime compatibility."]
        return []

    def test_provider(self, provider_id: str, model_id: str | None = None, *, stream: bool = False) -> dict[str, Any]:
        provider = self._provider_by_id(provider_id)
        model = self._normalize_model_id(provider_id, model_id or provider.get("default_model") or provider.get("model"))
        payload = {"model": model, "input": "Reply with exactly: ok", "stream": stream}
        result = self._provider_test_result(payload, stream=stream)
        if self._router_config is not None:
            self._router_config.record_test_result(result)
        return result

    def test_provider_vision(self, provider_id: str, model_id: str | None = None, *, stream: bool = False) -> dict[str, Any]:
        """Run one bounded image-grounding probe without exposing provider credentials."""
        provider = self._provider_by_id(provider_id)
        model = self._normalize_model_id(provider_id, model_id or provider.get("default_model") or provider.get("model"))
        payload = {
            "model": model,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "What is the dominant color of the attached image? Reply with one lowercase English word only."},
                        {"type": "input_image", "image_url": _vision_probe_red_square_data_uri(), "detail": "low"},
                    ],
                }
            ],
            "stream": stream,
            "reasoning": {"effort": "off"},
            "astrabridge_probe_force_final": True,
        }
        result = self._provider_test_result(payload, stream=stream)
        response_text = str(result.get("response_excerpt") or "").strip().lower()
        grounded = bool(result.get("ok")) and response_text == "red"
        result["ok"] = grounded
        result["image_probe"] = {
            "fixture": "red_square_png",
            "expected_response": "red",
            "grounded": grounded,
        }
        if self._router_config is not None:
            self._router_config.record_test_result(result)
        return result

    def test_model_case(self, *, provider_id: str, model_id: str, effort: str | None = None, temperature: float | None = None, stream: bool = False) -> dict[str, Any]:
        model_id = self._normalize_model_id(provider_id, model_id)
        payload: dict[str, Any] = {"model": model_id, "input": "Reply with exactly: ok", "stream": stream}
        if effort:
            payload["reasoning"] = {"effort": effort}
        if temperature is not None:
            payload["temperature"] = temperature
        provider = self._provider_by_id(provider_id)
        result = {
            **self._provider_test_result(payload, stream=stream),
            "native_model": provider.get("model"),
            "effort": effort,
            "temperature": temperature,
        }
        if self._router_config is not None:
            self._router_config.record_test_result(result)
        return result

    def _provider_test_result(self, payload: dict[str, Any], *, stream: bool) -> dict[str, Any]:
        provider_id, model_id = self._provider_and_model_from_payload(payload)
        parsed_preview: dict[str, Any] | None = None
        preview_warnings: list[str] = []
        semantic_conformance: dict[str, Any] | None = None
        try:
            parsed_preview = self.preview_payload(payload)
            preview_warnings = list(parsed_preview.get("warnings") or [])
            semantic_conformance = (
                dict(parsed_preview.get("semantic_conformance") or {}) if isinstance(parsed_preview, dict) else None
            )
            diagnostics: dict[str, Any] | None = None
            failure_notice: dict[str, Any] | None = None
            response_excerpt = ""
            content_type = "application/json; charset=utf-8"
            status = 200
            ok = True
            usage: Any = None
            request_kind = "stream" if stream else "request_response"
            if stream:
                buffer = _BufferHandler()
                self.forward_response(payload, buffer)
                status = buffer.status_code
                ok = status == 200
                content_type = buffer.headers.get("Content-Type")
                raw_text = buffer.wfile.getvalue().decode("utf-8", errors="replace")[:1200]
                if ok:
                    response_excerpt = raw_text
                else:
                    failure_notice = self._failure_notice_payload(raw_text, provider_id=provider_id, model_id=model_id)
                    response_excerpt = self._failure_excerpt(failure_notice, fallback=raw_text)
            else:
                completed = self.complete_response(payload)
                normalized = completed["normalized"]
                semantic_conformance = dict(completed.get("semantic_conformance") or {})
                usage = getattr(normalized, "usage", None)
                diagnostics = summarize_response_diagnostics(normalized, text_limit=1200)
                response_excerpt = str(diagnostics.get("text_excerpt") or "")[:1200]
                response_observation = dict(semantic_conformance.get("response_observation") or {})
                if str(response_observation.get("status") or "") == "blocked":
                    ok = False
                    failure_notice = self._failure_notice_payload(
                        "semantic output is empty: " + str(response_observation.get("action") or "provider response was not semantically usable"),
                        provider_id=provider_id,
                        model_id=model_id,
                    )
                    response_excerpt = self._failure_excerpt(failure_notice, fallback=response_excerpt)
            usage_reason = None
            if usage is None:
                usage_reason = "stream_health_usage_not_extracted" if stream and ok else "provider_response_usage_not_reported"
            result = {
                "ok": ok,
                "provider": provider_id,
                "model": model_id,
                "stream": stream,
                "status": status,
                "content_type": content_type,
                "preview": (parsed_preview or {}).get("upstream_payload") or {},
                "preview_warnings": preview_warnings,
                "warnings": preview_warnings,
                "semantic_conformance": semantic_conformance,
                "response_excerpt": response_excerpt,
                "response_diagnostics": diagnostics,
                "usage_signal": normalize_usage_signal(
                    source="router_provider_health",
                    provider_id=provider_id,
                    model=model_id,
                    usage=usage,
                    pricing=self._model_usage_pricing(provider_id, model_id),
                    reason=usage_reason,
                    request_kind=request_kind,
                ),
            }
            if failure_notice:
                result["usage_signal"] = usage_not_available(
                    source="router_provider_health",
                    reason="provider_health_failed",
                    provider_id=provider_id,
                    model=model_id,
                    request_kind=request_kind,
                    pricing=self._model_usage_pricing(provider_id, model_id),
                )
                result["failure_notice"] = failure_notice
            return result
        except Exception as exc:  # noqa: BLE001
            failure_notice = self._failure_notice_payload(str(exc), provider_id=provider_id, model_id=model_id)
            result = {
                "ok": False,
                "provider": provider_id,
                "model": model_id,
                "stream": stream,
                "status": int(failure_notice.get("native_status") or 400),
                "content_type": "application/json; charset=utf-8",
                "preview": (parsed_preview or {}).get("upstream_payload") or {},
                "preview_warnings": preview_warnings,
                "warnings": preview_warnings,
                "semantic_conformance": semantic_conformance,
                "response_excerpt": self._failure_excerpt(failure_notice, fallback=str(exc)[:1200]),
                "response_diagnostics": None,
                "failure_notice": failure_notice,
                "usage_signal": usage_not_available(
                    source="router_provider_health",
                    reason="provider_health_failed",
                    provider_id=provider_id,
                    model=model_id,
                    request_kind="stream" if stream else "request_response",
                    pricing=self._model_usage_pricing(provider_id, model_id),
                ),
            }
            return result

    def _normalize_model_id(self, provider_id: str, model_id: Any) -> str:
        raw = str(model_id or "").strip()
        if not raw:
            raise RuntimeError(f"No model configured for provider {provider_id}.")
        if "/" in raw:
            return raw
        return f"{provider_id}/{raw}"

    def _model_usage_pricing(self, provider_id: str, model_id: str) -> dict[str, Any]:
        configured_models = self._router_config.models() if self._router_config is not None else []
        native_model = str(model_id or "").split("/", 1)[1] if "/" in str(model_id or "") else str(model_id or "")
        return dict(effective_model_record(provider_id, native_model, configured_models) or {})

    def apply_temperature_config(self, profile: dict[str, Any], upstream_payload: dict[str, Any], model_id: Any) -> None:
        if "temperature" not in upstream_payload:
            return
        value = _optional_float(upstream_payload.get("temperature"))
        if value is None:
            upstream_payload.pop("temperature", None)
            return
        policy = self._temperature_policy(profile, model_id)
        if policy == "qwen_omit_zero_clamp_1":
            if value <= 0:
                upstream_payload.pop("temperature", None)
                return
            upstream_payload["temperature"] = min(max(value, 0.00001), 1.0)
            return
        if policy == "kimi_only_temperature_1":
            if abs(value - 1.0) > 0.000001:
                upstream_payload.pop("temperature", None)
                return
            upstream_payload["temperature"] = 1.0
            return
        upstream_payload["temperature"] = min(max(value, 0.0), 2.0)

    def temperature_warnings(self, profile: dict[str, Any], model_id: Any, temperature: Any) -> list[str]:
        value = _optional_float(temperature)
        if value is None:
            return []
        policy = self._temperature_policy(profile, model_id)
        if policy == "qwen_omit_zero_clamp_1":
            if value <= 0:
                return ["Qwen/DashScope compatible mode uses (0, 1.0] for temperature; 0 is omitted from upstream payload."]
            if value > 1:
                return ["Qwen/DashScope compatible mode caps temperature at 1.0; UI value was clamped for upstream."]
        if policy == "kimi_only_temperature_1":
            if abs(value - 1.0) > 0.000001:
                return ["Kimi K2 models only accept temperature=1; this UI value is omitted from the upstream payload."]
        if value < 0 or value > 2:
            return ["Temperature was clamped to the OpenAI-compatible 0-2 range."]
        return []

    def _temperature_policy(self, profile: dict[str, Any], model_id: Any) -> str:
        configured_models = self._router_config.models() if self._router_config is not None else []
        for item in configured_models:
            if str(item.get("id") or "") == str(model_id or ""):
                policy = str(item.get("temperature_adapter_policy") or "").strip()
                if policy:
                    return policy
        provider_family = _provider_family(
            profile.get("adapter_profile"),
            provider_family=profile.get("provider_family"),
            source_provider_id=profile.get("provider_id"),
            base_url=profile.get("base_url"),
            model=str(profile.get("model") or ""),
        )
        if provider_family:
            try:
                return get_provider_profile(provider_family).safety_policy.temperature_adapter_policy
            except ValueError:
                pass
        return "pass_through_0_2"

    def _request_upstream(self, *, parsed: urllib.parse.ParseResult, payload: dict[str, Any], bearer: str, stream: bool) -> http.client.HTTPResponse:
        if parsed.scheme not in {"http", "https"}:
            raise RuntimeError(f"Unsupported upstream scheme: {parsed.scheme}")
        headers = {
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = http.client.HTTPSConnection(parsed.hostname, port, timeout=300, context=ssl.create_default_context())
        else:
            connection = http.client.HTTPConnection(parsed.hostname, port, timeout=300)
        target = parsed.path or "/responses"
        if parsed.query:
            target += f"?{parsed.query}"
        connection.request("POST", target, body=body, headers=headers)
        return connection.getresponse()

    def _should_retry_provider_error(self, profile: dict[str, Any], status: int, text: str, attempt: int) -> bool:
        if attempt >= 2:
            return False
        provider = str(profile.get("provider_id") or "").lower()
        code = (self._provider_error_code(text) or "").lower()
        message = text.lower()
        if status in {502, 503, 504}:
            return True
        if status == 429 and ("overloaded" in message or code in {"engine_overloaded_error", "rate_limit_error"}):
            return True
        return "kimi" in provider and status == 429 and "engine_overloaded" in message

    def _provider_error_code(self, text: str) -> str | None:
        try:
            payload = json.loads(text)
            error = dict(payload.get("error") or payload)
            code = error.get("code") or error.get("type")
            return str(code) if code else None
        except Exception:
            return None

    def _port_in_use(self, port: int | None = None) -> bool:
        probe_port = int(port or self._port or 0)
        if probe_port <= 0:
            return False
        host = "127.0.0.1" if self._host in {"", "0.0.0.0"} else self._host
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex((host, probe_port)) == 0

    def _record(self, kind: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._events.append({"kind": kind, **payload})

    def _normalize_provider_error(self, profile: dict[str, Any], status: int, text: str) -> dict[str, Any]:
        native_code = None
        message = text.strip() or "Provider rejected request."
        try:
            payload = json.loads(text)
            error = dict(payload.get("error") or payload)
            native_code = error.get("code") or error.get("type")
            message = str(error.get("message") or message)
        except Exception:
            pass
        notice = self._failure_notice_payload(
            message if message == text.strip() else text,
            provider_id=str(profile.get("provider_id") or ""),
            model_id=str(profile.get("model") or ""),
            native_status=status,
            native_code=str(native_code or "").strip() or None,
        )
        context_hint = self._provider_error_hint(message, fallback="")
        if context_hint:
            notice["actionable_hint"] = context_hint
        return {"error": notice}

    def _provider_and_model_from_payload(self, payload: dict[str, Any]) -> tuple[str, str]:
        model_text = str(payload.get("model") or "").strip()
        provider = ""
        model = model_text
        if "/" in model_text:
            provider, model = model_text.split("/", 1)
        if not provider:
            try:
                profile = self._resolve_profile(payload)
            except Exception:
                return "", model_text
            provider = str(profile.get("provider_id") or "").strip()
            model = str(profile.get("model") or model or "").strip()
        normalized_model = f"{provider}/{model}" if provider and model and "/" not in model else (model_text or model)
        return provider, normalized_model

    def _failure_notice_payload(
        self,
        raw_message: str,
        *,
        provider_id: str,
        model_id: str,
        native_status: int | None = None,
        native_code: str | None = None,
    ) -> dict[str, Any]:
        parsed_error: dict[str, Any] | None = None
        try:
            parsed = json.loads(str(raw_message or ""))
            if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
                parsed_error = dict(parsed.get("error") or {})
        except Exception:
            parsed_error = None
        notice = (
            parsed_error
            if parsed_error and parsed_error.get("category") and parsed_error.get("actionable_hint")
            else classify_runtime_failure(
                str(raw_message or ""),
                current_provider=provider_id or None,
                current_model=model_id or None,
            ).to_payload()
        )
        payload = redact_sensitive(dict(notice or {}))
        payload.setdefault("type", "provider_error")
        payload.setdefault("provider", provider_id or payload.get("provider") or "")
        payload.setdefault("model", model_id or payload.get("model") or "")
        if native_status is not None and payload.get("native_status") is None:
            payload["native_status"] = native_status
        if native_code and payload.get("native_code") is None:
            payload["native_code"] = native_code
        if not str(payload.get("actionable_hint") or "").strip():
            payload["actionable_hint"] = self._provider_error_hint(
                str(payload.get("message") or raw_message or ""),
                fallback="Check provider auth, request shape, router state, or upstream connectivity.",
            )
        return payload

    @staticmethod
    def _failure_excerpt(failure_notice: dict[str, Any], *, fallback: str) -> str:
        summary = str(failure_notice.get("summary") or "").strip()
        hint = str(failure_notice.get("actionable_hint") or "").strip()
        message = str(failure_notice.get("message") or "").strip()
        text = " ".join(part for part in [summary, hint] if part).strip() or message or fallback
        return text[:1200]

    @staticmethod
    def _provider_error_hint(message: str, *, fallback: str) -> str:
        lowered = str(message or "").lower()
        context_markers = (
            "context",
            "maximum context",
            "context length",
            "context window",
            "tokens exceeded",
            "too many tokens",
            "maximum tokens",
            "input too long",
        )
        if any(marker in lowered for marker in context_markers):
            return "The provider hit a context limit. Reduce history or attachments; the router does not truncate automatically."
        return fallback

    def _error_context_for_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_text = str(payload.get("model") or "")
        provider = ""
        model = model_text
        if "/" in model_text:
            provider, model = model_text.split("/", 1)
        if not provider:
            try:
                profile = self._resolve_profile(payload)
                provider = str(profile.get("provider_id") or "")
                model = str(profile.get("model") or model)
            except Exception:
                pass
        return redact_sensitive({"provider": provider or None, "model": model or None})

    def _stream_chat_completion(self, adapter: RegistryProviderTransport, response: http.client.HTTPResponse, original_payload: dict[str, Any], handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(response.status)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        response_id = f"resp_router_{int(time.time())}"
        message_item = {"id": "msg_stream", "type": "message", "role": "assistant", "status": "in_progress", "content": []}
        self._write_sse(handler, {"type": "response.created", "response": {"id": response_id, "object": "response", "status": "in_progress"}})
        self._write_sse(handler, {"type": "response.output_item.added", "output_index": 0, "item": message_item})
        self._write_sse(
            handler,
            {
                "type": "response.content_part.added",
                "item_id": "msg_stream",
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": ""},
            },
        )
        partial_text = []
        partial_reasoning = []
        reasoning_stream_started = False
        partial_tool_calls: dict[int, dict[str, Any]] = {}
        stream_usage: dict[str, Any] = {}
        pending_lines = ""
        for chunk in iter(lambda: response.read(4096), b""):
            pending_lines += chunk.decode("utf-8", errors="replace")
            while "\n" in pending_lines:
                line, pending_lines = pending_lines.split("\n", 1)
                stripped = line.strip()
                if not stripped.startswith("data:"):
                    continue
                data = stripped[5:].strip()
                if data == "[DONE]":
                    continue
                try:
                    event = json.loads(data)
                except Exception:
                    continue
                if isinstance(event.get("usage"), dict):
                    stream_usage = dict(event.get("usage") or {})
                choices = list(event.get("choices") or [])
                if not choices:
                    continue
                delta = dict(choices[0].get("delta") or {})
                content = delta.get("content")
                reasoning_content = delta.get("reasoning_content")
                for call_delta in list(delta.get("tool_calls") or []):
                    if not isinstance(call_delta, dict):
                        continue
                    index = int(call_delta.get("index") if call_delta.get("index") is not None else len(partial_tool_calls))
                    call = partial_tool_calls.setdefault(index, {"id": f"call_stream_{index}", "type": "function", "function": {"name": "", "arguments": ""}})
                    if call_delta.get("id"):
                        call["id"] = str(call_delta.get("id"))
                    function_delta = dict(call_delta.get("function") or {})
                    function = dict(call.get("function") or {})
                    if function_delta.get("name"):
                        function["name"] = str(function_delta.get("name"))
                    if function_delta.get("arguments"):
                        function["arguments"] = str(function.get("arguments") or "") + str(function_delta.get("arguments"))
                    call["function"] = function
                if reasoning_content:
                    if not reasoning_stream_started:
                        reasoning_stream_started = True
                        self._write_sse(
                            handler,
                            {
                                "type": "response.output_item.added",
                                "output_index": 1,
                                "item": {
                                    "id": "reasoning_stream",
                                    "type": "reasoning",
                                    "summary": [],
                                    "content": [],
                                    "status": "in_progress",
                                },
                            },
                        )
                    self._write_sse(
                        handler,
                        {
                            "type": "response.reasoning_text.delta",
                            "item_id": "reasoning_stream",
                            "output_index": 1,
                            "delta": str(reasoning_content),
                        },
                    )
                    partial_reasoning.append(str(reasoning_content))
                if content:
                    partial_text.append(str(content))
                    self._write_sse(handler, {"type": "response.output_text.delta", "item_id": "msg_stream", "output_index": 0, "content_index": 0, "delta": str(content)})
        text = "".join(partial_text)
        if isinstance(adapter, RegistryChatCompletionsTransport):
            text = adapter._visible_text_or_reasoning_only_notice(text, "".join(partial_reasoning), bool(partial_tool_calls))
            if text and not partial_text and partial_reasoning and not partial_tool_calls:
                self._write_sse(handler, {"type": "response.output_text.delta", "item_id": "msg_stream", "output_index": 0, "content_index": 0, "delta": text})
        self._write_sse(handler, {"type": "response.output_text.done", "item_id": "msg_stream", "output_index": 0, "content_index": 0, "text": text})
        self._write_sse(
            handler,
            {
                "type": "response.content_part.done",
                "item_id": "msg_stream",
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": text},
            },
        )
        output = []
        message_done_item = {"id": "msg_stream", "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}], "status": "completed"}
        output.append(message_done_item)
        self._write_sse(handler, {"type": "response.output_item.done", "output_index": 0, "item": message_done_item})
        if partial_reasoning:
            reasoning_item = {"id": "reasoning_stream", "type": "reasoning", "summary": ["".join(partial_reasoning)], "content": ["".join(partial_reasoning)]}
            reasoning_index = len(output)
            output.append(reasoning_item)
            if not reasoning_stream_started:
                self._write_sse(handler, {"type": "response.output_item.added", "output_index": reasoning_index, "item": reasoning_item})
            self._write_sse(handler, {"type": "response.output_item.done", "output_index": reasoning_index, "item": reasoning_item})
        for index, call in sorted(partial_tool_calls.items()):
            function = dict(call.get("function") or {})
            call_id = str(call.get("id") or f"call_stream_{index}")
            tool_item = {
                "id": f"fc_{call_id}",
                "type": "function_call",
                "call_id": call_id,
                "name": function.get("name") or "tool",
                "arguments": adapter._safe_tool_arguments(function.get("arguments")) if isinstance(adapter, RegistryChatCompletionsTransport) else str(function.get("arguments") or "{}"),
                "status": "completed",
            }
            output_index = len(output)
            output.append(tool_item)
            self._write_sse(handler, {"type": "response.output_item.added", "output_index": output_index, "item": tool_item})
            self._write_sse(handler, {"type": "response.output_item.done", "output_index": output_index, "item": tool_item})
        final_response = {
            "id": response_id,
            "object": "response",
            "status": "completed",
            "model": original_payload.get("model"),
            "output": output,
            "output_text": text,
        }
        if stream_usage and isinstance(adapter, RegistryChatCompletionsTransport):
            final_response["usage"] = adapter._response_usage_from_chat_usage(stream_usage)
        self._write_sse(handler, {"type": "response.completed", "response": final_response})
        handler.wfile.write(b"data: [DONE]\n\n")
        handler.wfile.flush()

    def _write_sse(self, handler: BaseHTTPRequestHandler, event: dict[str, Any]) -> None:
        handler.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
        handler.wfile.flush()


def _fallback_context_window(profile: dict[str, Any]) -> int | None:
    provider = _provider_family(
        profile.get("adapter_profile"),
        provider_family=profile.get("provider_family"),
        source_provider_id=profile.get("provider_id"),
        base_url=profile.get("base_url"),
        model=profile.get("model"),
    )
    model = str(profile.get("model") or "")
    return known_context_window(provider, model) if provider else None


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _vision_probe_red_square_data_uri() -> str:
    """Return a deterministic, dependency-free PNG fixture for live vision probes."""
    width = height = 96
    scanline = b"\x00" + (b"\xff\x00\x00\xff" * width)
    raw = scanline * height

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _contains_non_data_image_reference(value: Any) -> bool:
    if isinstance(value, dict):
        item_type = str(value.get("type") or "")
        if item_type in {"input_image", "image_url"}:
            image_url = value.get("image_url")
            if isinstance(image_url, dict):
                candidate = str(image_url.get("url") or value.get("url") or "").strip()
            else:
                candidate = str(image_url or value.get("url") or "").strip()
            return bool(candidate) and not candidate.startswith("data:image/")
        return any(_contains_non_data_image_reference(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_non_data_image_reference(item) for item in value)
    return False


def _provider_family(
    seed: Any,
    *,
    adapter_profile: Any = None,
    provider_family: Any = None,
    source_provider_id: Any = None,
    base_url: Any = None,
    model: Any = None,
) -> str | None:
    candidates = (seed, provider_family, adapter_profile, source_provider_id, base_url, model)
    for candidate in candidates:
        try:
            return resolve_provider_id(str(candidate or "").strip())
        except ValueError:
            continue
    return None


def _profile_priority(profile: dict[str, Any]) -> int:
    profile_id = str(profile.get("profile_id") or "")
    provider_id = str(profile.get("provider_id") or "")
    default_profile_id = "openai-compatible" if provider_id == "openai" else f"{provider_id}-default"
    return 1 if profile_id == default_profile_id else 0


class _BufferHandler:
    def __init__(self) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.body = b""
        self.wfile = BytesIO()

    def send_response(self, status_code: int) -> None:
        self.status_code = status_code

    def send_header(self, key: str, value: str) -> None:
        self.headers[key] = value

    def end_headers(self) -> None:
        return

