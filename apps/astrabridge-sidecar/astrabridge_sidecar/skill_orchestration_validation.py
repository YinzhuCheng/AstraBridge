from __future__ import annotations

"""Skill-to-graph resolution and preflight checks.

This module is deliberately a bridge, not a second orchestration runtime.  A
manifest is resolved to one canonical graph template and then passed through
the existing graph lint, compiler, diff, and dry-run owners.  The resolver
does not call a provider, invoke MCP, spawn an agent, or write run state.
"""

import hashlib
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .agent_orchestration_checks import (
    compile_agent_orchestration_graph_file,
    diff_agent_orchestration_graphs,
    dry_run_agent_orchestration_graph_file,
    lint_agent_orchestration_graph_file,
)
from .agent_orchestration_contract import AGENT_ORCHESTRATION_SCHEMA_VERSION
from .agent_orchestration_file_format import (
    load_agent_orchestration_example,
    load_agent_orchestration_graph_file,
    source_owned_agent_orchestration_graph,
)
from .communication_isolation import validate_typed_communication_isolation
from .skill_provider_a2a_binding import bind_skill_provider_a2a
from .mcp_node_policy import builtin_mcp_preset_catalog
from .security import DESKTOP_KEY_PATH_RE, SECRET_RE, assert_no_secret_path, resolve_under


SKILL_GRAPH_RESOLUTION_SCHEMA_VERSION = "astrabridge-skill-graph-resolution-v1"
SKILL_ORCHESTRATION_VALIDATION_SCHEMA_VERSION = "astrabridge-skill-orchestration-validation-v1"
SKILL_ORCHESTRATION_RESOLVER_VERSION = "astrabridge-skill-graph-resolver-v1"

_TEMPLATE_ALIASES = {
    "supervisor_worker_synthesizer": "supervisor_worker_synthesizer",
    "code_fix_test_review": "code_fix_review",
    "fanout_fanin_research": "fanout_research_synthesis",
    "provider_update_smoke_gate": "provider_update_smoke",
    "multimodal_capability_adapter": "multimodal_capability_adapter",
}
_FORBIDDEN_KEY_NAMES = {
    "access_token",
    "api_key",
    "authorization",
    "bearer",
    "cookie",
    "private_reasoning",
    "raw_prompt",
    "raw_secret",
    "secret",
    "secret_key",
    "token",
}
_SAFE_NODE_BIND_FIELDS = {"prompt"}
_BUDGET_FIELDS = (
    "max_total_agents",
    "max_parallel_agents",
    "max_total_tokens",
    "max_provider_calls",
    "max_retries",
)


def load_skill_orchestration_manifest(skill_ref: str | Path | dict[str, Any]) -> dict[str, Any]:
    """Load one manifest by path, skill directory, or stable skill id.

    The public loader returns only the manifest payload.  Resolution keeps the
    source path separately so the payload remains schema-valid and immutable.
    """

    manifest, _ = _load_manifest_record(skill_ref)
    return deepcopy(manifest)


def resolve_skill_to_graph(
    skill_ref: str | Path | dict[str, Any],
    parameters: dict[str, Any] | None = None,
    *,
    requested_route: dict[str, Any] | None = None,
    requested_budget: dict[str, Any] | None = None,
    configured_models: list[dict[str, Any]] | None = None,
    profile_records: list[dict[str, Any]] | None = None,
    external_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a skill manifest to a canonical graph without live execution."""

    warnings: list[str] = []
    blockers: list[str] = []
    manifest: dict[str, Any] | None = None
    manifest_path: Path | None = None
    try:
        manifest, manifest_path = _load_manifest_record(skill_ref)
    except Exception as exc:  # fail closed while preserving an actionable report
        return _blocked_resolution(
            skill_ref=skill_ref,
            blockers=[f"skill_manifest_load_failed: {exc}"],
        )

    schema_errors = _validate_manifest(manifest)
    blockers.extend(schema_errors)
    manifest_digest = _digest(manifest) if not _contains_secret_like(manifest) else None
    manifest_skill_id = str(manifest.get("skill_id") or "").strip() or None
    manifest_version = str(manifest.get("version") or "").strip() or None
    skill_status = str(manifest.get("status") or "candidate").strip() or "candidate"
    params = deepcopy(parameters) if isinstance(parameters, dict) else {}
    if parameters is not None and not isinstance(parameters, dict):
        blockers.append("parameters_must_be_object")
        params = {}
    if _contains_secret_like(params):
        blockers.append("secret_like_content_in_parameters")

    parameter_schema = dict(dict(manifest.get("resolution") or {}).get("parameter_schema") or {})
    blockers.extend(_validate_parameters(params, parameter_schema))
    binding_report, binding_blockers = _validate_bindings(
        manifest,
        parameters=params,
        manifest_path=manifest_path,
    )
    blockers.extend(binding_blockers)
    policy_snapshot, policy_warnings, policy_blockers = _validate_policies(
        manifest,
        requested_route=requested_route,
        requested_budget=requested_budget,
    )
    warnings.extend(policy_warnings)
    blockers.extend(policy_blockers)

    graph: dict[str, Any] | None = None
    source_ref: str | None = None
    source_digest: str | None = None
    communication_isolation: dict[str, Any] | None = None
    provider_a2a_binding: dict[str, Any] | None = None
    resolution = dict(manifest.get("resolution") or {})
    try:
        graph, source_ref = _resolve_graph_source(resolution, manifest_path=manifest_path)
        graph = source_owned_agent_orchestration_graph(graph)
        source_digest = _digest(graph)
        declared_source_digest = str(resolution.get("source_digest") or "").strip()
        if declared_source_digest and declared_source_digest.lower() != source_digest.lower():
            blockers.append(
                "graph_source_digest_mismatch: declared source_digest does not match the resolved canonical graph"
            )
        template_ref = str(resolution.get("graph_template_ref") or "").strip()
        expected_template = _TEMPLATE_ALIASES.get(template_ref)
        # The canonical examples retain their historical template_id (for
        # example ``code_fix_test_review``), while the manifest ref is the
        # stable skill-facing alias.  The alias map proves the one-to-one
        # relationship without forcing a graph-file rename.
        if expected_template and str(graph.get("template_id") or "").strip() not in {template_ref, expected_template}:
            blockers.append(
                f"graph_template_mismatch: expected {expected_template}, got {graph.get('template_id')}"
            )
        if str(graph.get("schema_version") or "").strip() != AGENT_ORCHESTRATION_SCHEMA_VERSION:
            blockers.append("graph_schema_version_mismatch")
        graph_policy = dict(graph.get("graph_policy") or {})
        if int(graph_policy.get("max_depth") or 0) > 2:
            blockers.append("graph_depth_exceeds_skill_limit: max_depth must be <= 2")
        if graph_policy.get("requires_dry_run_before_live") is not True:
            blockers.append("graph_requires_dry_run_before_live")
        communication_isolation = validate_typed_communication_isolation(graph)
        if str(communication_isolation.get("status") or "").strip() != "pass":
            blockers.extend(
                f"communication_isolation:{item}"
                for item in list(communication_isolation.get("blockers") or [])
                if str(item or "").strip()
            )
        provider_a2a_binding = bind_skill_provider_a2a(
            manifest,
            graph,
            configured_models=configured_models,
            profile_records=profile_records,
            external_registry=external_registry,
        )
        binding_status = str(provider_a2a_binding.get("status") or "").strip()
        if binding_status == "blocked":
            blockers.extend(
                f"provider_a2a:{item}"
                for item in list(provider_a2a_binding.get("blockers") or [])
                if str(item or "").strip()
            )
        elif binding_status == "downgraded":
            warnings.extend(
                f"provider_a2a:{item}"
                for item in list(provider_a2a_binding.get("warnings") or [])
                if str(item or "").strip()
            )
    except Exception as exc:
        blockers.append(f"graph_source_invalid: {exc}")

    parameter_snapshot = _parameter_snapshot(params) if not _contains_secret_like(params) else {}
    provenance = {
        "resolver_version": SKILL_ORCHESTRATION_RESOLVER_VERSION,
        "skill_id": manifest_skill_id,
        "skill_version": manifest_version,
        "manifest_digest": manifest_digest,
        "source_ref": source_ref,
        "source_digest": source_digest,
        "graph_digest": source_digest,
        "parameter_names": sorted(str(key) for key in params),
        "parameter_count": len(params),
        "live_provider_calls": 0,
        "mcp_calls": 0,
        "agent_invocations": 0,
    }
    if manifest_path is not None:
        provenance["manifest_path"] = str(manifest_path)
    status = "blocked" if blockers else skill_status
    return {
        "schema_version": SKILL_GRAPH_RESOLUTION_SCHEMA_VERSION,
        "status": status,
        "skill_status": skill_status,
        "skill_ref": {"skill_id": manifest_skill_id, "version": manifest_version},
        "manifest_path": str(manifest_path) if manifest_path is not None else None,
        "manifest_digest": manifest_digest,
        "source_ref": source_ref,
        "source_digest": source_digest,
        "graph_digest": source_digest,
        "canonical_graph": deepcopy(graph) if graph is not None else None,
        "parameter_snapshot": parameter_snapshot,
        "binding_report": binding_report,
        "policy_snapshot": policy_snapshot,
        "communication_isolation": communication_isolation,
        "provider_a2a_binding": provider_a2a_binding,
        "warnings": _unique(warnings),
        "blockers": _unique(blockers),
        "provenance": provenance,
        "evidence": _evidence_snapshot(manifest),
    }


def validate_skill_orchestration(
    skill_ref: str | Path | dict[str, Any],
    parameters: dict[str, Any] | None = None,
    *,
    requested_route: dict[str, Any] | None = None,
    requested_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run resolution, lint, compile, and dry-run checks as one preflight."""

    resolution = resolve_skill_to_graph(
        skill_ref,
        parameters,
        requested_route=requested_route,
        requested_budget=requested_budget,
    )
    checks: dict[str, Any] = {}
    if not resolution.get("blockers") and isinstance(resolution.get("canonical_graph"), dict):
        for operation in ("lint", "compile", "dry_run"):
            checks[operation] = _run_graph_check(
                operation,
                resolution["canonical_graph"],
                source_ref=str(resolution.get("source_ref") or "<skill-graph>"),
            )
    else:
        checks = {operation: None for operation in ("lint", "compile", "dry_run")}
    return _validation_report("validate", resolution, checks)


def lint_skill_orchestration(
    skill_ref: str | Path | dict[str, Any],
    parameters: dict[str, Any] | None = None,
    *,
    requested_route: dict[str, Any] | None = None,
    requested_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _operation_report(
        "lint",
        skill_ref,
        parameters,
        requested_route=requested_route,
        requested_budget=requested_budget,
    )


def compile_skill_orchestration(
    skill_ref: str | Path | dict[str, Any],
    parameters: dict[str, Any] | None = None,
    *,
    requested_route: dict[str, Any] | None = None,
    requested_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _operation_report(
        "compile",
        skill_ref,
        parameters,
        requested_route=requested_route,
        requested_budget=requested_budget,
    )


def dry_run_skill_orchestration(
    skill_ref: str | Path | dict[str, Any],
    parameters: dict[str, Any] | None = None,
    *,
    requested_route: dict[str, Any] | None = None,
    requested_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _operation_report(
        "dry_run",
        skill_ref,
        parameters,
        requested_route=requested_route,
        requested_budget=requested_budget,
    )


def diff_skill_orchestrations(
    old_skill_ref: str | Path | dict[str, Any],
    new_skill_ref: str | Path | dict[str, Any],
    old_parameters: dict[str, Any] | None = None,
    new_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    old_resolution = resolve_skill_to_graph(old_skill_ref, old_parameters)
    new_resolution = resolve_skill_to_graph(new_skill_ref, new_parameters)
    blockers = [
        f"old_{item}"
        for item in list(old_resolution.get("blockers") or [])
    ] + [
        f"new_{item}"
        for item in list(new_resolution.get("blockers") or [])
    ]
    if blockers:
        return {
            "schema_version": SKILL_ORCHESTRATION_VALIDATION_SCHEMA_VERSION,
            "operation": "diff",
            "status": "blocked",
            "resolutions": {"old": old_resolution, "new": new_resolution},
            "graph_diff": None,
            "warnings": _unique([*old_resolution.get("warnings", []), *new_resolution.get("warnings", [])]),
            "blockers": _unique(blockers),
            "provenance": {"old": old_resolution.get("provenance"), "new": new_resolution.get("provenance")},
            "evidence": {"old": old_resolution.get("evidence"), "new": new_resolution.get("evidence")},
        }
    old_graph = dict(old_resolution["canonical_graph"])
    new_graph = dict(new_resolution["canonical_graph"])
    graph_diff = diff_agent_orchestration_graphs(
        old_graph,
        new_graph,
        old_file_path=str(old_resolution.get("source_ref") or "<skill-graph>"),
        new_file_path=str(new_resolution.get("source_ref") or "<skill-graph>"),
    )
    changes = list(graph_diff.get("changes") or [])
    old_param_digest = str(dict(old_resolution.get("parameter_snapshot") or {}).get("parameters_digest") or "")
    new_param_digest = str(dict(new_resolution.get("parameter_snapshot") or {}).get("parameters_digest") or "")
    if old_param_digest != new_param_digest:
        changes.append(
            {
                "change_type": "skill_parameters_changed",
                "old_parameter_digest": old_param_digest,
                "new_parameter_digest": new_param_digest,
                "old_parameter_names": list(dict(old_resolution.get("provenance") or {}).get("parameter_names") or []),
                "new_parameter_names": list(dict(new_resolution.get("provenance") or {}).get("parameter_names") or []),
            }
        )
    change_types = sorted({str(item.get("change_type") or "") for item in changes if str(item.get("change_type") or "")})
    return {
        "schema_version": SKILL_ORCHESTRATION_VALIDATION_SCHEMA_VERSION,
        "operation": "diff",
        "status": "changed" if changes else "no_change",
        "resolutions": {"old": old_resolution, "new": new_resolution},
        "graph_diff": {
            **graph_diff,
            "status": "changed" if changes else "no_change",
            "summary": {**dict(graph_diff.get("summary") or {}), "change_count": len(changes), "change_types": change_types},
            "changes": changes,
        },
        "warnings": _unique([*old_resolution.get("warnings", []), *new_resolution.get("warnings", [])]),
        "blockers": [],
        "provenance": {"old": old_resolution.get("provenance"), "new": new_resolution.get("provenance")},
        "evidence": {"old": old_resolution.get("evidence"), "new": new_resolution.get("evidence")},
    }


def render_skill_orchestration_report_markdown(report: dict[str, Any]) -> str:
    """Render a compact, redacted operator report for CLI/evidence use."""

    lines = [
        "# AstraBridge Skill Orchestration Validation",
        "",
        f"- Operation: `{report.get('operation')}`",
        f"- Status: `{report.get('status')}`",
    ]
    resolution = report.get("resolution")
    if isinstance(resolution, dict):
        lines.extend(
            [
                f"- Skill: `{dict(resolution.get('skill_ref') or {}).get('skill_id')}`",
                f"- Manifest digest: `{resolution.get('manifest_digest')}`",
                f"- Graph digest: `{resolution.get('graph_digest')}`",
            ]
        )
    if isinstance(report.get("resolutions"), dict):
        lines.append("- Diff resolves both old and new skill references.")
    warnings = list(report.get("warnings") or [])
    blockers = list(report.get("blockers") or [])
    if warnings:
        lines.extend(["", "## Warnings", *[f"- {item}" for item in warnings]])
    if blockers:
        lines.extend(["", "## Blockers", *[f"- {item}" for item in blockers]])
    checks = report.get("checks")
    if isinstance(checks, dict):
        lines.extend(["", "## Checks"])
        for name, check in checks.items():
            status = dict(check or {}).get("status") if isinstance(check, dict) else "blocked_by_resolution"
            lines.append(f"- `{name}`: `{status}`")
    return "\n".join(lines).strip() + "\n"


def _operation_report(
    operation: str,
    skill_ref: str | Path | dict[str, Any],
    parameters: dict[str, Any] | None,
    *,
    requested_route: dict[str, Any] | None,
    requested_budget: dict[str, Any] | None,
) -> dict[str, Any]:
    resolution = resolve_skill_to_graph(
        skill_ref,
        parameters,
        requested_route=requested_route,
        requested_budget=requested_budget,
    )
    check = None
    if not resolution.get("blockers") and isinstance(resolution.get("canonical_graph"), dict):
        check = _run_graph_check(
            operation,
            resolution["canonical_graph"],
            source_ref=str(resolution.get("source_ref") or "<skill-graph>"),
        )
    return _validation_report(operation, resolution, {operation: check})


def _validation_report(operation: str, resolution: dict[str, Any], checks: dict[str, Any]) -> dict[str, Any]:
    warnings = list(resolution.get("warnings") or [])
    blockers = list(resolution.get("blockers") or [])
    for check in checks.values():
        if not isinstance(check, dict):
            continue
        warnings.extend(str(item) for item in list(check.get("warnings") or []))
        blockers.extend(str(item) for item in list(check.get("blockers") or []))
    check_statuses = [str(dict(check or {}).get("status") or "blocked") for check in checks.values()]
    if blockers or "blocked" in check_statuses:
        status = "blocked"
    elif operation == "diff":
        status = "pass"
    else:
        status = "pass"
    return {
        "schema_version": SKILL_ORCHESTRATION_VALIDATION_SCHEMA_VERSION,
        "operation": operation,
        "status": status,
        "resolution": resolution,
        "checks": checks,
        "warnings": _unique(warnings),
        "blockers": _unique(blockers),
        "provenance": resolution.get("provenance"),
        "evidence": resolution.get("evidence"),
    }


def _run_graph_check(operation: str, graph: dict[str, Any], *, source_ref: str) -> dict[str, Any]:
    """Use existing file-based check owners with an ephemeral canonical copy."""

    try:
        with tempfile.TemporaryDirectory(prefix="astrabridge-skill-graph-") as temp_dir:
            graph_path = Path(temp_dir) / "resolved-graph.json"
            graph_path.write_text(
                json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            if operation == "lint":
                report = lint_agent_orchestration_graph_file(graph_path)
            elif operation == "compile":
                report = compile_agent_orchestration_graph_file(graph_path)
            elif operation == "dry_run":
                report = dry_run_agent_orchestration_graph_file(graph_path)
            else:
                raise ValueError(f"unsupported skill graph check: {operation}")
        report = deepcopy(report)
        report["source_ref"] = source_ref
        report.pop("file_path", None)
        return report
    except Exception as exc:
        return {
            "status": "blocked",
            "operation": operation,
            "source_ref": source_ref,
            "warnings": [],
            "blockers": [f"{operation}_failed: {exc}"],
        }


def _resolve_graph_source(resolution: dict[str, Any], *, manifest_path: Path | None) -> tuple[dict[str, Any], str]:
    mode = str(resolution.get("mode") or "").strip()
    graph_schema_version = str(resolution.get("graph_schema_version") or "").strip()
    if graph_schema_version != AGENT_ORCHESTRATION_SCHEMA_VERSION:
        raise ValueError("resolution.graph_schema_version must match the canonical graph schema")
    if mode == "builtin_template":
        template_ref = str(resolution.get("graph_template_ref") or "").strip()
        example_id = _TEMPLATE_ALIASES.get(template_ref)
        if not example_id:
            raise ValueError(f"unknown graph_template_ref: {template_ref or '<empty>'}")
        return load_agent_orchestration_example(example_id), f"examples/agent-orchestration/{example_id}.json"
    if mode == "project_graph":
        graph_file_ref = str(resolution.get("graph_file_ref") or "").strip()
        if not graph_file_ref:
            raise ValueError("resolution.graph_file_ref is required")
        repo_root = _repo_root()
        base = manifest_path.parent if manifest_path is not None else repo_root
        candidate = Path(graph_file_ref)
        if not candidate.is_absolute():
            candidate = base / candidate
        graph_path = resolve_under(repo_root, candidate)
        assert_no_secret_path(graph_path)
        if not graph_path.is_file():
            raise ValueError(f"project graph file does not exist: {graph_file_ref}")
        return load_agent_orchestration_graph_file(graph_path), graph_path.relative_to(repo_root).as_posix()
    if mode == "inline_graph":
        graph = resolution.get("inline_graph")
        if not isinstance(graph, dict):
            raise ValueError("resolution.inline_graph must be an object")
        return deepcopy(graph), "inline_graph"
    raise ValueError(f"unsupported resolution.mode: {mode or '<empty>'}")


def _validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if _contains_secret_like(manifest):
        errors.append("secret_like_content_in_manifest")
    try:
        import jsonschema

        schema_path = _repo_root() / "PLAN" / "schemas" / "astrabridge-skill-to-graph-manifest-v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.absolute_path)):
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            errors.append(f"manifest_schema:{location}: {error.message}")
    except Exception as exc:
        errors.append(f"manifest_schema_validation_failed: {exc}")
    return errors


def _validate_parameters(parameters: dict[str, Any], parameter_schema: dict[str, Any]) -> list[str]:
    if not parameter_schema:
        return ["missing_parameter_schema"]
    try:
        import jsonschema

        validator = jsonschema.Draft202012Validator(parameter_schema)
        return [
            f"parameter_schema:{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
            for error in sorted(validator.iter_errors(parameters), key=lambda item: list(item.absolute_path))
        ]
    except Exception as exc:
        return [f"parameter_schema_validation_failed: {exc}"]


def _validate_bindings(
    manifest: dict[str, Any],
    *,
    parameters: dict[str, Any],
    manifest_path: Path | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    resolution = dict(manifest.get("resolution") or {})
    schema = dict(resolution.get("parameter_schema") or {})
    properties = dict(schema.get("properties") or {})
    required_parameters = {str(item).strip() for item in list(schema.get("required") or []) if str(item).strip()}
    bindings = list(resolution.get("bindings") or [])
    seen: set[str] = set()
    report: list[dict[str, Any]] = []
    blockers: list[str] = []
    graph: dict[str, Any] | None = None
    try:
        graph, _ = _resolve_graph_source(resolution, manifest_path=manifest_path)
    except Exception:
        # Source errors are reported by the resolver; binding names can still
        # be checked independently so diagnostics stay actionable.
        graph = None
    for binding in bindings:
        if not isinstance(binding, dict):
            blockers.append("binding_must_be_object")
            continue
        parameter = str(binding.get("parameter") or "").strip()
        graph_path = str(binding.get("graph_path") or "").strip()
        required = bool(binding.get("required"))
        if parameter not in properties:
            blockers.append(f"binding_unknown_parameter: {parameter or '<empty>'}")
        if parameter in seen:
            blockers.append(f"binding_duplicate_parameter: {parameter}")
        seen.add(parameter)
        if parameter in required_parameters and not required:
            blockers.append(f"binding_required_flag_must_be_true: {parameter}")
        path_status = "validated"
        if graph_path.startswith("input"):
            if graph_path == "input":
                blockers.append("binding_input_path_must_name_field")
        elif graph_path.startswith("nodes."):
            parts = graph_path.split(".")
            if len(parts) != 3 or parts[2] not in _SAFE_NODE_BIND_FIELDS:
                blockers.append(
                    f"binding_unsafe_graph_path: {graph_path}; only input.* and nodes.<id>.prompt are allowed"
                )
                path_status = "blocked"
            elif graph is not None:
                node = next(
                    (
                        item
                        for item in list(graph.get("nodes") or [])
                        if isinstance(item, dict) and str(item.get("node_id") or "") == parts[1]
                    ),
                    None,
                )
                if node is None:
                    blockers.append(f"binding_unknown_node: {parts[1]}")
                    path_status = "blocked"
                elif parts[2] not in node:
                    blockers.append(f"binding_missing_graph_field: {graph_path}")
                    path_status = "blocked"
        else:
            blockers.append(f"binding_unsupported_graph_path: {graph_path or '<empty>'}")
            path_status = "blocked"
        report.append(
            {
                "parameter": parameter,
                "graph_path": graph_path,
                "required": required,
                "status": path_status,
                "value_present": parameter in parameters,
                "value_type": _safe_type(parameters.get(parameter)) if parameter in parameters else None,
            }
        )
    for parameter in sorted(required_parameters.difference(seen)):
        blockers.append(f"binding_missing_required_parameter: {parameter}")
    unknown_parameters = sorted(set(parameters).difference(properties))
    for parameter in unknown_parameters:
        blockers.append(f"parameter_not_declared: {parameter}")
    return report, blockers


def _validate_policies(
    manifest: dict[str, Any],
    *,
    requested_route: dict[str, Any] | None,
    requested_budget: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    policies = deepcopy(dict(manifest.get("policies") or {}))
    warnings: list[str] = []
    blockers: list[str] = []
    composition = dict(manifest.get("composition") or {})
    if composition.get("allow_runtime_nesting") is not False:
        blockers.append("runtime_nesting_must_be_disabled")
    expansion_depth = composition.get("max_expansion_depth")
    if not isinstance(expansion_depth, int) or isinstance(expansion_depth, bool) or expansion_depth != 1:
        blockers.append("composition_depth_must_equal_one")
    communication = dict(policies.get("communication") or {})
    if communication.get("exclude_private_memory") is not True:
        blockers.append("private_memory_must_be_excluded")
    if communication.get("allow_direct_teammate_messages") is not False:
        blockers.append("direct_teammate_messages_must_be_disabled")
    subagent = dict(policies.get("subagent") or {})
    if subagent.get("allow_nested_subagents") is not False:
        blockers.append("nested_subagents_must_be_disabled")
    if subagent.get("allow_direct_teammate_messages") is not False:
        blockers.append("subagent_direct_messages_must_be_disabled")
    mcp = dict(policies.get("mcp") or {})
    if mcp.get("loopback_allowed") is not True:
        blockers.append("mcp_loopback_must_remain_enabled_for_uniform_interface")
    a2a = dict(policies.get("a2a") or {})
    if a2a.get("gateway_required") is not True:
        blockers.append("a2a_gateway_required")
    if a2a.get("external_enabled") and not list(a2a.get("allowed_card_refs") or []):
        blockers.append("external_a2a_requires_allowed_card_refs")
    budget = dict(policies.get("budget") or {})
    for field in _BUDGET_FIELDS[:-1]:
        value = budget.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            blockers.append(f"budget_{field}_must_be_integer")
        elif value <= 0:
            blockers.append(f"budget_{field}_must_be_positive")
    max_retries = budget.get("max_retries")
    if not isinstance(max_retries, int) or isinstance(max_retries, bool):
        blockers.append("budget_max_retries_must_be_integer")
    elif max_retries < 0:
        blockers.append("budget_max_retries_must_be_non_negative")
    max_parallel_agents = budget.get("max_parallel_agents")
    max_total_agents = budget.get("max_total_agents")
    if (
        isinstance(max_parallel_agents, int)
        and not isinstance(max_parallel_agents, bool)
        and isinstance(max_total_agents, int)
        and not isinstance(max_total_agents, bool)
        and max_parallel_agents > max_total_agents
    ):
        blockers.append("budget_max_parallel_agents_exceeds_total_agents")
    provider_limits = _limits_by_key(budget.get("provider_concurrency"), "provider_id")
    model_limits = _limits_by_key(budget.get("model_concurrency"), "model_id")
    if len(provider_limits) != len(list(budget.get("provider_concurrency") or [])):
        blockers.append("budget_provider_concurrency_contains_duplicates")
    if len(model_limits) != len(list(budget.get("model_concurrency") or [])):
        blockers.append("budget_model_concurrency_contains_duplicates")
    routing = dict(policies.get("routing") or {})
    allowed_providers = {str(item).strip() for item in list(routing.get("allowed_provider_ids") or []) if str(item).strip()}
    allowed_models = {str(item).strip() for item in list(routing.get("allowed_model_ids") or []) if str(item).strip()}
    if requested_route is not None:
        if not isinstance(requested_route, dict):
            blockers.append("requested_route_must_be_object")
        else:
            requested_provider = str(requested_route.get("provider_id") or "").strip()
            requested_model = str(requested_route.get("model_id") or "").strip()
            if requested_provider and requested_provider not in allowed_providers:
                blockers.append(f"requested_route_widens_provider_allowlist: {requested_provider}")
            if requested_model and requested_model not in allowed_models:
                blockers.append(f"requested_route_widens_model_allowlist: {requested_model}")
    effective_budget = deepcopy(budget)
    if requested_budget is not None:
        if not isinstance(requested_budget, dict):
            blockers.append("requested_budget_must_be_object")
        else:
            for field, value in requested_budget.items():
                if field not in _BUDGET_FIELDS:
                    blockers.append(f"requested_budget_unknown_field: {field}")
                    continue
                if not isinstance(value, int) or isinstance(value, bool):
                    blockers.append(f"requested_budget_{field}_must_be_integer")
                    continue
                manifest_value_raw = budget.get(field)
                if not isinstance(manifest_value_raw, int) or isinstance(manifest_value_raw, bool):
                    blockers.append(f"requested_budget_manifest_value_invalid_{field}")
                    continue
                manifest_value = manifest_value_raw
                if field == "max_retries":
                    valid_range = 0 <= value <= manifest_value
                else:
                    valid_range = 1 <= value <= manifest_value
                if not valid_range:
                    blockers.append(f"requested_budget_widens_or_invalid_{field}")
                else:
                    effective_budget[field] = value
    effective_parallel = effective_budget.get("max_parallel_agents")
    effective_total = effective_budget.get("max_total_agents")
    if (
        isinstance(effective_parallel, int)
        and not isinstance(effective_parallel, bool)
        and isinstance(effective_total, int)
        and not isinstance(effective_total, bool)
        and effective_parallel > effective_total
    ):
        blockers.append("requested_budget_max_parallel_agents_exceeds_total_agents")
    available_presets = builtin_mcp_preset_catalog()
    for preset_id in list(mcp.get("preset_ids") or []):
        if str(preset_id).strip() not in available_presets:
            warnings.append(f"mcp_preset_not_available_yet: {preset_id}")
    for rule in list(mcp.get("tool_rules") or []):
        if isinstance(rule, dict) and str(rule.get("server") or "").strip() not in available_presets:
            warnings.append(f"mcp_server_not_available_yet: {rule.get('server')}")
    if str(manifest.get("status") or "candidate") == "candidate":
        warnings.append("skill_lifecycle_candidate: product promotion remains gated")
    policy_snapshot = {
        "routing": routing,
        "mcp": mcp,
        "communication": communication,
        "subagent": subagent,
        "budget": effective_budget,
        "approval": deepcopy(dict(policies.get("approval") or {})),
        "a2a": a2a,
        "composition": composition,
        "requested_route": deepcopy(requested_route) if isinstance(requested_route, dict) else None,
        "requested_budget": deepcopy(requested_budget) if isinstance(requested_budget, dict) else None,
    }
    return policy_snapshot, _unique(warnings), _unique(blockers)


def _load_manifest_record(skill_ref: str | Path | dict[str, Any]) -> tuple[dict[str, Any], Path | None]:
    if isinstance(skill_ref, dict):
        return deepcopy(skill_ref), None
    candidate = Path(str(skill_ref))
    if candidate.exists():
        manifest_path = candidate / "orchestration-manifest.json" if candidate.is_dir() else candidate
        return _read_manifest_file(manifest_path), manifest_path.resolve()
    text_ref = str(skill_ref).strip()
    skills_root = _repo_root() / "apps" / "astrabridge-sidecar" / "skills"
    direct = skills_root / text_ref / "orchestration-manifest.json"
    if direct.is_file():
        return _read_manifest_file(direct), direct.resolve()
    matches: list[Path] = []
    for path in sorted(skills_root.glob("*/orchestration-manifest.json")):
        try:
            payload = _read_manifest_file(path)
        except Exception:
            continue
        skill_id = str(payload.get("skill_id") or "").strip()
        if text_ref in {skill_id, path.parent.name, skill_id.replace(".", "-")}:
            matches.append(path)
    if len(matches) == 1:
        return _read_manifest_file(matches[0]), matches[0].resolve()
    if len(matches) > 1:
        raise ValueError(f"ambiguous skill reference: {text_ref}")
    raise FileNotFoundError(f"skill orchestration manifest not found: {text_ref}")


def _read_manifest_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"skill orchestration manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("skill orchestration manifest must be an object")
    return payload


def _blocked_resolution(*, skill_ref: Any, blockers: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SKILL_GRAPH_RESOLUTION_SCHEMA_VERSION,
        "status": "blocked",
        "skill_status": None,
        "skill_ref": {"input": str(skill_ref) if not isinstance(skill_ref, dict) else "<manifest-object>"},
        "manifest_path": None,
        "manifest_digest": None,
        "source_ref": None,
        "source_digest": None,
        "graph_digest": None,
        "canonical_graph": None,
        "parameter_snapshot": {},
        "binding_report": [],
        "policy_snapshot": None,
        "warnings": [],
        "blockers": _unique(blockers),
        "provenance": {
            "resolver_version": SKILL_ORCHESTRATION_RESOLVER_VERSION,
            "live_provider_calls": 0,
            "mcp_calls": 0,
            "agent_invocations": 0,
        },
        "evidence": None,
    }


def _evidence_snapshot(manifest: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(manifest.get("evidence") or {})
    return {
        "required_level": evidence.get("required_level"),
        "fixture_ref": evidence.get("fixture_ref"),
        "artifact_root": evidence.get("artifact_root"),
        "redaction": "parameter values and prompt payloads are omitted",
    }


def _parameter_snapshot(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "parameters_digest": _digest(parameters),
        "parameters": {
            str(key): {"type": _safe_type(value), "present": True}
            for key, value in sorted(parameters.items())
        },
    }


def _safe_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _limits_by_key(items: Any, key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in list(items or []):
        if not isinstance(item, dict):
            continue
        value = str(item.get(key) or "").strip()
        if value:
            result[value] = item
    return result


def _contains_secret_like(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).strip().lower().replace("-", "_")
            if lowered in _FORBIDDEN_KEY_NAMES or SECRET_RE.search(str(key)):
                return True
            if _contains_secret_like(child):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_secret_like(child) for child in value)
    if isinstance(value, str):
        return bool(DESKTOP_KEY_PATH_RE.search(value) or SECRET_RE.search(value))
    return False


def _digest(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _unique(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(value)
    return result
