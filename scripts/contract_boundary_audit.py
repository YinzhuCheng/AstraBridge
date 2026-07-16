from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agent_orchestration_compiler import compile_agent_orchestration_graph  # noqa: E402
from astrabridge_sidecar.agent_orchestration_contract import (  # noqa: E402
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    lift_task_graph_to_agent_orchestration_graph,
    lower_agent_orchestration_graph_to_task_graph,
    validate_agent_orchestration_graph,
)
from astrabridge_sidecar.agent_orchestration_file_format import agent_orchestration_example_catalog  # noqa: E402
from astrabridge_sidecar.providers.transports import (  # noqa: E402
    ACTIVE_PROVIDER_FAMILY_TRANSPORTS,
    WIRE_API_FALLBACK_TRANSPORTS,
)
from astrabridge_sidecar.task_graph_contract import (  # noqa: E402
    TASK_GRAPH_RUN_SCHEMA_VERSION,
    TASK_GRAPH_SCHEMA_VERSION,
    load_task_graph_fixture,
    load_task_graph_run_fixture,
    task_graph_fixture_catalog,
    validate_graph_definition,
    validate_task_graph_run,
)


CONTRACT_BOUNDARY_AUDIT_SCHEMA_VERSION = "astrabridge-contract-boundary-audit-v1"
STABILITY_PLAN_PATH = REPO_ROOT / "PLAN" / "ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md"
CAPABILITY_PLAN_PATH = REPO_ROOT / "PLAN" / "CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md"
OWNERSHIP_DOC_PATH = REPO_ROOT / "docs" / "CODE_OWNERSHIP_AND_CONTRACTS.md"
PROTOCOL_PACKAGE_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "protocol" / "__init__.py"

EXPECTED_PROVIDER_TRANSPORTS = {
    "qwen": "QwenResponsesTransport",
    "deepseek": "DeepSeekChatTransport",
    "kimi": "KimiChatTransport",
    "glm": "GlmChatTransport",
}

EXPECTED_WIRE_TRANSPORTS = {
    "chat": "OpenAIChatTransport",
    "responses": "OpenAIResponsesTransport",
}


def _audit_stability_ownership() -> dict[str, Any]:
    """Verify that shared-contract ownership and plan routing are explicit.

    This is intentionally a small governance check rather than a runtime
    implementation check. It prevents a second active plan or compatibility
    document from becoming an unreviewed source of truth while the numbered
    migration steps move live consumers behind ``astrabridge_sidecar.protocol``.
    """

    errors: list[str] = []
    required_paths = {
        "stability_plan": STABILITY_PLAN_PATH,
        "capability_plan": CAPABILITY_PLAN_PATH,
        "ownership_doc": OWNERSHIP_DOC_PATH,
        "protocol_package": PROTOCOL_PACKAGE_PATH,
    }
    missing = [name for name, path in required_paths.items() if not path.exists()]
    if missing:
        errors.append(f"missing stability ownership inputs: {', '.join(sorted(missing))}")

    ownership_text = OWNERSHIP_DOC_PATH.read_text(encoding="utf-8") if OWNERSHIP_DOC_PATH.exists() else ""
    stability_text = STABILITY_PLAN_PATH.read_text(encoding="utf-8") if STABILITY_PLAN_PATH.exists() else ""
    capability_text = CAPABILITY_PLAN_PATH.read_text(encoding="utf-8") if CAPABILITY_PLAN_PATH.exists() else ""

    ownership_markers = (
        "astrabridge_sidecar.protocol",
        "Agent Envelope, delivery events, and artifact references",
        "MCP protocol core and broker boundary",
        "Durable graph run state, scheduler commands, and ordered events",
        "Canonical NodeType registry and compiled graph executable metadata",
        "ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md",
    )
    for marker in ownership_markers:
        if marker not in ownership_text:
            errors.append(f"ownership document missing canonical marker: {marker}")

    normalized_stability_text = stability_text.lower()
    if not (
        "single active execution source" in normalized_stability_text
        or "single execution source of truth" in normalized_stability_text
    ):
        errors.append("stability plan does not declare one active execution source")
    if "ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md" not in capability_text:
        errors.append("capability runtime plan does not delegate overlapping stability work")
    if "web lane" not in capability_text.lower() or "standalone" not in capability_text.lower():
        errors.append("capability plan delegation lost the standalone web-lane boundary")

    return {
        "contract": "stability_protocol_and_plan_ownership",
        "owner": "docs/CODE_OWNERSHIP_AND_CONTRACTS.md + astrabridge_sidecar.protocol",
        "status": "pass" if not errors else "fail",
        "required_inputs": {name: str(path.relative_to(REPO_ROOT)) for name, path in required_paths.items()},
        "errors": errors,
    }


def _graph_signature(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "graph_id": str(graph.get("graph_id") or ""),
        "task_id": str(graph.get("task_id") or ""),
        "template_id": str(graph.get("template_id") or ""),
        "node_ids": sorted(str(item.get("node_id") or "") for item in list(graph.get("nodes") or []) if isinstance(item, dict)),
        "edge_ids": sorted(str(item.get("edge_id") or "") for item in list(graph.get("edges") or []) if isinstance(item, dict)),
        "entry_node_ids": sorted(str(item) for item in list(dict(graph.get("graph_policy") or {}).get("entry_node_ids") or [])),
    }


def _audit_provider_transport_registry() -> dict[str, Any]:
    active = {family: transport.__name__ for family, transport in ACTIVE_PROVIDER_FAMILY_TRANSPORTS.items()}
    fallback = {wire_api: transport.__name__ for wire_api, transport in WIRE_API_FALLBACK_TRANSPORTS.items()}
    errors: list[str] = []
    if active != EXPECTED_PROVIDER_TRANSPORTS:
        errors.append(f"active provider transport registry drifted: {active}")
    if fallback != EXPECTED_WIRE_TRANSPORTS:
        errors.append(f"wire API fallback registry drifted: {fallback}")
    return {
        "contract": "provider_transport_selection",
        "owner": "astrabridge_sidecar.providers.transports",
        "status": "pass" if not errors else "fail",
        "active_provider_transports": active,
        "wire_api_fallback_transports": fallback,
        "errors": errors,
    }


def _audit_task_graph_fixtures() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    errors: list[str] = []
    for template_id in sorted(task_graph_fixture_catalog()):
        case_errors: list[str] = []
        node_count = 0
        edge_count = 0
        parallel_group_count = 0
        try:
            task_graph = load_task_graph_fixture(template_id)
            validated_task_graph = validate_graph_definition(task_graph)
            orchestration_graph = lift_task_graph_to_agent_orchestration_graph(validated_task_graph)
            canonical = validate_agent_orchestration_graph(orchestration_graph)
            compiled = compile_agent_orchestration_graph(canonical)
            lowered = validate_graph_definition(lower_agent_orchestration_graph_to_task_graph(canonical))
            task_run = validate_task_graph_run(load_task_graph_run_fixture(template_id), graph_definition=validated_task_graph)
            source_signature = _graph_signature(validated_task_graph)
            lowered_signature = _graph_signature(lowered)
            node_count = len(list(validated_task_graph.get("nodes") or []))
            edge_count = len(list(validated_task_graph.get("edges") or []))
            parallel_group_count = int(dict(compiled.get("topology") or {}).get("parallel_group_count") or 0)
            if source_signature != lowered_signature:
                case_errors.append("lift/lower changed graph identity, topology, or entry-node ownership")
            if canonical.get("schema_version") != AGENT_ORCHESTRATION_SCHEMA_VERSION:
                case_errors.append("lifted graph has an unexpected canonical schema version")
            if compiled.get("graph_id") != validated_task_graph.get("graph_id"):
                case_errors.append("compiled plan graph_id no longer matches the persisted graph")
            if task_run.get("schema_version") != TASK_GRAPH_RUN_SCHEMA_VERSION:
                case_errors.append("task graph run schema version drifted")
        except (TypeError, ValueError) as exc:
            case_errors.append(f"contract field drift or conversion failure: {exc}")
        if case_errors:
            errors.extend(f"{template_id}: {message}" for message in case_errors)
        cases.append(
            {
                "template_id": template_id,
                "status": "pass" if not case_errors else "fail",
                "node_count": node_count,
                "edge_count": edge_count,
                "parallel_group_count": parallel_group_count,
                "errors": case_errors,
            }
        )
    return {
        "contract": "persisted_task_graph_to_canonical_orchestration",
        "owner": "task_graph_contract + agent_orchestration_contract",
        "status": "pass" if not errors else "fail",
        "task_graph_schema_version": TASK_GRAPH_SCHEMA_VERSION,
        "cases": cases,
        "errors": errors,
    }


def _audit_orchestration_examples() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    errors: list[str] = []
    for example_id, graph in sorted(agent_orchestration_example_catalog().items()):
        case_errors: list[str] = []
        node_count = 0
        edge_count = 0
        parallel_group_count = 0
        try:
            canonical = validate_agent_orchestration_graph(graph)
            compiled = compile_agent_orchestration_graph(canonical)
            lowered = validate_graph_definition(lower_agent_orchestration_graph_to_task_graph(canonical))
            relifted = validate_agent_orchestration_graph(lift_task_graph_to_agent_orchestration_graph(lowered))
            source_signature = _graph_signature(canonical)
            relifted_signature = _graph_signature(relifted)
            node_count = len(list(canonical.get("nodes") or []))
            edge_count = len(list(canonical.get("edges") or []))
            parallel_group_count = int(dict(compiled.get("topology") or {}).get("parallel_group_count") or 0)
            if source_signature != relifted_signature:
                case_errors.append("lower/lift changed graph identity, topology, or entry-node ownership")
            if compiled.get("graph_id") != canonical.get("graph_id"):
                case_errors.append("compiled plan graph_id does not match canonical graph")
        except (TypeError, ValueError) as exc:
            case_errors.append(f"contract field drift or conversion failure: {exc}")
        if case_errors:
            errors.extend(f"{example_id}: {message}" for message in case_errors)
        cases.append(
            {
                "example_id": example_id,
                "status": "pass" if not case_errors else "fail",
                "node_count": node_count,
                "edge_count": edge_count,
                "parallel_group_count": parallel_group_count,
                "errors": case_errors,
            }
        )
    return {
        "contract": "canonical_orchestration_to_persisted_task_graph",
        "owner": "agent_orchestration_contract + agent_orchestration_compiler",
        "status": "pass" if not errors else "fail",
        "canonical_schema_version": AGENT_ORCHESTRATION_SCHEMA_VERSION,
        "cases": cases,
        "errors": errors,
    }


def audit_contract_boundaries() -> dict[str, Any]:
    checks = [
        _audit_stability_ownership(),
        _audit_provider_transport_registry(),
        _audit_task_graph_fixtures(),
        _audit_orchestration_examples(),
    ]
    errors = [error for check in checks for error in list(check.get("errors") or [])]
    return {
        "schema_version": CONTRACT_BOUNDARY_AUDIT_SCHEMA_VERSION,
        "status": "pass" if not errors else "fail",
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "passed_check_count": sum(check.get("status") == "pass" for check in checks),
            "error_count": len(errors),
            "task_graph_fixture_count": len(task_graph_fixture_catalog()),
            "orchestration_example_count": len(agent_orchestration_example_catalog()),
        },
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify AstraBridge provider and task-graph contract boundaries.")
    parser.add_argument("--output", type=Path, help="Optional JSON report destination.")
    args = parser.parse_args(argv)
    report = audit_contract_boundaries()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
