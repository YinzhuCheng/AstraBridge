from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any


EXTERNAL_A2A_CONFORMANCE_KIT_SCHEMA_VERSION = "astrabridge-external-a2a-conformance-kit-v1"


def build_external_a2a_conformance_kit(
    *,
    issuer: str = "trusted-geo",
    audience: str = "astrabridge-gateway",
    workspace_id: str = "workspace-demo",
    security_schemes: list[str] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    presented_security_schemes = list(security_schemes or ["mutualTlsSecurityScheme"])
    return {
        "schema_version": EXTERNAL_A2A_CONFORMANCE_KIT_SCHEMA_VERSION,
        "positive_case": {
            "task": _base_task("task-conformance-positive"),
            "metadata": {
                "external_a2a": {
                    "issuer": issuer,
                    "audience": audience,
                    "workspace_id": workspace_id,
                    "trust_level": "pinned",
                    "protocol_version": "1.0",
                    "supported_protocol_versions": ["1.0"],
                    "protocol_binding": "JSONRPC",
                    "supported_protocol_bindings": ["JSONRPC"],
                    "required_extensions": ["task-send", "task-stream"],
                    "optional_extensions": ["artifact-transfer"],
                    "security_schemes": presented_security_schemes,
                    "request_id": "req-positive",
                    "sent_at": now.isoformat(),
                    "expires_at": (now + timedelta(minutes=5)).isoformat(),
                }
            },
        },
        "negative_cases": [
            {
                "case_id": "expired_request",
                "expected_http_status": 409,
                "expected_code": "expired_request",
                "task": _base_task("task-expired"),
                "metadata": {
                    "external_a2a": {
                        "issuer": issuer,
                        "audience": audience,
                        "workspace_id": workspace_id,
                        "trust_level": "pinned",
                        "protocol_version": "1.0",
                        "supported_protocol_versions": ["1.0"],
                        "protocol_binding": "JSONRPC",
                        "supported_protocol_bindings": ["JSONRPC"],
                        "security_schemes": presented_security_schemes,
                        "request_id": "req-expired",
                        "sent_at": (now - timedelta(minutes=20)).isoformat(),
                        "expires_at": (now - timedelta(minutes=10)).isoformat(),
                    }
                },
            },
            {
                "case_id": "wrong_audience",
                "expected_http_status": 403,
                "expected_code": "wrong_audience",
                "task": _base_task("task-wrong-audience"),
                "metadata": {
                    "external_a2a": {
                        "issuer": issuer,
                        "audience": "another-gateway",
                        "workspace_id": workspace_id,
                        "trust_level": "pinned",
                        "protocol_version": "1.0",
                        "supported_protocol_versions": ["1.0"],
                        "protocol_binding": "JSONRPC",
                        "supported_protocol_bindings": ["JSONRPC"],
                        "security_schemes": presented_security_schemes,
                        "request_id": "req-wrong-audience",
                        "sent_at": now.isoformat(),
                    }
                },
            },
            {
                "case_id": "untrusted_peer",
                "expected_http_status": 403,
                "expected_code": "untrusted_peer",
                "task": _base_task("task-untrusted"),
                "metadata": {
                    "external_a2a": {
                        "issuer": "unknown-peer",
                        "audience": audience,
                        "workspace_id": workspace_id,
                        "trust_level": "workspace_trusted",
                        "protocol_version": "1.0",
                        "supported_protocol_versions": ["1.0"],
                        "protocol_binding": "JSONRPC",
                        "supported_protocol_bindings": ["JSONRPC"],
                        "security_schemes": presented_security_schemes,
                        "request_id": "req-untrusted",
                        "sent_at": now.isoformat(),
                    }
                },
            },
            {
                "case_id": "missing_security_scheme",
                "expected_http_status": 403,
                "expected_code": "missing_security_scheme",
                "task": _base_task("task-missing-security"),
                "metadata": {
                    "external_a2a": {
                        "issuer": issuer,
                        "audience": audience,
                        "workspace_id": workspace_id,
                        "trust_level": "pinned",
                        "protocol_version": "1.0",
                        "supported_protocol_versions": ["1.0"],
                        "protocol_binding": "JSONRPC",
                        "supported_protocol_bindings": ["JSONRPC"],
                        "security_schemes": ["noAuthSecurityScheme"],
                        "request_id": "req-missing-security",
                        "sent_at": now.isoformat(),
                    }
                },
            },
            {
                "case_id": "incompatible_protocol_version",
                "expected_http_status": 422,
                "expected_code": "incompatible_protocol_version",
                "task": _base_task("task-incompatible-version"),
                "metadata": {
                    "external_a2a": {
                        "issuer": issuer,
                        "audience": audience,
                        "workspace_id": workspace_id,
                        "trust_level": "pinned",
                        "protocol_version": "9.0",
                        "supported_protocol_versions": ["9.0"],
                        "protocol_binding": "JSONRPC",
                        "supported_protocol_bindings": ["JSONRPC"],
                        "security_schemes": presented_security_schemes,
                        "request_id": "req-incompatible-version",
                        "sent_at": now.isoformat(),
                    }
                },
            },
            {
                "case_id": "request_too_large",
                "expected_http_status": 413,
                "expected_code": "request_too_large",
                "task": {
                    "id": "task-oversized",
                    "input": [
                        {
                            "partId": "prompt",
                            "kind": "text",
                            "mimeType": "text/plain",
                            "text": "x" * (300 * 1024),
                        }
                    ],
                },
                "metadata": {
                    "external_a2a": {
                        "issuer": issuer,
                        "audience": audience,
                        "workspace_id": workspace_id,
                        "trust_level": "pinned",
                        "protocol_version": "1.0",
                        "supported_protocol_versions": ["1.0"],
                        "protocol_binding": "JSONRPC",
                        "supported_protocol_bindings": ["JSONRPC"],
                        "security_schemes": presented_security_schemes,
                        "request_id": "req-oversized",
                        "sent_at": now.isoformat(),
                    }
                },
            },
        ],
        "replay_case": {
            "initial": {
                "task": _base_task("task-replay-initial"),
                "metadata": {
                    "external_a2a": {
                        "issuer": issuer,
                        "audience": audience,
                        "workspace_id": workspace_id,
                        "trust_level": "pinned",
                        "protocol_version": "1.0",
                        "supported_protocol_versions": ["1.0"],
                        "protocol_binding": "JSONRPC",
                        "supported_protocol_bindings": ["JSONRPC"],
                        "security_schemes": presented_security_schemes,
                        "request_id": "req-replay-shared",
                        "sent_at": now.isoformat(),
                    }
                },
            },
            "replayed": {
                "task": _base_task("task-replay-second"),
                "metadata": {
                    "external_a2a": {
                        "issuer": issuer,
                        "audience": audience,
                        "workspace_id": workspace_id,
                        "trust_level": "pinned",
                        "protocol_version": "1.0",
                        "supported_protocol_versions": ["1.0"],
                        "protocol_binding": "JSONRPC",
                        "supported_protocol_bindings": ["JSONRPC"],
                        "security_schemes": presented_security_schemes,
                        "request_id": "req-replay-shared",
                        "sent_at": now.isoformat(),
                    }
                },
                "expected_http_status": 409,
                "expected_code": "replayed_request",
            },
        },
    }


def _base_task(task_id: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "input": [
            {
                "partId": "prompt",
                "kind": "text",
                "mimeType": "text/plain",
                "text": "Run the external A2A gateway conformance case.",
            }
        ],
    }


__all__ = [
    "EXTERNAL_A2A_CONFORMANCE_KIT_SCHEMA_VERSION",
    "build_external_a2a_conformance_kit",
]
