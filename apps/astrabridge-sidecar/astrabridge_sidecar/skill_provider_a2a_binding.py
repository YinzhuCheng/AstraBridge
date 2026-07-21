"""Provider/profile and external-A2A binding for skill-backed graphs.

This is a read-only qualification layer.  It resolves declarative skill
routing against the existing provider registry/model catalog and delegates
external peer handling to ``external_a2a_gateway``.  It never reads secrets,
performs provider calls, discovers a peer over the network, or creates a
parallel runtime protocol.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .agent_orchestration_checks import build_known_model_capabilities
from .external_a2a_conformance import (
    EXTERNAL_A2A_CONFORMANCE_KIT_SCHEMA_VERSION,
    build_external_a2a_conformance_kit,
)
from .external_a2a_gateway import (
    EXTERNAL_A2A_CARD_REF_PREFIX,
    build_external_a2a_gateway_snapshot,
    validate_external_a2a_agent_card_registry,
)
from .model_catalog.catalog import effective_model_record, effective_model_records
from .providers import all_provider_profiles, get_provider_profile, resolve_provider_id
from .security import redact_sensitive


SKILL_PROVIDER_A2A_BINDING_SCHEMA_VERSION = "astrabridge-skill-provider-a2a-binding-v1"
SKILL_PROVIDER_A2A_BINDING_VERSION = "astrabridge-provider-a2a-binding-v1"
_TRUST_RANK = {"untrusted": 0, "workspace_trusted": 1, "pinned": 2}


def bind_skill_provider_a2a(
    manifest: dict[str, Any],
    graph: dict[str, Any],
    *,
    configured_models: list[dict[str, Any]] | None = None,
    profile_records: list[dict[str, Any]] | None = None,
    external_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve skill route declarations into a redacted qualification report.

    ``status=qualified`` means every explicit graph route has a catalog/model
    capability record and the configured requirement level is satisfied.
    ``status=downgraded`` is intentionally non-fatal for candidate skills: the
    graph remains reviewable, but the report records exactly what is missing.
    Promoted/provider-qualified skill statuses fail closed instead of silently
    treating a downgrade as a qualification.
    """

    blockers: list[str] = []
    warnings: list[str] = []
    route_results: list[dict[str, Any]] = []
    manifest_data = dict(manifest or {}) if isinstance(manifest, dict) else {}
    graph_data = dict(graph or {}) if isinstance(graph, dict) else {}
    routing = dict(dict(manifest_data.get("policies") or {}).get("routing") or {})
    required_level = str(
        dict(manifest_data.get("evidence") or {}).get("required_level")
        or manifest_data.get("status")
        or "candidate"
    ).strip() or "candidate"
    allowed_providers = {
        _clean_provider(item)
        for item in list(routing.get("allowed_provider_ids") or [])
        if str(item or "").strip()
    }
    allowed_models = {
        _native_model_id(item)
        for item in list(routing.get("allowed_model_ids") or [])
        if str(item or "").strip()
    }
    fallback_mode = str(routing.get("fallback_mode") or "deny").strip() or "deny"
    declared_profile_ids = {
        str(item).strip()
        for item in list(routing.get("profile_ids") or [])
        if str(item or "").strip()
    }
    profile_index = {
        str(item.get("profile_id") or "").strip(): dict(item)
        for item in list(profile_records or [])
        if isinstance(item, dict) and str(item.get("profile_id") or "").strip()
    }
    provider_ids = {profile.id for profile in all_provider_profiles()}
    effective_models = effective_model_records(configured_models, include_disabled=True)

    if not allowed_providers:
        blockers.append("routing_allowed_provider_ids_must_not_be_empty")
    if not allowed_models:
        blockers.append("routing_allowed_model_ids_must_not_be_empty")

    known_capabilities = build_known_model_capabilities(
        graph=graph_data,
        configured_models=configured_models,
        profile_records=profile_records,
    )
    for node in list(graph_data.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        route_results.append(
            _bind_node_route(
                node,
                graph=graph_data,
                routing=routing,
                allowed_providers=allowed_providers,
                allowed_models=allowed_models,
                declared_profile_ids=declared_profile_ids,
                profile_index=profile_index,
                provider_ids=provider_ids,
                effective_models=effective_models,
                known_capabilities=known_capabilities,
                fallback_mode=fallback_mode,
            )
        )
    for route in route_results:
        blockers.extend(str(item) for item in list(route.get("blockers") or []) if str(item or "").strip())
        warnings.extend(str(item) for item in list(route.get("warnings") or []) if str(item or "").strip())

    a2a_result = _bind_external_a2a(
        manifest=manifest_data,
        graph=graph_data,
        required_level=required_level,
        external_registry=external_registry,
    )
    blockers.extend(str(item) for item in list(a2a_result.get("blockers") or []) if str(item or "").strip())
    warnings.extend(str(item) for item in list(a2a_result.get("warnings") or []) if str(item or "").strip())

    route_statuses = {str(item.get("status") or "") for item in route_results}
    # A deferred runtime-profile route is intentionally non-fatal for a
    # candidate skill, but it is not evidence of a qualified provider route.
    has_downgrade = bool(route_statuses.intersection({"downgraded", "deferred"})) or str(a2a_result.get("status") or "") == "downgraded"
    if required_level in {"provider-qualified", "external-a2a-qualified"}:
        if has_downgrade:
            blockers.append("required_qualification_level_not_met: downgraded_route")
        if any(status in {"blocked", "unresolved", "deferred"} for status in route_statuses):
            blockers.append("required_qualification_level_not_met: blocked_route")
    if required_level == "external-a2a-qualified" and str(a2a_result.get("status") or "") != "qualified":
        blockers.append("required_external_a2a_qualification_not_met")

    blockers = _unique(blockers)
    warnings = _unique(warnings)
    if blockers:
        status = "blocked"
    elif has_downgrade:
        status = "downgraded"
    elif route_results or str(a2a_result.get("status") or "") == "qualified":
        status = "qualified"
    else:
        status = "deferred"
    report: dict[str, Any] = {
        "schema_version": SKILL_PROVIDER_A2A_BINDING_SCHEMA_VERSION,
        "binding_version": SKILL_PROVIDER_A2A_BINDING_VERSION,
        "status": status,
        "required_level": required_level,
        "skill_id": str(manifest_data.get("skill_id") or "").strip() or None,
        "graph_id": str(graph_data.get("graph_id") or "").strip() or None,
        "routing_policy": {
            "selection_mode": str(routing.get("selection_mode") or "").strip() or None,
            "allowed_provider_ids": sorted(allowed_providers),
            "allowed_model_ids": sorted(allowed_models),
            "fallback_mode": fallback_mode,
            "required_capabilities": sorted(
                str(item).strip()
                for item in list(routing.get("required_capabilities") or [])
                if str(item or "").strip()
            ),
            "profile_ids": sorted(declared_profile_ids),
        },
        "route_results": route_results,
        "external_a2a": a2a_result,
        "warnings": warnings,
        "blockers": blockers,
        "provenance": {
            "provider_calls": 0,
            "mcp_calls": 0,
            "agent_invocations": 0,
            "network_discovery_calls": 0,
            "catalog_model_count": len(effective_models),
            "protocol_owner": "astrabridge_sidecar.protocol",
            "a2a_owner": "astrabridge_sidecar.external_a2a_gateway",
        },
    }
    report["binding_digest"] = _digest(report)
    return redact_sensitive(report)


def _bind_node_route(
    node: dict[str, Any],
    *,
    graph: dict[str, Any],
    routing: dict[str, Any],
    allowed_providers: set[str],
    allowed_models: set[str],
    declared_profile_ids: set[str],
    profile_index: dict[str, dict[str, Any]],
    provider_ids: set[str],
    effective_models: list[dict[str, Any]],
    known_capabilities: dict[str, dict[str, Any]],
    fallback_mode: str,
) -> dict[str, Any]:
    node_id = str(node.get("node_id") or "").strip() or "<node>"
    node_routing = dict(node.get("routing") or {})
    selection_mode = str(node_routing.get("selection_mode") or "none").strip() or "none"
    blockers: list[str] = []
    warnings: list[str] = []
    if selection_mode == "none":
        return {
            "node_id": node_id,
            "selection_mode": selection_mode,
            "status": "deferred",
            "provider_id": None,
            "model_id": None,
            "profile_id": None,
            "capability_status": "deferred",
            "required_port_types": _required_port_types(node),
            "warnings": [f"node:{node_id}:route_deferred_to_runtime_profile"],
            "blockers": [],
        }
    provider_raw = str(node_routing.get("provider_id") or "").strip()
    model_raw = str(node_routing.get("model_id") or "").strip()
    profile_id = str(node_routing.get("profile_id") or "").strip() or None
    provider_id = _clean_provider(provider_raw) if provider_raw else ""
    model_id = _native_model_id(model_raw)
    if selection_mode == "profile":
        if profile_id and declared_profile_ids and profile_id not in declared_profile_ids:
            blockers.append(f"node:{node_id}:profile_not_in_skill_allowlist:{profile_id}")
        profile = dict(profile_index.get(profile_id or "") or {})
        if not profile and profile_id:
            warnings.append(f"node:{node_id}:profile_not_present_in_readonly_snapshot:{profile_id}")
        provider_id = _clean_provider(str(profile.get("provider_id") or provider_raw)) if (profile or provider_raw) else ""
        model_id = _native_model_id(str(profile.get("model") or model_raw))
    if not provider_id:
        blockers.append(f"node:{node_id}:provider_id_missing_for_{selection_mode}_route")
    elif provider_id not in provider_ids:
        blockers.append(f"node:{node_id}:unknown_provider_id:{provider_id}")
    if provider_id and allowed_providers and provider_id not in allowed_providers:
        blockers.append(f"node:{node_id}:provider_not_in_skill_allowlist:{provider_id}")
    if not model_id:
        blockers.append(f"node:{node_id}:model_id_missing_for_{selection_mode}_route")
    elif allowed_models and model_id not in allowed_models:
        blockers.append(f"node:{node_id}:model_not_in_skill_allowlist:{model_id}")

    model_record = effective_model_record(provider_id, model_id, effective_models) if provider_id and model_id else None
    required_ports = _required_port_types(node)
    capability = dict(known_capabilities.get(model_id) or known_capabilities.get(f"{provider_id}/{model_id}") or {})
    missing_input_ports = sorted(set(required_ports["input"]).difference(set(capability.get("input_port_types") or [])))
    missing_output_ports = sorted(set(required_ports["output"]).difference(set(capability.get("output_port_types") or [])))
    if missing_input_ports:
        blockers.append(f"node:{node_id}:missing_model_input_capabilities:{','.join(missing_input_ports)}")
    if missing_output_ports:
        blockers.append(f"node:{node_id}:missing_model_output_capabilities:{','.join(missing_output_ports)}")
    capability_status = "qualified"
    if not model_record:
        capability_status = "downgraded"
        warnings.append(f"node:{node_id}:model_not_in_catalog_snapshot:{provider_id}/{model_id}")
    else:
        if model_record.get("enabled") is False:
            blockers.append(f"node:{node_id}:model_disabled:{provider_id}/{model_id}")
        snapshot = dict(model_record.get("verified_capability_snapshot") or {})
        snapshot_status = str(
            model_record.get("verified_capability_snapshot_status")
            or model_record.get("verified_capability_snapshot_verification_state")
            or snapshot.get("status")
            or "unverified"
        ).strip().lower()
        if snapshot_status not in {"verified", "partial"}:
            capability_status = "downgraded"
            warnings.append(f"node:{node_id}:model_capability_snapshot_{snapshot_status}:provider_canary_required")
        missing_declared_capability = _check_required_route_capabilities(
            node_id=node_id,
            model_record=model_record,
            required_capabilities=set(
                str(item).strip()
                for item in list(routing.get("required_capabilities") or [])
                if str(item or "").strip()
            ),
            warnings=warnings,
            blockers=blockers,
        )
        if missing_declared_capability:
            capability_status = "downgraded"
    profile_status = "qualified"
    if declared_profile_ids and not profile_id:
        matching_profiles = [
            item
            for item in profile_index.values()
            if _clean_provider(str(item.get("provider_id") or "")) == provider_id
            and str(item.get("profile_id") or "").strip() in declared_profile_ids
        ]
        if not matching_profiles:
            warnings.append(f"node:{node_id}:provider_profile_snapshot_missing:{provider_id}")
            profile_status = "downgraded"
        else:
            profile_id = str(matching_profiles[0].get("profile_id") or "").strip() or None
    if selection_mode == "profile" and profile_id and not profile_index.get(profile_id):
        profile_status = "downgraded"
    status = "blocked" if blockers else "downgraded" if capability_status == "downgraded" or profile_status == "downgraded" else "qualified"
    if status == "downgraded" and fallback_mode == "deny":
        warnings.append(f"node:{node_id}:fallback_mode_deny_but_route_is_not_fully_verified")
    return {
        "node_id": node_id,
        "selection_mode": selection_mode,
        "status": status,
        "provider_id": provider_id or None,
        "model_id": model_id or None,
        "profile_id": profile_id,
        "profile_status": profile_status,
        "capability_status": capability_status,
        "required_port_types": required_ports,
        "missing_input_port_types": missing_input_ports,
        "missing_output_port_types": missing_output_ports,
        "warnings": _unique(warnings),
        "blockers": _unique(blockers),
    }


def _check_required_route_capabilities(
    *,
    node_id: str,
    model_record: dict[str, Any],
    required_capabilities: set[str],
    warnings: list[str],
    blockers: list[str],
) -> bool:
    missing = False
    if "web_search" in required_capabilities and not (
        bool(model_record.get("supports_search_tool"))
        or str(model_record.get("web_search_tool_type") or "").strip()
        or str(model_record.get("mcp_web_support") or "").strip() in {"verified", "verified_astrabridge_web"}
    ):
        warnings.append(f"node:{node_id}:required_capability_web_search_not_verified")
        missing = True
    if "structured_edit" in required_capabilities:
        edit_policy = model_record.get("edit_policy")
        edit_values = set(edit_policy.values()) if isinstance(edit_policy, dict) else set()
        if "structured_edit" not in edit_values:
            warnings.append(f"node:{node_id}:required_capability_structured_edit_not_verified")
            missing = True
    for capability in sorted(required_capabilities.difference({"text", "structured_json", "web_search", "structured_edit"})):
        # Unknown capability labels are not silently treated as supported.
        warnings.append(f"node:{node_id}:required_capability_unmapped:{capability}")
        missing = True
    return missing


def _bind_external_a2a(
    *,
    manifest: dict[str, Any],
    graph: dict[str, Any],
    required_level: str,
    external_registry: dict[str, Any] | None,
) -> dict[str, Any]:
    policy = dict(dict(manifest.get("policies") or {}).get("a2a") or {})
    refs = sorted(
        str(node.get("card_ref") or "").strip()
        for node in list(graph.get("nodes") or [])
        if isinstance(node, dict) and str(node.get("card_ref") or "").strip().startswith(EXTERNAL_A2A_CARD_REF_PREFIX)
    )
    refs = sorted(set(refs))
    external_enabled = policy.get("external_enabled") is True
    allowed_refs = {
        str(item).strip()
        for item in list(policy.get("allowed_card_refs") or [])
        if str(item or "").strip()
    }
    minimum_trust = str(policy.get("minimum_trust_level") or "workspace_trusted").strip() or "workspace_trusted"
    blockers: list[str] = []
    warnings: list[str] = []
    if refs and not external_enabled:
        blockers.append("graph_references_external_a2a_but_skill_policy_disables_external_a2a")
    unknown_refs = sorted(set(refs).difference(allowed_refs))
    if refs and unknown_refs:
        blockers.append(f"external_a2a_card_not_in_skill_allowlist:{','.join(unknown_refs)}")
    if external_enabled and not refs:
        warnings.append("external_a2a_enabled_without_referenced_card_route")
    if not refs:
        return {
            "status": "not_requested" if not external_enabled else "downgraded",
            "external_enabled": external_enabled,
            "referenced_card_refs": [],
            "minimum_trust_level": minimum_trust,
            "gateway_required": policy.get("gateway_required") is True,
            "gateway_snapshot": None,
            "conformance": None,
            "warnings": _unique(warnings),
            "blockers": _unique(blockers),
        }

    registry = graph.get("external_agent_card_registry")
    if registry is None:
        registry = external_registry
    gateway_snapshot: dict[str, Any] | None = None
    try:
        normalized_registry = validate_external_a2a_agent_card_registry(
            registry,
            referenced_card_refs=set(refs),
        )
        gateway_snapshot = build_external_a2a_gateway_snapshot(
            registry=normalized_registry,
            referenced_card_refs=set(refs),
        )
    except Exception as exc:
        blockers.append(f"external_a2a_gateway_validation_failed:{type(exc).__name__}:{redact_sensitive(str(exc))}")

    cards = {
        str(item.get("card_ref") or "").strip(): dict(item)
        for item in list((gateway_snapshot or {}).get("registry_snapshot") or [])
        if isinstance(item, dict)
    }
    trust_downgrades: list[str] = []
    for ref in refs:
        card = cards.get(ref) or {}
        trust_level = str(card.get("trust_level") or "untrusted").strip().lower()
        if _TRUST_RANK.get(trust_level, -1) < _TRUST_RANK.get(minimum_trust, 1):
            trust_downgrades.append(ref)
            warnings.append(f"external_a2a_card_below_minimum_trust:{ref}:{trust_level}")
    if trust_downgrades and required_level == "external-a2a-qualified":
        blockers.append("external_a2a_trust_requirement_not_met")
    gateway_manifest = dict((gateway_snapshot or {}).get("manifest") or {})
    if gateway_snapshot and str(gateway_manifest.get("verification_state") or "").strip() != "verified":
        warnings.append("external_a2a_gateway_snapshot_is_downgraded")
        if required_level == "external-a2a-qualified":
            blockers.append("external_a2a_gateway_snapshot_not_verified")
    # The existing conformance kit is a deterministic, no-network fixture. It
    # proves the positive/negative case inventory is available without turning
    # skill resolution into a live peer call.
    kit = build_external_a2a_conformance_kit()
    conformance = {
        "schema_version": EXTERNAL_A2A_CONFORMANCE_KIT_SCHEMA_VERSION,
        "positive_case_present": isinstance(kit.get("positive_case"), dict),
        "negative_case_count": len(list(kit.get("negative_cases") or [])),
        "replay_case_present": isinstance(kit.get("replay_case"), dict),
        "network_calls": 0,
    }
    if not conformance["positive_case_present"] or not conformance["negative_case_count"]:
        blockers.append("external_a2a_conformance_fixture_incomplete")
    status = "blocked" if blockers else "downgraded" if trust_downgrades or not gateway_snapshot else "qualified"
    return {
        "status": status,
        "external_enabled": external_enabled,
        "referenced_card_refs": refs,
        "minimum_trust_level": minimum_trust,
        "gateway_required": policy.get("gateway_required") is True,
        "gateway_owner": "astrabridge_sidecar.external_a2a_gateway",
        "gateway_snapshot": _gateway_snapshot_summary(gateway_snapshot),
        "conformance": conformance,
        "warnings": _unique(warnings),
        "blockers": _unique(blockers),
    }


def _gateway_snapshot_summary(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    manifest = dict(snapshot.get("manifest") or {})
    return {
        "schema_version": str(snapshot.get("schema_version") or "").strip() or None,
        "supported_protocol_versions": [str(item).strip() for item in list(snapshot.get("supported_protocol_versions") or []) if str(item or "").strip()],
        "supported_protocol_bindings": [str(item).strip() for item in list(snapshot.get("supported_protocol_bindings") or []) if str(item or "").strip()],
        "referenced_card_refs": [str(item).strip() for item in list(snapshot.get("referenced_card_refs") or []) if str(item or "").strip()],
        "registry_digest": str(manifest.get("registry_digest") or "").strip() or None,
        "gateway_digest": str(manifest.get("digest") or "").strip() or None,
        "verification_state": str(manifest.get("verification_state") or "").strip() or None,
        "freshness_status": str(manifest.get("freshness_status") or "").strip() or None,
        "routable_card_refs": [str(item).strip() for item in list(manifest.get("routable_card_refs") or []) if str(item or "").strip()],
        "downgraded_card_refs": [str(item).strip() for item in list(manifest.get("downgraded_card_refs") or []) if str(item or "").strip()],
        "mapping_contract": deepcopy(dict(snapshot.get("mapping_contract") or {})),
    }


def _required_port_types(node: dict[str, Any]) -> dict[str, list[str]]:
    ports = dict(node.get("ports") or {})
    required_inputs = sorted(
        {
            str(item.get("port_type") or "").strip()
            for item in list(ports.get("inputs") or [])
            if isinstance(item, dict) and bool(item.get("required")) and str(item.get("port_type") or "").strip()
        }
    )
    outputs = sorted(
        {
            str(item.get("port_type") or "").strip()
            for item in list(ports.get("outputs") or [])
            if isinstance(item, dict) and str(item.get("port_type") or "").strip()
        }
    )
    return {"input": required_inputs, "output": outputs}


def _clean_provider(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return resolve_provider_id(text)
    except ValueError:
        return text.lower()


def _native_model_id(value: Any) -> str:
    text = str(value or "").strip()
    if "/" in text:
        return text.split("/", 1)[1].strip()
    return text


def _digest(value: dict[str, Any]) -> str:
    payload = {key: value[key] for key in value if key != "binding_digest"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))


__all__ = [
    "SKILL_PROVIDER_A2A_BINDING_SCHEMA_VERSION",
    "SKILL_PROVIDER_A2A_BINDING_VERSION",
    "bind_skill_provider_a2a",
]
