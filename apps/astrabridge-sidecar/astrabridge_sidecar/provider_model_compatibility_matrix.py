from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from .security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, SecurityError


PROVIDER_MODEL_COMPATIBILITY_MATRIX_SCHEMA_VERSION = "astrabridge-provider-model-compatibility-matrix-v1"
ENTRY_SECTION_NAMES = ("declared_capability", "runtime_normalized_contract", "validated_evidence")
ENTRY_KINDS = ("provider", "model")
OVERALL_STATUSES = ("verified", "partial", "blocked", "unknown")
VALIDATION_STATUSES = ("pass", "warn", "fail", "partial", "skipped", "blocked", "unknown")
FORBIDDEN_FIELD_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "access_token",
    "refresh_token",
    "session_token",
    "bearer_token",
    "vault_password",
    "admin_session_token",
    "provider_secret",
    "raw_secret",
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+[a-z0-9._-]{12,}|cookie\s*:|ssh-rsa|BEGIN\s+(RSA|OPENSSH|EC|DSA)\s+PRIVATE\s+KEY)"
)


def compatibility_matrix_entry_template(*, entry_kind: str = "model") -> dict[str, Any]:
    if entry_kind not in ENTRY_KINDS:
        raise ValueError(f"Unsupported compatibility entry kind: {entry_kind}")
    entry = deepcopy(_ENTRY_TEMPLATE)
    entry["entry_kind"] = entry_kind
    return entry


def empty_provider_model_compatibility_matrix() -> dict[str, Any]:
    return {
        "schema_version": PROVIDER_MODEL_COMPATIBILITY_MATRIX_SCHEMA_VERSION,
        "generated_at": None,
        "matrix_id": None,
        "matrix_scope": {
            "source_kind": "unknown",
            "managed_session_mode": None,
            "managed_username": None,
            "registry_provider_ids": [],
            "effective_provider_ids": [],
            "web_lane_policy": "standalone",
        },
        "status_definitions": {
            "overall_statuses": list(OVERALL_STATUSES),
            "validation_statuses": list(VALIDATION_STATUSES),
        },
        "entry_section_names": list(ENTRY_SECTION_NAMES),
        "entries": [],
        "evidence_index": {
            "source_files": [],
            "runtime_sources": [],
            "artifact_paths": [],
        },
        "redaction_rules": {
            "secret_free": True,
            "forbidden_field_markers": list(FORBIDDEN_FIELD_MARKERS),
            "notes": [
                "Store paths, summaries, usage signals, and evidence references only.",
                "Do not embed raw provider requests, raw provider responses, auth headers, cookies, or reusable secrets.",
            ],
        },
    }


def assert_secret_free_provider_model_compatibility_matrix(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise TypeError("Compatibility matrix payload must be a dict.")
    if str(payload.get("schema_version") or "") != PROVIDER_MODEL_COMPATIBILITY_MATRIX_SCHEMA_VERSION:
        raise ValueError("Unexpected provider/model compatibility matrix schema version.")
    for key in ("matrix_scope", "entries", "evidence_index"):
        if key not in payload:
            raise ValueError(f"Compatibility matrix is missing top-level field: {key}")
    _reject_secret_like(payload, path="matrix")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Compatibility matrix entries must be a list.")
    for index, entry in enumerate(entries):
        _validate_entry(entry, index=index)


def _validate_entry(entry: Any, *, index: int) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"Compatibility matrix entry {index} must be a dict.")
    if str(entry.get("entry_kind") or "") not in ENTRY_KINDS:
        raise ValueError(f"Compatibility matrix entry {index} has invalid entry_kind.")
    if str(entry.get("overall_status") or "") not in OVERALL_STATUSES:
        raise ValueError(f"Compatibility matrix entry {index} has invalid overall_status.")
    for section in ENTRY_SECTION_NAMES:
        if section not in entry or not isinstance(entry.get(section), dict):
            raise ValueError(f"Compatibility matrix entry {index} is missing section {section}.")
    validation = dict(entry.get("validated_evidence") or {})
    validation_status = str(validation.get("validation_status") or "")
    if validation_status and validation_status not in VALIDATION_STATUSES:
        raise ValueError(f"Compatibility matrix entry {index} has invalid validation_status.")


def _reject_secret_like(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered == "secret" or any(marker in lowered for marker in FORBIDDEN_FIELD_MARKERS):
                raise SecurityError(f"Forbidden secret-bearing field in compatibility matrix: {path}.{key}")
            _reject_secret_like(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_like(item, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if value.startswith("data:image/"):
        raise SecurityError(f"Inline image data is not allowed in compatibility matrix payloads: {path}")
    if DESKTOP_KEY_PATH_RE.search(value):
        raise SecurityError(f"Desktop key path is not allowed in compatibility matrix payloads: {path}")
    if SECRET_QUERY_RE.search(value) or SECRET_VALUE_RE.search(value):
        raise SecurityError(f"Secret-like value is not allowed in compatibility matrix payloads: {path}")


_ENTRY_TEMPLATE: dict[str, Any] = {
    "entry_id": None,
    "entry_kind": "model",
    "provider_id": None,
    "model_id": None,
    "display_name": None,
    "declared_capability": {
        "source_of_truth": [],
        "protocol": None,
        "reasoning_mode": None,
        "default_model": None,
        "input_modalities": [],
        "edit_policy": {},
        "tool_policy": {},
        "context_policy": {},
        "fallback_policy": {},
    },
    "runtime_normalized_contract": {
        "source_of_truth": [],
        "managed_key_available": None,
        "effective_default_model": None,
        "codex_runtime_metadata": {},
        "capability_metadata": {},
        "reasoning_state": {},
        "context_window": {},
        "authority": {},
        "contract_warnings": [],
    },
    "validated_evidence": {
        "validation_status": "unknown",
        "health_status": "unknown",
        "validation_scope": [],
        "evidence_paths": [],
        "last_verified_at": None,
        "usage_signals": {},
        "known_failures": [],
        "known_pitfalls": [],
        "notes": [],
    },
    "overall_status": "unknown",
    "warnings": [],
}
