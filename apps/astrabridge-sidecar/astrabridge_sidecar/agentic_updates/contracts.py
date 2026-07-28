from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from ..common import new_id, now_iso
from ..security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, SECRET_RE, SecurityError
from .route_promotion import normalize_route_promotion_section, route_promotion_section_template


AGENTIC_UPDATE_CONTRACT_SCHEMA_VERSION = "astrabridge-agentic-update-contract-v1"
AGENTIC_UPDATE_PROPOSAL_SCHEMA_VERSION = "astrabridge-agentic-update-proposal-v1"
AGENTIC_UPDATE_SCHEMA_DEFINITIONS_VERSION = "astrabridge-agentic-update-schema-definitions-v1"

UPDATE_SCOPES = (
    "provider_metadata",
    "provider_adapter",
    "execution_routes",
    "capability_routes",
    "codex_kernel",
    "plugin_skill_surface",
    "docs_only",
)
VERSION_POLICIES = ("pinned", "stable", "latest", "deprecated_check", "security_fix_only")
APPLY_MODES = ("discover_only", "proposal_only", "isolated_apply", "verify_candidate", "promote_after_smoke")
APPROVAL_POLICIES = ("manual_review_required", "preapproved_discovery_only")
VALIDATION_STATUSES = ("not_run", "pass", "warn", "fail", "partial", "skipped", "blocked")
APPROVAL_STATUSES = ("not_requested", "pending_manual_review", "approved", "rejected")

FORBIDDEN_SECRET_FIELD_MARKERS = (
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
FORBIDDEN_RAW_PAYLOAD_FIELD_MARKERS = (
    "raw_request",
    "raw_response",
    "raw_provider_request",
    "raw_provider_response",
    "raw_external_payload",
    "request_headers",
    "response_headers",
    "authorization_header",
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)("
    r"authorization\s*:|"
    r"bearer\s+[a-z0-9._~+/=-]{12,}|"
    r"cookie\s*:|"
    r"api[_-]?key\s*[:=]\s*\S+|"
    r"secret[_-]?(key|token)?\s*[:=]\s*\S+|"
    r"token\s*[:=]\s*\S+|"
    r"sk-[a-z0-9]{20,}|"
    r"xox[baprs]-[a-z0-9-]{20,}|"
    r"AIza[0-9A-Za-z_\-]{20,}|"
    r"ssh-rsa|"
    r"BEGIN\s+(RSA|OPENSSH|EC|DSA)\s+PRIVATE\s+KEY"
    r")"
)


def normalize_update_scope_contract(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("Agentic update contract payload must be a dict.")
    assert_secret_free_agentic_update_payload(payload, label="agentic_update_contract")

    scopes = _normalize_string_list(payload.get("scope"), field="scope", required=True)
    invalid_scopes = sorted(set(scopes).difference(UPDATE_SCOPES))
    if invalid_scopes:
        raise ValueError(f"Unsupported agentic update scope: {', '.join(invalid_scopes)}")

    version_policy = _normalize_enum(payload.get("version_policy") or "stable", field="version_policy", allowed=VERSION_POLICIES)
    target_version = _optional_string(payload.get("target_version"), field="target_version")
    if version_policy == "pinned" and not target_version:
        raise ValueError("target_version is required when version_policy is pinned.")

    apply_mode = _normalize_enum(payload.get("apply_mode") or "proposal_only", field="apply_mode", allowed=APPLY_MODES)
    approval_policy = _normalize_enum(
        payload.get("approval_policy") or "manual_review_required",
        field="approval_policy",
        allowed=APPROVAL_POLICIES,
    )
    normalized = {
        "schema_version": AGENTIC_UPDATE_CONTRACT_SCHEMA_VERSION,
        "normalized_at": now_iso(),
        "scope": scopes,
        "providers": _normalize_string_list(payload.get("providers"), field="providers"),
        "models": _normalize_string_list(payload.get("models"), field="models"),
        "version_policy": version_policy,
        "target_version": target_version,
        "apply_mode": apply_mode,
        "allow_network": _optional_bool(payload.get("allow_network"), default=True, field="allow_network"),
        "allow_provider_calls": _optional_bool(payload.get("allow_provider_calls"), default=False, field="allow_provider_calls"),
        "allow_install": _optional_bool(payload.get("allow_install"), default=False, field="allow_install"),
        "allow_code_changes": _optional_bool(payload.get("allow_code_changes"), default=False, field="allow_code_changes"),
        "approval_policy": approval_policy,
    }
    _validate_authorization_boundary(normalized)
    assert_secret_free_agentic_update_payload(normalized, label="agentic_update_contract")
    return normalized


def agentic_update_schema_definitions() -> dict[str, Any]:
    return {
        "schema_version": AGENTIC_UPDATE_SCHEMA_DEFINITIONS_VERSION,
        "generated_at": now_iso(),
        "contract_versions": {
            "normalized_scope_contract": AGENTIC_UPDATE_CONTRACT_SCHEMA_VERSION,
            "proposal": AGENTIC_UPDATE_PROPOSAL_SCHEMA_VERSION,
        },
        "definitions": {
            "update_request": {
                "type": "object",
                "required": ["scope"],
                "fields": _scope_contract_fields(include_runtime_fields=False),
                "defaults": {
                    "version_policy": "stable",
                    "apply_mode": "proposal_only",
                    "allow_network": True,
                    "allow_provider_calls": False,
                    "allow_install": False,
                    "allow_code_changes": False,
                    "approval_policy": "manual_review_required",
                },
            },
            "normalized_scope_contract": {
                "type": "object",
                "schema_version": AGENTIC_UPDATE_CONTRACT_SCHEMA_VERSION,
                "required": ["schema_version", "normalized_at", "scope", "version_policy", "apply_mode"],
                "fields": _scope_contract_fields(include_runtime_fields=True),
            },
            "discovery_result": {
                "type": "object",
                "required": ["schema_version", "sources", "findings"],
                "notes": ["Source records store URLs, hashes, timestamps, short excerpts, and trust labels only."],
            },
            "diff": {
                "type": "object",
                "required": ["schema_version", "status", "changes"],
                "notes": ["Diff records describe proposed changes; they do not apply them."],
            },
            "validation_result": {
                "type": "object",
                "required": ["schema_version", "status", "gates"],
                "allowed_statuses": list(VALIDATION_STATUSES),
            },
            "approval_state": {
                "type": "object",
                "required": ["schema_version", "status", "policy"],
                "allowed_statuses": list(APPROVAL_STATUSES),
                "allowed_policies": list(APPROVAL_POLICIES),
            },
            "apply_manifest": {
                "type": "object",
                "required": ["schema_version", "mode", "changed_paths"],
                "notes": ["changed_paths must be empty unless the contract allows code or config changes."],
            },
            "rollback_manifest": {
                "type": "object",
                "required": ["schema_version", "reversible", "steps"],
                "notes": ["Rollback instructions must be reviewable and must not delete preserved evidence."],
            },
            "route_promotion": {
                "type": "object",
                "required": ["schema_version", "status", "records"],
                "notes": [
                    "Documentation records are not route proof; each promotion binds one model, endpoint fingerprint, and adapter signature.",
                    "Provider-backed gate evidence is required before tool, coding-route, or default-route promotion."
                ],
            },
            "proposal": {
                "type": "object",
                "schema_version": AGENTIC_UPDATE_PROPOSAL_SCHEMA_VERSION,
                "required": [
                    "schema_version",
                    "run_id",
                    "run_contract",
                    "discovery_result",
                    "diff",
                    "validation_result",
                    "approval_state",
                    "apply_manifest",
                    "rollback_manifest",
                ],
            },
        },
        "redaction_rules": {
            "forbidden_secret_field_markers": list(FORBIDDEN_SECRET_FIELD_MARKERS),
            "forbidden_raw_payload_field_markers": list(FORBIDDEN_RAW_PAYLOAD_FIELD_MARKERS),
            "inline_media_data_allowed": False,
            "desktop_key_paths_allowed": False,
        },
    }


def agentic_update_proposal_template(
    run_contract: dict[str, Any],
    *,
    run_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    contract = normalize_update_scope_contract(run_contract)
    now = created_at or now_iso()
    proposal = {
        "schema_version": AGENTIC_UPDATE_PROPOSAL_SCHEMA_VERSION,
        "run_id": run_id or new_id("agentic-update"),
        "created_at": now,
        "run_contract": contract,
        "discovery_result": {
            "schema_version": "astrabridge-agentic-update-discovery-result-v1",
            "generated_at": now,
            "mode": "fixture" if not contract["allow_network"] else "pending",
            "sources": [],
            "findings": [],
            "warnings": [],
        },
        "diff": {
            "schema_version": "astrabridge-agentic-update-diff-v1",
            "status": "not_generated",
            "changes": [],
            "warnings": [],
        },
        "validation_result": {
            "schema_version": "astrabridge-agentic-update-validation-result-v1",
            "status": "not_run",
            "gates": [],
            "evidence_paths": [],
            "warnings": [],
        },
        "approval_state": {
            "schema_version": "astrabridge-agentic-update-approval-state-v1",
            "status": "pending_manual_review",
            "policy": contract["approval_policy"],
            "approved_by": None,
            "approved_at": None,
        },
        "apply_manifest": {
            "schema_version": "astrabridge-agentic-update-apply-manifest-v1",
            "mode": contract["apply_mode"],
            "changed_paths": [],
            "applied_at": None,
            "warnings": [],
        },
        "rollback_manifest": {
            "schema_version": "astrabridge-agentic-update-rollback-manifest-v1",
            "reversible": True,
            "steps": [],
            "evidence_paths": [],
            "warnings": [],
        },
        "route_promotion": route_promotion_section_template(generated_at=now),
    }
    return validate_update_proposal(proposal)


def validate_update_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        raise TypeError("Agentic update proposal must be a dict.")
    assert_secret_free_agentic_update_payload(proposal, label="agentic_update_proposal")
    if proposal.get("schema_version") != AGENTIC_UPDATE_PROPOSAL_SCHEMA_VERSION:
        raise ValueError("Unexpected agentic update proposal schema version.")
    for field in (
        "run_id",
        "run_contract",
        "discovery_result",
        "diff",
        "validation_result",
        "approval_state",
        "apply_manifest",
        "rollback_manifest",
    ):
        if field not in proposal:
            raise ValueError(f"Agentic update proposal is missing required field: {field}")

    normalized = deepcopy(proposal)
    normalized["run_contract"] = normalize_update_scope_contract(dict(proposal["run_contract"]))
    normalized["route_promotion"] = normalize_route_promotion_section(
        dict(proposal.get("route_promotion") or {}),
    )
    _validate_discovery_result(normalized["discovery_result"])
    _validate_diff(normalized["diff"])
    _validate_validation_result(normalized["validation_result"])
    _validate_approval_state(normalized["approval_state"], normalized["run_contract"])
    _validate_apply_manifest(normalized["apply_manifest"], normalized["run_contract"])
    _validate_rollback_manifest(normalized["rollback_manifest"])
    assert_secret_free_agentic_update_payload(normalized, label="agentic_update_proposal")
    return normalized


def assert_secret_free_agentic_update_payload(payload: Any, *, label: str = "agentic_update") -> None:
    _reject_secret_like(payload, path=label)


def _validate_authorization_boundary(contract: dict[str, Any]) -> None:
    scopes = set(contract["scope"])
    apply_mode = contract["apply_mode"]
    if contract["allow_provider_calls"]:
        if not contract["allow_network"]:
            raise ValueError("allow_provider_calls requires allow_network.")
        if apply_mode not in {"verify_candidate", "promote_after_smoke"}:
            raise ValueError("allow_provider_calls is only allowed for verify_candidate or promote_after_smoke.")
    if contract["allow_install"]:
        if scopes.isdisjoint({"codex_kernel", "plugin_skill_surface"}):
            raise ValueError("allow_install is only allowed for codex_kernel or plugin_skill_surface scopes.")
        if apply_mode not in {"isolated_apply", "verify_candidate", "promote_after_smoke"}:
            raise ValueError("allow_install requires isolated_apply, verify_candidate, or promote_after_smoke.")
    if contract["allow_code_changes"]:
        if apply_mode not in {"isolated_apply", "verify_candidate", "promote_after_smoke"}:
            raise ValueError("allow_code_changes requires isolated_apply, verify_candidate, or promote_after_smoke.")
        if contract["approval_policy"] != "manual_review_required":
            raise ValueError("allow_code_changes requires manual_review_required approval.")
    if apply_mode == "promote_after_smoke" and contract["approval_policy"] != "manual_review_required":
        raise ValueError("promote_after_smoke requires manual_review_required approval.")


def _validate_discovery_result(value: Any) -> None:
    data = _ensure_section_dict(value, "discovery_result")
    _require_section_fields(data, "discovery_result", ("schema_version", "sources", "findings"))
    if not isinstance(data["sources"], list):
        raise ValueError("discovery_result.sources must be a list.")
    if not isinstance(data["findings"], list):
        raise ValueError("discovery_result.findings must be a list.")


def _validate_diff(value: Any) -> None:
    data = _ensure_section_dict(value, "diff")
    _require_section_fields(data, "diff", ("schema_version", "status", "changes"))
    if not isinstance(data["changes"], list):
        raise ValueError("diff.changes must be a list.")


def _validate_validation_result(value: Any) -> None:
    data = _ensure_section_dict(value, "validation_result")
    _require_section_fields(data, "validation_result", ("schema_version", "status", "gates"))
    if str(data["status"]) not in VALIDATION_STATUSES:
        raise ValueError("validation_result.status is invalid.")
    if not isinstance(data["gates"], list):
        raise ValueError("validation_result.gates must be a list.")


def _validate_approval_state(value: Any, contract: dict[str, Any]) -> None:
    data = _ensure_section_dict(value, "approval_state")
    _require_section_fields(data, "approval_state", ("schema_version", "status", "policy"))
    if str(data["status"]) not in APPROVAL_STATUSES:
        raise ValueError("approval_state.status is invalid.")
    if str(data["policy"]) not in APPROVAL_POLICIES:
        raise ValueError("approval_state.policy is invalid.")
    if data["policy"] != contract["approval_policy"]:
        raise ValueError("approval_state.policy must match run_contract.approval_policy.")


def _validate_apply_manifest(value: Any, contract: dict[str, Any]) -> None:
    data = _ensure_section_dict(value, "apply_manifest")
    _require_section_fields(data, "apply_manifest", ("schema_version", "mode", "changed_paths"))
    if str(data["mode"]) != contract["apply_mode"]:
        raise ValueError("apply_manifest.mode must match run_contract.apply_mode.")
    changed_paths = data["changed_paths"]
    if not isinstance(changed_paths, list):
        raise ValueError("apply_manifest.changed_paths must be a list.")
    if changed_paths and not contract["allow_code_changes"]:
        raise ValueError("apply_manifest.changed_paths requires allow_code_changes.")


def _validate_rollback_manifest(value: Any) -> None:
    data = _ensure_section_dict(value, "rollback_manifest")
    _require_section_fields(data, "rollback_manifest", ("schema_version", "reversible", "steps"))
    if not isinstance(data["reversible"], bool):
        raise ValueError("rollback_manifest.reversible must be a bool.")
    if not isinstance(data["steps"], list):
        raise ValueError("rollback_manifest.steps must be a list.")


def _ensure_section_dict(value: Any, section: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{section} must be a dict.")
    return value


def _require_section_fields(data: dict[str, Any], section: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if field not in data:
            raise ValueError(f"{section} is missing required field: {field}")


def _scope_contract_fields(*, include_runtime_fields: bool) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "scope": {"type": "string_or_string_array", "allowed": list(UPDATE_SCOPES)},
        "providers": {"type": "string_array", "required": False},
        "models": {"type": "string_array", "required": False},
        "version_policy": {"type": "string", "allowed": list(VERSION_POLICIES)},
        "target_version": {"type": "string", "required_when": {"version_policy": "pinned"}},
        "apply_mode": {"type": "string", "allowed": list(APPLY_MODES)},
        "allow_network": {"type": "boolean"},
        "allow_provider_calls": {"type": "boolean"},
        "allow_install": {"type": "boolean"},
        "allow_code_changes": {"type": "boolean"},
        "approval_policy": {"type": "string", "allowed": list(APPROVAL_POLICIES)},
    }
    if include_runtime_fields:
        fields = {
            "schema_version": {"const": AGENTIC_UPDATE_CONTRACT_SCHEMA_VERSION},
            "normalized_at": {"type": "iso8601_timestamp"},
            **fields,
        }
    return fields


def _normalize_string_list(value: Any, *, field: str, required: bool = False) -> list[str]:
    if value is None:
        if required:
            raise ValueError(f"{field} is required.")
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            raise TypeError(f"{field} entries must be strings.")
        text = item.strip()
        if not text:
            raise ValueError(f"{field} entries must not be empty.")
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    if required and not normalized:
        raise ValueError(f"{field} is required.")
    return normalized


def _normalize_enum(value: Any, *, field: str, allowed: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string.")
    text = value.strip()
    if text not in allowed:
        raise ValueError(f"Unsupported {field}: {text}")
    return text


def _optional_string(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string.")
    text = value.strip()
    return text or None


def _optional_bool(value: Any, *, default: bool, field: str) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a bool.")
    return value


def _reject_secret_like(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered == "secret" or any(marker in lowered for marker in FORBIDDEN_SECRET_FIELD_MARKERS):
                raise SecurityError(f"Forbidden secret-bearing field in agentic update payload: {path}.{key_text}")
            if any(marker in lowered for marker in FORBIDDEN_RAW_PAYLOAD_FIELD_MARKERS):
                raise SecurityError(f"Raw external payload field is not allowed in agentic update payload: {path}.{key_text}")
            _reject_secret_like(item, path=f"{path}.{key_text}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_like(item, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if value.startswith("data:image/") or value.startswith("data:audio/"):
        raise SecurityError(f"Inline media data is not allowed in agentic update payloads: {path}")
    if DESKTOP_KEY_PATH_RE.search(value):
        raise SecurityError(f"Desktop key path is not allowed in agentic update payloads: {path}")
    if SECRET_QUERY_RE.search(value) or SECRET_RE.search(value) or _SECRET_VALUE_RE.search(value):
        raise SecurityError(f"Secret-like value is not allowed in agentic update payloads: {path}")
