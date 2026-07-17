from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .node_type_registry import task_graph_node_kind_ids
from .security import DESKTOP_KEY_PATH_RE, SECRET_RE, SecurityError, resolve_under


TASK_GRAPH_SCHEMA_VERSION = "astrabridge-task-graph-v1"
TASK_GRAPH_RUN_SCHEMA_VERSION = "astrabridge-task-graph-run-v1"
TASK_GRAPH_SCHEMA_DEFINITIONS_VERSION = "astrabridge-task-graph-schema-definitions-v1"

GRAPH_TEMPLATE_IDS = (
    "supervisor_worker_synthesizer",
    "fanout_fanin_research",
    "code_fix_test_review",
    "provider_update_smoke_gate",
    "document_extract_analyze_report",
    "multimodal_capability_adapter",
    "custom_blank_graph",
)
NODE_KINDS = task_graph_node_kind_ids()
NODE_DEFINITION_STATUSES = ("draft", "ready", "invalid", "disabled")
EDGE_TYPES = ("context_handoff", "artifact_handoff", "control_dependency", "approval_dependency", "fanout_branch", "fanin_merge")
EDGE_STATUSES = ("draft", "ready", "invalid", "disabled")
SPAWN_MODES = ("inline_lane", "isolated_lane", "subagent_worker", "manual_only")
HISTORY_MODES = ("none", "last_n_messages", "latest_summary_only", "latest_machine_result_only", "explicit_refs_only")
ARTIFACT_MODES = ("none", "explicit_artifacts", "latest_matching_kind", "required_output_only")
SUMMARY_STRATEGIES = ("no_summary", "human_summary_only", "machine_result_only", "human_and_machine")
ARTIFACT_KINDS = (
    "text_report",
    "structured_json",
    "code_diff",
    "test_report",
    "validation_report",
    "screenshot",
    "image",
    "audio",
    "video",
    "document_extract",
    "graph_definition",
    "run_summary",
    "approval_record",
    "diagnostic_bundle",
)
ARTIFACT_STATUSES = ("pending", "ready", "partial", "blocked", "redacted", "failed")
RUN_STATUSES = (
    "queued",
    "ready_for_dry_run",
    "dry_run_running",
    "dry_run_blocked",
    "dry_run_passed",
    "running",
    "paused_for_review",
    "needs_review",
    "partial",
    "cancelled",
    "failed",
    "completed",
    "rolled_back",
)
NODE_RUN_STATUSES = (
    "queued",
    "waiting_on_dependencies",
    "ready",
    "dry_run_blocked",
    "dry_run_passed",
    "running",
    "waiting_on_approval",
    "waiting_on_artifact",
    "needs_review",
    "partial",
    "skipped",
    "blocked",
    "cancelled",
    "failed",
    "completed",
)
WORKER_ORIGINS = ("provider_lane", "codex_subagent", "manual", "automation", "fixture_runner")
RUN_EVENT_TYPES = (
    "run_created",
    "run_dry_run_started",
    "run_dry_run_completed",
    "node_queued",
    "node_started",
    "node_progress",
    "node_completed",
    "node_blocked",
    "node_failed",
    "node_cancelled",
    "node_needs_review",
    "artifact_created",
    "artifact_redacted",
    "approval_requested",
    "approval_resolved",
    "handoff_created",
    "run_cancel_requested",
    "run_cancelled",
    "run_completed",
    "run_failed",
    "run_needs_review",
    "run_rolled_back",
)
APPROVAL_STATES = ("not_required", "pending", "approved", "rejected", "expired")
REVIEW_KINDS = ("human_gate", "policy_gate", "provider_call_gate", "filesystem_write_gate", "external_write_gate", "install_gate")
ALLOWED_PRODUCT_PATH_PREFIXES = ("PRIVATE/", ".astrabridge/")

_FIXTURE_TASK_ID = "task_graph_fixture_task"
_FIXTURE_CREATED_AT = "2026-07-07T00:00:00+09:00"
_FIXTURE_UPDATED_AT = "2026-07-07T00:05:00+09:00"


def task_graph_schema_definitions() -> dict[str, Any]:
    return {
        "schema_version": TASK_GRAPH_SCHEMA_DEFINITIONS_VERSION,
        "contract_versions": {
            "graph_definition": TASK_GRAPH_SCHEMA_VERSION,
            "task_graph_run": TASK_GRAPH_RUN_SCHEMA_VERSION,
        },
        "definitions": {
            "graph_definition": {
                "required": [
                    "schema_version",
                    "graph_id",
                    "task_id",
                    "title",
                    "template_id",
                    "status",
                    "nodes",
                    "edges",
                    "graph_policy",
                    "created_at",
                    "updated_at",
                    "state_version",
                ]
            },
            "agent_node": {"allowed_kinds": list(NODE_KINDS), "allowed_statuses": list(NODE_DEFINITION_STATUSES)},
            "agent_edge": {"allowed_types": list(EDGE_TYPES), "allowed_statuses": list(EDGE_STATUSES)},
            "context_policy": {
                "allowed_history_modes": list(HISTORY_MODES),
                "allowed_artifact_modes": list(ARTIFACT_MODES),
                "allowed_summary_strategies": list(SUMMARY_STRATEGIES),
            },
            "artifact_ref": {"allowed_kinds": list(ARTIFACT_KINDS), "allowed_statuses": list(ARTIFACT_STATUSES)},
            "task_graph_run": {"allowed_statuses": list(RUN_STATUSES)},
            "node_run_state": {"allowed_statuses": list(NODE_RUN_STATUSES), "allowed_worker_origins": list(WORKER_ORIGINS)},
            "run_event": {"allowed_event_types": list(RUN_EVENT_TYPES)},
            "approval_state": {"allowed_states": list(APPROVAL_STATES), "allowed_review_kinds": list(REVIEW_KINDS)},
        },
    }


def task_graph_fixture_catalog() -> dict[str, dict[str, Any]]:
    fixtures = {
        "supervisor_worker_synthesizer": _supervisor_worker_synthesizer_fixture(),
        "fanout_fanin_research": _fanout_fanin_research_fixture(),
        "code_fix_test_review": _code_fix_test_review_fixture(),
        "provider_update_smoke_gate": _provider_update_smoke_gate_fixture(),
        "document_extract_analyze_report": _document_extract_analyze_report_fixture(),
        "multimodal_capability_adapter": _multimodal_capability_adapter_fixture(),
        "custom_blank_graph": _custom_blank_graph_fixture(),
    }
    for template_id, graph in fixtures.items():
        validate_graph_definition(graph)
        if graph["template_id"] != template_id:
            raise ValueError(f"Fixture template mismatch: {template_id}")
    return fixtures


def load_task_graph_fixture(template_id: str) -> dict[str, Any]:
    try:
        graph = task_graph_fixture_catalog()[str(template_id)]
    except KeyError as exc:
        raise ValueError(f"Unknown task graph fixture: {template_id}") from exc
    return deepcopy(graph)


def task_graph_negative_fixture_catalog() -> dict[str, dict[str, Any]]:
    missing_context_graph = load_task_graph_fixture("supervisor_worker_synthesizer")
    missing_context_graph["edges"][0].pop("context_policy", None)

    unsafe_write_graph = load_task_graph_fixture("code_fix_test_review")
    code_fix = next(node for node in unsafe_write_graph["nodes"] if node["node_id"] == "node_code_fix")
    code_fix["execution_policy"]["requires_human_approval"] = False
    code_fix.pop("approval_gate", None)

    missing_machine_schema_graph = load_task_graph_fixture("fanout_fanin_research")
    researcher = next(node for node in missing_machine_schema_graph["nodes"] if node["node_id"] == "node_research_a")
    researcher["output_contract"].pop("machine_result_schema", None)
    researcher["output_contract"]["artifact_only"] = False

    invalid_artifact_run = load_task_graph_run_fixture("document_extract_analyze_report")
    invalid_artifact_run["artifact_refs"].append(
        {
            "artifact_id": "artifact_outside_workspace",
            "artifact_kind": "document_extract",
            "task_id": _FIXTURE_TASK_ID,
            "run_id": invalid_artifact_run["run_id"],
            "source_node_id": "node_extract",
            "path": "C:/outside/secrets/report.json",
            "media_type": "application/json",
            "status": "ready",
            "created_at": _FIXTURE_CREATED_AT,
        }
    )

    return {
        "missing_context_policy": {
            "target": "graph_definition",
            "payload": missing_context_graph,
            "expected_error": "context_policy",
        },
        "unsafe_write_without_review": {
            "target": "graph_definition",
            "payload": unsafe_write_graph,
            "expected_error": "review path",
        },
        "missing_machine_result_schema": {
            "target": "graph_definition",
            "payload": missing_machine_schema_graph,
            "expected_error": "machine_result_schema",
        },
        "invalid_artifact_ref_path": {
            "target": "task_graph_run",
            "payload": invalid_artifact_run,
            "expected_error": "allowed workspace",
        },
    }


def load_negative_task_graph_fixture(case_id: str) -> dict[str, Any]:
    try:
        fixture = task_graph_negative_fixture_catalog()[str(case_id)]
    except KeyError as exc:
        raise ValueError(f"Unknown negative task graph fixture: {case_id}") from exc
    return deepcopy(fixture)


def load_task_graph_run_fixture(template_id: str) -> dict[str, Any]:
    graph = load_task_graph_fixture(template_id)
    run = {
        "schema_version": TASK_GRAPH_RUN_SCHEMA_VERSION,
        "run_id": f"graph-run-fixture-{template_id}",
        "graph_id": graph["graph_id"],
        "task_id": graph["task_id"],
        "trace_id": f"trace-{template_id}",
        "context_id": f"context-{template_id}",
        "status": "ready_for_dry_run",
        "entry_node_ids": list(dict(graph["graph_policy"]).get("entry_node_ids") or []),
        "node_run_states": [
            {
                "node_id": node["node_id"],
                "run_id": f"graph-run-fixture-{template_id}",
                "status": "ready" if node["node_id"] in list(dict(graph["graph_policy"]).get("entry_node_ids") or []) else "waiting_on_dependencies",
                "attempt_count": 0,
                "started_at": _FIXTURE_CREATED_AT,
                "updated_at": _FIXTURE_UPDATED_AT,
                "worker_origin": "fixture_runner",
                "warnings": [],
            }
            for node in graph["nodes"]
        ],
        "artifact_refs": [],
        "event_refs": [
            {
                "event_id": f"event-run-created-{template_id}",
                "run_id": f"graph-run-fixture-{template_id}",
                "task_id": graph["task_id"],
                "trace_id": f"trace-{template_id}",
                "event_type": "run_created",
                "created_at": _FIXTURE_CREATED_AT,
                "summary": "Fixture run created for contract validation.",
            }
        ],
        "approval_state": {"status": "not_required"},
        "run_policy_snapshot": {"mode": "fixture_only"},
        "created_at": _FIXTURE_CREATED_AT,
        "updated_at": _FIXTURE_UPDATED_AT,
        "state_version": 1,
    }
    return validate_task_graph_run(run, graph_definition=graph)


def validate_graph_definition(graph: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, dict):
        raise TypeError("Task graph definition must be a dict.")
    _reject_secret_like(graph, path="task_graph_definition")
    normalized = deepcopy(graph)
    _require_fields(
        normalized,
        "graph_definition",
        ("schema_version", "graph_id", "task_id", "title", "template_id", "status", "nodes", "edges", "graph_policy", "created_at", "updated_at", "state_version"),
    )
    if normalized["schema_version"] != TASK_GRAPH_SCHEMA_VERSION:
        raise ValueError("Unexpected task graph schema version.")
    _require_non_empty_string(normalized["graph_id"], field="graph_definition.graph_id")
    _require_non_empty_string(normalized["task_id"], field="graph_definition.task_id")
    _require_non_empty_string(normalized["title"], field="graph_definition.title")
    _require_enum(normalized["template_id"], field="graph_definition.template_id", allowed=GRAPH_TEMPLATE_IDS)
    _require_enum(normalized["status"], field="graph_definition.status", allowed=NODE_DEFINITION_STATUSES)
    if not isinstance(normalized["nodes"], list) or not normalized["nodes"]:
        raise ValueError("graph_definition.nodes must be a non-empty list.")
    if not isinstance(normalized["edges"], list):
        raise ValueError("graph_definition.edges must be a list.")
    if not isinstance(normalized["graph_policy"], dict):
        raise ValueError("graph_definition.graph_policy must be a dict.")
    if not isinstance(normalized["state_version"], int) or normalized["state_version"] <= 0:
        raise ValueError("graph_definition.state_version must be a positive integer.")

    node_ids: set[str] = set()
    for node in normalized["nodes"]:
        _validate_agent_node(node, graph_id=str(normalized["graph_id"]))
        node_id = str(node["node_id"])
        if node_id in node_ids:
            raise ValueError(f"graph_definition has duplicate node_id: {node_id}")
        node_ids.add(node_id)

    edge_ids: set[str] = set()
    for edge in normalized["edges"]:
        _validate_agent_edge(edge, graph_id=str(normalized["graph_id"]), known_node_ids=node_ids)
        edge_id = str(edge["edge_id"])
        if edge_id in edge_ids:
            raise ValueError(f"graph_definition has duplicate edge_id: {edge_id}")
        edge_ids.add(edge_id)

    entry_node_ids = _normalize_string_list(normalized["graph_policy"].get("entry_node_ids"), field="graph_policy.entry_node_ids", required=True)
    if not entry_node_ids:
        raise ValueError("graph_definition entry nodes must not be empty.")
    unknown_entry_ids = sorted(set(entry_node_ids).difference(node_ids))
    if unknown_entry_ids:
        raise ValueError(f"graph_definition entry nodes reference unknown node ids: {', '.join(unknown_entry_ids)}")
    normalized["graph_policy"]["entry_node_ids"] = entry_node_ids
    _reject_secret_like(normalized, path="task_graph_definition")
    return normalized


def validate_task_graph_run(
    run: dict[str, Any],
    *,
    graph_definition: dict[str, Any] | None = None,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    if not isinstance(run, dict):
        raise TypeError("Task graph run must be a dict.")
    _reject_secret_like(run, path="task_graph_run")
    normalized = deepcopy(run)
    # Tolerate the early draft top-level names from the plan artifact.
    if "node_run_states" not in normalized and "node_runs" in normalized:
        normalized["node_run_states"] = list(normalized.get("node_runs") or [])
    if "artifact_refs" not in normalized and "artifacts" in normalized:
        normalized["artifact_refs"] = list(normalized.get("artifacts") or [])
    if "event_refs" not in normalized and "events" in normalized:
        normalized["event_refs"] = list(normalized.get("events") or [])

    _require_fields(
        normalized,
        "task_graph_run",
        (
            "schema_version",
            "run_id",
            "graph_id",
            "task_id",
            "trace_id",
            "context_id",
            "status",
            "entry_node_ids",
            "node_run_states",
            "artifact_refs",
            "event_refs",
            "approval_state",
            "run_policy_snapshot",
            "created_at",
            "updated_at",
            "state_version",
        ),
    )
    if normalized["schema_version"] != TASK_GRAPH_RUN_SCHEMA_VERSION:
        raise ValueError("Unexpected task graph run schema version.")
    for field in ("run_id", "graph_id", "task_id", "trace_id", "context_id"):
        _require_non_empty_string(normalized[field], field=f"task_graph_run.{field}")
    _require_enum(normalized["status"], field="task_graph_run.status", allowed=RUN_STATUSES)
    if not isinstance(normalized["node_run_states"], list):
        raise ValueError("task_graph_run.node_run_states must be a list.")
    if not isinstance(normalized["artifact_refs"], list):
        raise ValueError("task_graph_run.artifact_refs must be a list.")
    if not isinstance(normalized["event_refs"], list):
        raise ValueError("task_graph_run.event_refs must be a list.")
    if not isinstance(normalized["run_policy_snapshot"], dict):
        raise ValueError("task_graph_run.run_policy_snapshot must be a dict.")
    if not isinstance(normalized["state_version"], int) or normalized["state_version"] <= 0:
        raise ValueError("task_graph_run.state_version must be a positive integer.")

    if graph_definition is not None:
        graph = validate_graph_definition(graph_definition)
        if normalized["graph_id"] != graph["graph_id"]:
            raise ValueError("task_graph_run.graph_id must match graph_definition.graph_id.")
        if normalized["task_id"] != graph["task_id"]:
            raise ValueError("task_graph_run.task_id must match graph_definition.task_id.")
        valid_node_ids = {str(node["node_id"]) for node in graph["nodes"]}
    else:
        valid_node_ids = set(_normalize_string_list(normalized["entry_node_ids"], field="task_graph_run.entry_node_ids", required=True))
        for item in list(normalized["node_run_states"] or []):
            if isinstance(item, dict):
                node_id = str(item.get("node_id") or "").strip()
                if node_id:
                    valid_node_ids.add(node_id)
    normalized["entry_node_ids"] = _normalize_string_list(normalized["entry_node_ids"], field="task_graph_run.entry_node_ids", required=True)

    for node_id in normalized["entry_node_ids"]:
        if node_id not in valid_node_ids:
            raise ValueError(f"task_graph_run.entry_node_ids references unknown node_id: {node_id}")

    seen_node_runs: set[str] = set()
    for item in normalized["node_run_states"]:
        _validate_node_run_state(item, run_id=str(normalized["run_id"]), known_node_ids=valid_node_ids)
        node_id = str(item["node_id"])
        if node_id in seen_node_runs:
            raise ValueError(f"task_graph_run has duplicate node_run_state for node_id: {node_id}")
        seen_node_runs.add(node_id)

    for artifact in normalized["artifact_refs"]:
        _validate_artifact_ref(artifact, run_id=str(normalized["run_id"]), task_id=str(normalized["task_id"]), workspace_root=workspace_root)

    for event in normalized["event_refs"]:
        _validate_run_event(event, run_id=str(normalized["run_id"]), task_id=str(normalized["task_id"]), trace_id=str(normalized["trace_id"]))

    _validate_approval_state(normalized["approval_state"])
    _reject_secret_like(normalized, path="task_graph_run")
    return normalized


def _validate_agent_node(node: Any, *, graph_id: str) -> None:
    data = _ensure_dict(node, "agent_node")
    _require_fields(data, "agent_node", ("node_id", "graph_id", "kind", "label", "agent_card_ref", "execution_policy", "output_contract", "position", "status"))
    _require_non_empty_string(data["node_id"], field="agent_node.node_id")
    if str(data["graph_id"]) != graph_id:
        raise ValueError(f"agent_node.graph_id must match graph_definition.graph_id for node {data.get('node_id')}.")
    _require_enum(data["kind"], field="agent_node.kind", allowed=NODE_KINDS)
    _require_non_empty_string(data["label"], field="agent_node.label")
    _require_non_empty_string(data["agent_card_ref"], field="agent_node.agent_card_ref")
    _require_enum(data["status"], field="agent_node.status", allowed=NODE_DEFINITION_STATUSES)
    _validate_execution_policy(data["execution_policy"], node_id=str(data["node_id"]))
    _validate_output_contract(data["output_contract"], node_id=str(data["node_id"]))
    _validate_position(data["position"], label=f"agent_node.position[{data['node_id']}]")
    if "approval_gate" in data:
        _validate_approval_gate(data["approval_gate"], node_id=str(data["node_id"]))
    _validate_high_risk_review_path(data)


def _validate_agent_edge(edge: Any, *, graph_id: str, known_node_ids: set[str]) -> None:
    data = _ensure_dict(edge, "agent_edge")
    _require_fields(data, "agent_edge", ("edge_id", "graph_id", "from_node_id", "to_node_id", "edge_type", "context_policy", "status"))
    _require_non_empty_string(data["edge_id"], field="agent_edge.edge_id")
    if str(data["graph_id"]) != graph_id:
        raise ValueError(f"agent_edge.graph_id must match graph_definition.graph_id for edge {data.get('edge_id')}.")
    _require_non_empty_string(data["from_node_id"], field="agent_edge.from_node_id")
    _require_non_empty_string(data["to_node_id"], field="agent_edge.to_node_id")
    _require_enum(data["edge_type"], field="agent_edge.edge_type", allowed=EDGE_TYPES)
    _require_enum(data["status"], field="agent_edge.status", allowed=EDGE_STATUSES)
    if str(data["from_node_id"]) not in known_node_ids or str(data["to_node_id"]) not in known_node_ids:
        raise ValueError(f"agent_edge {data['edge_id']} references unknown node ids.")
    _validate_context_policy(data["context_policy"], label=f"agent_edge.context_policy[{data['edge_id']}]")


def _validate_context_policy(value: Any, *, label: str) -> None:
    data = _ensure_dict(value, label)
    _require_fields(
        data,
        label,
        ("policy_id", "history_mode", "artifact_mode", "exclude_private_memory", "include_machine_results", "include_human_summaries"),
    )
    _require_non_empty_string(data["policy_id"], field=f"{label}.policy_id")
    _require_enum(data["history_mode"], field=f"{label}.history_mode", allowed=HISTORY_MODES)
    _require_enum(data["artifact_mode"], field=f"{label}.artifact_mode", allowed=ARTIFACT_MODES)
    _require_bool(data["exclude_private_memory"], field=f"{label}.exclude_private_memory")
    _require_bool(data["include_machine_results"], field=f"{label}.include_machine_results")
    _require_bool(data["include_human_summaries"], field=f"{label}.include_human_summaries")
    if not bool(data["exclude_private_memory"]):
        raise ValueError(f"{label} must set exclude_private_memory=true for worker-safe handoff.")
    if "summary_strategy" in data and data["summary_strategy"] is not None:
        _require_enum(data["summary_strategy"], field=f"{label}.summary_strategy", allowed=SUMMARY_STRATEGIES)
    if "history_length" in data and data["history_length"] is not None:
        if not isinstance(data["history_length"], int) or data["history_length"] < 0:
            raise ValueError(f"{label}.history_length must be a non-negative integer.")
    if "included_artifacts" in data and data["included_artifacts"] is not None:
        if not isinstance(data["included_artifacts"], list) or not all(isinstance(item, str) for item in data["included_artifacts"]):
            raise ValueError(f"{label}.included_artifacts must be a list of strings.")
    if "resource_refs" in data and data["resource_refs"] is not None:
        if not isinstance(data["resource_refs"], list) or not all(isinstance(item, str) for item in data["resource_refs"]):
            raise ValueError(f"{label}.resource_refs must be a list of strings.")


def _validate_execution_policy(value: Any, *, node_id: str) -> None:
    data = _ensure_dict(value, f"execution_policy[{node_id}]")
    _require_fields(
        data,
        f"execution_policy[{node_id}]",
        ("spawn_mode", "retry_policy", "timeout_ms", "allow_provider_calls", "allow_code_changes", "allow_install", "requires_human_approval"),
    )
    _require_enum(data["spawn_mode"], field=f"execution_policy[{node_id}].spawn_mode", allowed=SPAWN_MODES)
    if not isinstance(data["retry_policy"], dict):
        raise ValueError(f"execution_policy[{node_id}].retry_policy must be a dict.")
    if not isinstance(data["timeout_ms"], int) or data["timeout_ms"] <= 0:
        raise ValueError(f"execution_policy[{node_id}].timeout_ms must be a positive integer.")
    _require_bool(data["allow_provider_calls"], field=f"execution_policy[{node_id}].allow_provider_calls")
    _require_bool(data["allow_code_changes"], field=f"execution_policy[{node_id}].allow_code_changes")
    _require_bool(data["allow_install"], field=f"execution_policy[{node_id}].allow_install")
    _require_bool(data["requires_human_approval"], field=f"execution_policy[{node_id}].requires_human_approval")


def _validate_output_contract(value: Any, *, node_id: str) -> None:
    data = _ensure_dict(value, f"output_contract[{node_id}]")
    _require_fields(data, f"output_contract[{node_id}]", ("human_summary_required", "artifact_outputs"))
    _require_bool(data["human_summary_required"], field=f"output_contract[{node_id}].human_summary_required")
    if not isinstance(data["artifact_outputs"], list):
        raise ValueError(f"output_contract[{node_id}].artifact_outputs must be a list.")
    artifact_only = bool(data.get("artifact_only"))
    machine_result_schema = data.get("machine_result_schema")
    if artifact_only:
        if machine_result_schema in (None, {}):
            return
        if not isinstance(machine_result_schema, dict):
            raise ValueError(f"output_contract[{node_id}].machine_result_schema must be a dict when present.")
        return
    if not isinstance(machine_result_schema, dict) or not machine_result_schema:
        raise ValueError(f"output_contract[{node_id}] must declare machine_result_schema unless artifact_only=true.")


def _validate_position(value: Any, *, label: str) -> None:
    data = _ensure_dict(value, label)
    _require_fields(data, label, ("x", "y"))
    for axis in ("x", "y"):
        if not isinstance(data[axis], (int, float)):
            raise ValueError(f"{label}.{axis} must be numeric.")


def _validate_approval_gate(value: Any, *, node_id: str) -> None:
    data = _ensure_dict(value, f"approval_gate[{node_id}]")
    _require_fields(data, f"approval_gate[{node_id}]", ("review_kind",))
    _require_enum(data["review_kind"], field=f"approval_gate[{node_id}].review_kind", allowed=REVIEW_KINDS)


def _validate_high_risk_review_path(node: dict[str, Any]) -> None:
    policy = dict(node["execution_policy"])
    high_risk = bool(policy.get("allow_code_changes")) or bool(policy.get("allow_install"))
    if not high_risk:
        return
    if bool(policy.get("requires_human_approval")):
        return
    if isinstance(node.get("approval_gate"), dict) and str(node["approval_gate"].get("review_kind") or "") in REVIEW_KINDS:
        return
    raise ValueError(f"agent_node {node['node_id']} requests high-risk execution without a review path.")


def _validate_node_run_state(value: Any, *, run_id: str, known_node_ids: set[str]) -> None:
    data = _ensure_dict(value, "node_run_state")
    _require_fields(data, "node_run_state", ("node_id", "run_id", "status", "attempt_count", "started_at", "updated_at"))
    _require_non_empty_string(data["node_id"], field="node_run_state.node_id")
    if str(data["node_id"]) not in known_node_ids:
        raise ValueError(f"node_run_state references unknown node_id: {data['node_id']}")
    if str(data["run_id"]) != run_id:
        raise ValueError("node_run_state.run_id must match task_graph_run.run_id.")
    _require_enum(data["status"], field="node_run_state.status", allowed=NODE_RUN_STATUSES)
    if not isinstance(data["attempt_count"], int) or data["attempt_count"] < 0:
        raise ValueError("node_run_state.attempt_count must be a non-negative integer.")
    if "worker_origin" in data and data["worker_origin"] is not None:
        _require_enum(data["worker_origin"], field="node_run_state.worker_origin", allowed=WORKER_ORIGINS)


def _validate_artifact_ref(value: Any, *, run_id: str, task_id: str, workspace_root: str | Path | None) -> None:
    data = _ensure_dict(value, "artifact_ref")
    _require_fields(data, "artifact_ref", ("artifact_id", "artifact_kind", "task_id", "run_id", "source_node_id", "path", "media_type", "status", "created_at"))
    _require_non_empty_string(data["artifact_id"], field="artifact_ref.artifact_id")
    _require_enum(data["artifact_kind"], field="artifact_ref.artifact_kind", allowed=ARTIFACT_KINDS)
    if str(data["task_id"]) != task_id:
        raise ValueError("artifact_ref.task_id must match task_graph_run.task_id.")
    if str(data["run_id"]) != run_id:
        raise ValueError("artifact_ref.run_id must match task_graph_run.run_id.")
    _require_non_empty_string(data["source_node_id"], field="artifact_ref.source_node_id")
    _require_non_empty_string(data["path"], field="artifact_ref.path")
    _require_non_empty_string(data["media_type"], field="artifact_ref.media_type")
    _require_enum(data["status"], field="artifact_ref.status", allowed=ARTIFACT_STATUSES)
    _validate_artifact_path(str(data["path"]), workspace_root=workspace_root)


def _validate_artifact_path(path_text: str, *, workspace_root: str | Path | None) -> None:
    normalized_path = str(path_text).replace("\\", "/").strip()
    if not normalized_path:
        raise ValueError("artifact_ref.path must not be empty.")
    if workspace_root is None:
        if normalized_path.startswith("/"):
            raise ValueError("artifact_ref.path must be workspace-relative or product-controlled when workspace_root is not provided.")
        if not normalized_path.startswith(ALLOWED_PRODUCT_PATH_PREFIXES):
            raise ValueError("artifact_ref.path must stay under an allowed workspace or product-controlled path.")
        return
    try:
        resolved = resolve_under(Path(workspace_root), path_text)
    except SecurityError as exc:
        raise ValueError("artifact_ref.path must stay under an allowed workspace or product-controlled path.") from exc
    relative = resolved.relative_to(Path(workspace_root).resolve()).as_posix()
    if not relative.startswith(ALLOWED_PRODUCT_PATH_PREFIXES):
        raise ValueError("artifact_ref.path must stay under an allowed workspace or product-controlled path.")


def _validate_run_event(value: Any, *, run_id: str, task_id: str, trace_id: str) -> None:
    data = _ensure_dict(value, "run_event")
    _require_fields(data, "run_event", ("event_id", "run_id", "task_id", "trace_id", "event_type", "created_at"))
    _require_non_empty_string(data["event_id"], field="run_event.event_id")
    if str(data["run_id"]) != run_id:
        raise ValueError("run_event.run_id must match task_graph_run.run_id.")
    if str(data["task_id"]) != task_id:
        raise ValueError("run_event.task_id must match task_graph_run.task_id.")
    if str(data["trace_id"]) != trace_id:
        raise ValueError("run_event.trace_id must match task_graph_run.trace_id.")
    _require_enum(data["event_type"], field="run_event.event_type", allowed=RUN_EVENT_TYPES)


def _validate_approval_state(value: Any) -> None:
    data = _ensure_dict(value, "approval_state")
    _require_fields(data, "approval_state", ("status",))
    _require_enum(data["status"], field="approval_state.status", allowed=APPROVAL_STATES)


def _ensure_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict.")
    return value


def _require_fields(data: dict[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if field not in data:
            raise ValueError(f"{label} is missing required field: {field}")


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string.")
    text = value.strip()
    if not text:
        raise ValueError(f"{field} must not be empty.")
    return text


def _require_enum(value: Any, *, field: str, allowed: tuple[str, ...]) -> str:
    text = _require_non_empty_string(value, field=field)
    if text not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
    return text


def _require_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a bool.")
    return value


def _normalize_string_list(value: Any, *, field: str, required: bool = False) -> list[str]:
    if value is None:
        if required:
            raise ValueError(f"{field} is required.")
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _require_non_empty_string(item, field=field)
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized


def _reject_secret_like(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_secret_like(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_like(child, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if DESKTOP_KEY_PATH_RE.search(value) or SECRET_RE.search(value):
        raise SecurityError(f"Secret-like content detected in {path}")


def _fixture_context_policy(policy_id: str, *, history_mode: str = "latest_summary_only", artifact_mode: str = "required_output_only") -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "history_mode": history_mode,
        "artifact_mode": artifact_mode,
        "exclude_private_memory": True,
        "include_machine_results": True,
        "include_human_summaries": True,
        "summary_strategy": "human_and_machine",
    }


def _fixture_execution_policy(
    *,
    spawn_mode: str = "isolated_lane",
    allow_provider_calls: bool = True,
    allow_code_changes: bool = False,
    allow_install: bool = False,
    requires_human_approval: bool = False,
) -> dict[str, Any]:
    return {
        "spawn_mode": spawn_mode,
        "retry_policy": {"max_attempts": 1},
        "timeout_ms": 120000,
        "allow_provider_calls": allow_provider_calls,
        "allow_code_changes": allow_code_changes,
        "allow_install": allow_install,
        "requires_human_approval": requires_human_approval,
    }


def _fixture_output_contract(
    *,
    artifact_outputs: list[str],
    machine_required_fields: list[str] | None = None,
    artifact_only: bool = False,
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "human_summary_required": True,
        "artifact_outputs": list(artifact_outputs),
        "artifact_only": artifact_only,
    }
    if not artifact_only:
        contract["machine_result_schema"] = {
            "type": "object",
            "required": list(machine_required_fields or ["status"]),
        }
    return contract


def _fixture_node(
    *,
    graph_id: str,
    node_id: str,
    kind: str,
    label: str,
    x: int,
    y: int,
    agent_card_ref: str,
    execution_policy: dict[str, Any],
    output_contract: dict[str, Any],
    approval_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node = {
        "node_id": node_id,
        "graph_id": graph_id,
        "kind": kind,
        "label": label,
        "agent_card_ref": agent_card_ref,
        "execution_policy": execution_policy,
        "output_contract": output_contract,
        "position": {"x": x, "y": y},
        "status": "ready",
    }
    if approval_gate is not None:
        node["approval_gate"] = approval_gate
    return node


def _fixture_edge(*, graph_id: str, edge_id: str, from_node_id: str, to_node_id: str, edge_type: str) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "graph_id": graph_id,
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "edge_type": edge_type,
        "context_policy": _fixture_context_policy(f"policy_{edge_id}"),
        "status": "ready",
    }


def _base_graph(graph_id: str, title: str, template_id: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], *, entry_node_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": TASK_GRAPH_SCHEMA_VERSION,
        "graph_id": graph_id,
        "task_id": _FIXTURE_TASK_ID,
        "title": title,
        "template_id": template_id,
        "status": "ready",
        "nodes": nodes,
        "edges": edges,
        "graph_policy": {"entry_node_ids": entry_node_ids},
        "created_at": _FIXTURE_CREATED_AT,
        "updated_at": _FIXTURE_UPDATED_AT,
        "state_version": 1,
    }


def _supervisor_worker_synthesizer_fixture() -> dict[str, Any]:
    graph_id = "graph_fixture_supervisor_worker_synthesizer"
    nodes = [
        _fixture_node(
            graph_id=graph_id,
            node_id="node_supervisor",
            kind="supervisor",
            label="Supervisor",
            x=80,
            y=120,
            agent_card_ref="agent_card_supervisor",
            execution_policy=_fixture_execution_policy(spawn_mode="inline_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["structured_json"], machine_required_fields=["plan", "next_workers"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_worker",
            kind="worker",
            label="Worker",
            x=360,
            y=120,
            agent_card_ref="agent_card_worker",
            execution_policy=_fixture_execution_policy(spawn_mode="subagent_worker"),
            output_contract=_fixture_output_contract(artifact_outputs=["text_report"], machine_required_fields=["result", "confidence"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_synth",
            kind="synthesizer",
            label="Synthesizer",
            x=640,
            y=120,
            agent_card_ref="agent_card_synthesizer",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["run_summary"], machine_required_fields=["summary", "decision"]),
        ),
    ]
    edges = [
        _fixture_edge(graph_id=graph_id, edge_id="edge_supervisor_worker", from_node_id="node_supervisor", to_node_id="node_worker", edge_type="context_handoff"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_worker_synth", from_node_id="node_worker", to_node_id="node_synth", edge_type="artifact_handoff"),
    ]
    return _base_graph(graph_id, "Supervisor / Worker / Synthesizer", "supervisor_worker_synthesizer", nodes, edges, entry_node_ids=["node_supervisor"])


def _fanout_fanin_research_fixture() -> dict[str, Any]:
    graph_id = "graph_fixture_fanout_fanin_research"
    nodes = [
        _fixture_node(
            graph_id=graph_id,
            node_id="node_supervisor",
            kind="supervisor",
            label="Research Planner",
            x=80,
            y=160,
            agent_card_ref="agent_card_research_supervisor",
            execution_policy=_fixture_execution_policy(spawn_mode="inline_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["structured_json"], machine_required_fields=["questions", "branches"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_research_a",
            kind="worker",
            label="Research Branch A",
            x=320,
            y=80,
            agent_card_ref="agent_card_research_worker",
            execution_policy=_fixture_execution_policy(spawn_mode="subagent_worker"),
            output_contract=_fixture_output_contract(artifact_outputs=["text_report"], machine_required_fields=["findings", "sources"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_research_b",
            kind="worker",
            label="Research Branch B",
            x=320,
            y=240,
            agent_card_ref="agent_card_research_worker",
            execution_policy=_fixture_execution_policy(spawn_mode="subagent_worker"),
            output_contract=_fixture_output_contract(artifact_outputs=["text_report"], machine_required_fields=["findings", "sources"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_merge",
            kind="synthesizer",
            label="Research Synthesizer",
            x=620,
            y=160,
            agent_card_ref="agent_card_research_synthesizer",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["run_summary"], machine_required_fields=["synthesis", "gaps"]),
        ),
    ]
    edges = [
        _fixture_edge(graph_id=graph_id, edge_id="edge_plan_a", from_node_id="node_supervisor", to_node_id="node_research_a", edge_type="fanout_branch"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_plan_b", from_node_id="node_supervisor", to_node_id="node_research_b", edge_type="fanout_branch"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_a_merge", from_node_id="node_research_a", to_node_id="node_merge", edge_type="fanin_merge"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_b_merge", from_node_id="node_research_b", to_node_id="node_merge", edge_type="fanin_merge"),
    ]
    return _base_graph(graph_id, "Fan-out / Fan-in Research", "fanout_fanin_research", nodes, edges, entry_node_ids=["node_supervisor"])


def _code_fix_test_review_fixture() -> dict[str, Any]:
    graph_id = "graph_fixture_code_fix_test_review"
    nodes = [
        _fixture_node(
            graph_id=graph_id,
            node_id="node_plan_fix",
            kind="supervisor",
            label="Plan Fix",
            x=60,
            y=160,
            agent_card_ref="agent_card_code_supervisor",
            execution_policy=_fixture_execution_policy(spawn_mode="inline_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["structured_json"], machine_required_fields=["files", "approach"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_code_fix",
            kind="worker",
            label="Apply Code Fix",
            x=300,
            y=160,
            agent_card_ref="agent_card_code_worker",
            execution_policy=_fixture_execution_policy(
                spawn_mode="subagent_worker",
                allow_provider_calls=True,
                allow_code_changes=True,
                requires_human_approval=True,
            ),
            output_contract=_fixture_output_contract(artifact_outputs=["code_diff"], machine_required_fields=["changed_files", "summary"]),
            approval_gate={"review_kind": "filesystem_write_gate"},
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_test",
            kind="validator",
            label="Run Tests",
            x=540,
            y=80,
            agent_card_ref="agent_card_test_worker",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["test_report"], machine_required_fields=["status", "failures"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_review",
            kind="reviewer",
            label="Review",
            x=540,
            y=240,
            agent_card_ref="agent_card_review_worker",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["validation_report"], machine_required_fields=["decision", "issues"]),
        ),
    ]
    edges = [
        _fixture_edge(graph_id=graph_id, edge_id="edge_plan_fix", from_node_id="node_plan_fix", to_node_id="node_code_fix", edge_type="context_handoff"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_fix_test", from_node_id="node_code_fix", to_node_id="node_test", edge_type="artifact_handoff"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_fix_review", from_node_id="node_code_fix", to_node_id="node_review", edge_type="artifact_handoff"),
    ]
    return _base_graph(graph_id, "Code Fix / Test / Review", "code_fix_test_review", nodes, edges, entry_node_ids=["node_plan_fix"])


def _provider_update_smoke_gate_fixture() -> dict[str, Any]:
    graph_id = "graph_fixture_provider_update_smoke_gate"
    nodes = [
        _fixture_node(
            graph_id=graph_id,
            node_id="node_discover",
            kind="extractor",
            label="Discover Provider Update",
            x=80,
            y=160,
            agent_card_ref="agent_card_provider_discovery",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["structured_json"], machine_required_fields=["provider_changes", "candidate_models"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_smoke",
            kind="validator",
            label="Generate Smoke Matrix",
            x=340,
            y=160,
            agent_card_ref="agent_card_provider_smoke",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["validation_report"], machine_required_fields=["matrix", "blocked_cases"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_gate",
            kind="gate",
            label="Manual Promotion Gate",
            x=620,
            y=160,
            agent_card_ref="agent_card_manual_gate",
            execution_policy=_fixture_execution_policy(spawn_mode="manual_only", allow_provider_calls=False, requires_human_approval=True),
            output_contract=_fixture_output_contract(artifact_outputs=["approval_record"], machine_required_fields=["decision", "notes"]),
            approval_gate={"review_kind": "provider_call_gate"},
        ),
    ]
    edges = [
        _fixture_edge(graph_id=graph_id, edge_id="edge_discover_smoke", from_node_id="node_discover", to_node_id="node_smoke", edge_type="artifact_handoff"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_smoke_gate", from_node_id="node_smoke", to_node_id="node_gate", edge_type="approval_dependency"),
    ]
    return _base_graph(graph_id, "Provider Update / Smoke / Gate", "provider_update_smoke_gate", nodes, edges, entry_node_ids=["node_discover"])


def _document_extract_analyze_report_fixture() -> dict[str, Any]:
    graph_id = "graph_fixture_document_extract_analyze_report"
    nodes = [
        _fixture_node(
            graph_id=graph_id,
            node_id="node_extract",
            kind="extractor",
            label="Extract Document",
            x=80,
            y=160,
            agent_card_ref="agent_card_document_extractor",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["document_extract"], machine_required_fields=["sections", "entities"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_analyze",
            kind="worker",
            label="Analyze Extract",
            x=340,
            y=160,
            agent_card_ref="agent_card_document_analyst",
            execution_policy=_fixture_execution_policy(spawn_mode="subagent_worker"),
            output_contract=_fixture_output_contract(artifact_outputs=["structured_json"], machine_required_fields=["analysis", "confidence"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_report",
            kind="synthesizer",
            label="Write Report",
            x=620,
            y=160,
            agent_card_ref="agent_card_document_reporter",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["text_report"], machine_required_fields=["report", "recommendations"]),
        ),
    ]
    edges = [
        _fixture_edge(graph_id=graph_id, edge_id="edge_extract_analyze", from_node_id="node_extract", to_node_id="node_analyze", edge_type="artifact_handoff"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_analyze_report", from_node_id="node_analyze", to_node_id="node_report", edge_type="artifact_handoff"),
    ]
    return _base_graph(graph_id, "Document Extract / Analyze / Report", "document_extract_analyze_report", nodes, edges, entry_node_ids=["node_extract"])


def _multimodal_capability_adapter_fixture() -> dict[str, Any]:
    graph_id = "graph_fixture_multimodal_capability_adapter"
    nodes = [
        _fixture_node(
            graph_id=graph_id,
            node_id="node_probe_input",
            kind="extractor",
            label="Probe Input Capability",
            x=80,
            y=160,
            agent_card_ref="agent_card_multimodal_probe",
            execution_policy=_fixture_execution_policy(spawn_mode="inline_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["structured_json"], machine_required_fields=["input_modes", "provider_gaps"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_adapt_contract",
            kind="worker",
            label="Adapt Input Contract",
            x=340,
            y=160,
            agent_card_ref="agent_card_multimodal_adapter",
            execution_policy=_fixture_execution_policy(spawn_mode="subagent_worker"),
            output_contract=_fixture_output_contract(artifact_outputs=["image", "audio"], machine_required_fields=["adapted_prompt", "message_parts"]),
        ),
        _fixture_node(
            graph_id=graph_id,
            node_id="node_verify_output",
            kind="validator",
            label="Verify Output Mode",
            x=600,
            y=160,
            agent_card_ref="agent_card_multimodal_validator",
            execution_policy=_fixture_execution_policy(spawn_mode="isolated_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["validation_report"], machine_required_fields=["supported_outputs", "fallback_needed"]),
        ),
    ]
    edges = [
        _fixture_edge(graph_id=graph_id, edge_id="edge_probe_adapt", from_node_id="node_probe_input", to_node_id="node_adapt_contract", edge_type="artifact_handoff"),
        _fixture_edge(graph_id=graph_id, edge_id="edge_adapt_verify", from_node_id="node_adapt_contract", to_node_id="node_verify_output", edge_type="artifact_handoff"),
    ]
    return _base_graph(graph_id, "Multimodal Capability Adapter", "multimodal_capability_adapter", nodes, edges, entry_node_ids=["node_probe_input"])


def _custom_blank_graph_fixture() -> dict[str, Any]:
    graph_id = "graph_fixture_custom_blank_graph"
    nodes = [
        _fixture_node(
            graph_id=graph_id,
            node_id="node_start_here",
            kind="artifact_source",
            label="Start Here",
            x=140,
            y=180,
            agent_card_ref="agent_card_blank_seed",
            execution_policy=_fixture_execution_policy(spawn_mode="inline_lane"),
            output_contract=_fixture_output_contract(artifact_outputs=["structured_json"], machine_required_fields=["goal", "next_nodes"]),
        ),
    ]
    edges: list[dict[str, Any]] = []
    return _base_graph(graph_id, "Custom Blank Graph", "custom_blank_graph", nodes, edges, entry_node_ids=["node_start_here"])
