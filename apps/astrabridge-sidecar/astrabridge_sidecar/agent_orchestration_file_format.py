from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .agent_orchestration_contract import (
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    validate_agent_orchestration_graph,
)


AGENT_ORCHESTRATION_FILE_FORMAT_VERSION = "astrabridge-agent-orchestration-file-v1"
AGENT_ORCHESTRATION_FILE_EXTENSIONS = (".json",)
SOURCE_OWNED_DERIVED_NODE_FIELDS = (
    "resolved_node_type_id",
    "resolved_node_type_version",
    "node_type_registry_fingerprint",
)
EXAMPLE_GRAPH_IDS = (
    "supervisor_worker_synthesizer",
    "code_fix_review",
    "provider_update_smoke",
    "fanout_research_synthesis",
    "multimodal_capability_adapter",
    "custom_blank_graph",
)


def parse_agent_orchestration_graph_text(text: str, *, source_name: str = "<memory>") -> dict[str, Any]:
    if not isinstance(text, str):
        raise TypeError("Agent orchestration graph text must be a string.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source_name} is not valid JSON: {exc.msg}") from exc
    return source_owned_agent_orchestration_graph(payload)


def serialize_agent_orchestration_graph(graph: dict[str, Any]) -> str:
    normalized = source_owned_agent_orchestration_graph(graph)
    return json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"


def load_agent_orchestration_graph_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    _require_supported_extension(file_path)
    return parse_agent_orchestration_graph_text(file_path.read_text(encoding="utf-8"), source_name=str(file_path))


def write_agent_orchestration_graph_file(path: str | Path, graph: dict[str, Any]) -> Path:
    file_path = Path(path)
    _require_supported_extension(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(serialize_agent_orchestration_graph(graph), encoding="utf-8")
    return file_path


def agent_orchestration_file_format_spec() -> dict[str, Any]:
    return {
        "format_version": AGENT_ORCHESTRATION_FILE_FORMAT_VERSION,
        "schema_version": AGENT_ORCHESTRATION_SCHEMA_VERSION,
        "extensions": list(AGENT_ORCHESTRATION_FILE_EXTENSIONS),
        "content_type": "application/json",
    }


def agent_orchestration_example_catalog() -> dict[str, dict[str, Any]]:
    examples = {
        "supervisor_worker_synthesizer": _supervisor_worker_synthesizer_example(),
        "code_fix_review": _code_fix_review_example(),
        "provider_update_smoke": _provider_update_smoke_example(),
        "fanout_research_synthesis": _fanout_research_synthesis_example(),
        "multimodal_capability_adapter": _multimodal_capability_adapter_example(),
        "custom_blank_graph": _custom_blank_graph_example(),
    }
    for graph in examples.values():
        validate_agent_orchestration_graph(graph)
    return {key: deepcopy(value) for key, value in examples.items()}


def load_agent_orchestration_example(example_id: str) -> dict[str, Any]:
    try:
        graph = agent_orchestration_example_catalog()[str(example_id)]
    except KeyError as exc:
        raise ValueError(f"Unknown agent orchestration example: {example_id}") from exc
    return deepcopy(graph)


def source_owned_agent_orchestration_graph(graph: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_agent_orchestration_graph(graph)
    source_owned = deepcopy(normalized)
    for node in list(source_owned.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        for field in SOURCE_OWNED_DERIVED_NODE_FIELDS:
            node.pop(field, None)
    return source_owned


def _require_supported_extension(path: Path) -> None:
    if path.suffix.lower() not in AGENT_ORCHESTRATION_FILE_EXTENSIONS:
        raise ValueError(
            "Unsupported agent orchestration graph file extension. "
            f"Allowed: {', '.join(AGENT_ORCHESTRATION_FILE_EXTENSIONS)}"
        )


def _base_graph(*, graph_id: str, title: str, template_id: str, tags: list[str], entry_node_ids: list[str], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], schema_registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": AGENT_ORCHESTRATION_SCHEMA_VERSION,
        "graph_id": graph_id,
        "task_id": "task_example",
        "title": title,
        "template_id": template_id,
        "status": "ready",
        "metadata": {
            "description": title,
            "tags": list(tags),
            "owners": [],
            "created_at": "2026-07-07T00:00:00+09:00",
            "updated_at": "2026-07-07T00:05:00+09:00",
        },
        "graph_policy": {
            "entry_node_ids": list(entry_node_ids),
            "max_depth": 2,
            "default_permission_mode": "ask",
            "default_collaboration_mode": "default",
            "default_execution_backend": "app_server",
            "requires_dry_run_before_live": True,
        },
        "nodes": nodes,
        "edges": edges,
        "schema_registry": deepcopy(schema_registry),
        "migration": {
            "source_kind": "native_authoring",
            "compiled_task_graph_version": "astrabridge-task-graph-v1",
            "compatibility": {
                "lowering_mode": "lossy_legacy_task_graph",
                "preserves_unknown_fields": False,
                "notes": [
                    "Canonical graphs remain the source of truth for GUI, code, dry-run, and runtime work.",
                    "Lowering into legacy task graphs is a compatibility shim while the generic scheduler is still under construction.",
                ],
            },
        },
        "state_version": 1,
    }


def _node(
    *,
    node_id: str,
    kind: str,
    role: str,
    label: str,
    card_ref: str,
    provider_id: str | None,
    model_id: str | None,
    prompt: str,
    tool_classes: list[str],
    output_mode: str,
    machine_result_schema_ref: str | None,
    artifact_specs: list[dict[str, str]],
    spawn_mode: str,
    timeout_ms: int,
    risk_class: str,
    allow_provider_calls: bool,
    allow_code_changes: bool,
    allow_install: bool,
    requires_human_approval: bool,
    x: int,
    y: int,
    approval_kind: str | None = None,
    input_ports: list[dict[str, Any]] | None = None,
    output_ports: list[dict[str, Any]] | None = None,
    input_mode: str = "task_context_and_typed_ports",
    input_port_ids: list[str] | None = None,
    capability_claims: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    routing: dict[str, Any] = {"selection_mode": "none"}
    if provider_id and model_id:
        routing = {"selection_mode": "explicit", "provider_id": provider_id, "model_id": model_id}
    if capability_claims:
        routing["capability_claims"] = deepcopy(capability_claims)
    effective_input_ports = deepcopy(input_ports) if input_ports is not None else [
        {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True}
    ]
    effective_output_ports = deepcopy(output_ports) if output_ports is not None else _infer_output_ports(
        machine_result_schema_ref=machine_result_schema_ref,
        artifact_specs=artifact_specs,
    )
    declared_input_port_ids = list(input_port_ids) if input_port_ids is not None else [str(item["port_id"]) for item in effective_input_ports]
    node = {
        "node_id": node_id,
        "kind": kind,
        "label": label,
        "role": role,
        "card_ref": card_ref,
        "routing": routing,
        "prompt": {"template_mode": "inline", "template": prompt},
        "tools": {"approval_mode": "ask", "allowed_tool_classes": list(tool_classes)},
        "ports": {
            "inputs": effective_input_ports,
            "outputs": effective_output_ports,
        },
        "input_contract": {"mode": input_mode, "port_ids": declared_input_port_ids},
        "output_contract": {
            "mode": output_mode,
            "machine_result_schema_ref": machine_result_schema_ref,
            "artifact_specs": deepcopy(artifact_specs),
            "human_summary_required": True,
        },
        "execution": {
            "spawn_mode": spawn_mode,
            "timeout_ms": timeout_ms,
            "retry_policy": {"max_attempts": 1},
            "execution_backend": "human_review" if spawn_mode == "manual_only" else "app_server",
            "collaboration_mode": "default",
            "subagent_policy": {
                "isolation_mode": "lane",
                "max_turns": 8,
                "allow_direct_teammate_messages": False,
                "share_worktree": False,
                "allow_nested_subagents": False,
            }
            if spawn_mode == "subagent_worker"
            else None,
        },
        "safety": {
            "risk_class": risk_class,
            "allow_provider_calls": allow_provider_calls,
            "allow_code_changes": allow_code_changes,
            "allow_install": allow_install,
            "requires_human_approval": requires_human_approval,
        },
        "ui": {"position": {"x": x, "y": y}, "layout_mode": "canvas"},
        "status": "ready",
    }
    if approval_kind:
        node["safety"]["approval_kind"] = approval_kind
    return node


def _edge(
    *,
    edge_id: str,
    from_node_id: str,
    to_node_id: str,
    edge_type: str,
    schema_ref: str,
    message_template: str,
    x: int,
    y: int,
    port_bindings: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "edge_type": edge_type,
        "handoff_contract": {
            "message_template": message_template,
            "message_part_modes": ["machine_result", "human_summary"],
            "required_output_schema_refs": [schema_ref],
            "port_bindings": deepcopy(port_bindings),
        },
        "context_policy": {
            "policy_id": f"policy_{edge_id}",
            "history_mode": "latest_summary_only",
            "artifact_mode": "required_output_only",
            "exclude_private_memory": True,
            "include_machine_results": True,
            "include_human_summaries": True,
            "summary_strategy": "human_and_machine",
        },
        "ui": {"position": {"x": x, "y": y}, "layout_mode": "canvas"},
        "status": "ready",
    }


def _infer_output_ports(*, machine_result_schema_ref: str | None, artifact_specs: list[dict[str, str]]) -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []
    if machine_result_schema_ref:
        ports.append(
            {
                "port_id": "machine_result",
                "label": "Machine Result",
                "port_type": "structured_json",
                "shape": "single",
                "required": True,
                "schema_ref": machine_result_schema_ref,
            }
        )
    for spec in artifact_specs:
        artifact_kind = str(spec.get("kind") or "").strip()
        artifact_id = str(spec.get("id") or artifact_kind or "artifact").strip()
        ports.append(
            {
                "port_id": artifact_id,
                "label": artifact_id.replace("_", " ").title(),
                "port_type": _artifact_kind_to_port_type(artifact_kind),
                "shape": "single",
                "required": False,
                "artifact_kind": artifact_kind,
            }
        )
    return ports


def _artifact_kind_to_port_type(kind: str) -> str:
    mapping = {
        "structured_json": "structured_json",
        "image": "image",
        "audio": "audio",
        "video": "video",
        "document_extract": "document",
        "code_diff": "code_diff",
        "dataset": "dataset",
        "approval_record": "approval_record",
        "tool_result": "tool_result",
        "validation_report": "agent_report",
        "run_summary": "agent_report",
        "test_report": "agent_report",
        "text_report": "text",
    }
    return mapping.get(kind, "text")


def _code_fix_review_example() -> dict[str, Any]:
    schemas = {
        "schema.plan_fix_result": {"type": "object", "required": ["files", "approach"]},
        "schema.code_fix_result": {"type": "object", "required": ["changed_files", "summary"]},
        "schema.test_result": {"type": "object", "required": ["status", "failures"]},
        "schema.review_result": {"type": "object", "required": ["decision", "issues"]},
    }
    nodes = [
        _node(
            node_id="node_plan_fix",
            kind="supervisor",
            role="planner",
            label="Plan Fix",
            card_ref="agent_card_code_supervisor",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Bound the file set and expected evidence before any edits.",
            tool_classes=["web", "read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.plan_fix_result",
            artifact_specs=[{"kind": "structured_json", "id": "plan_manifest"}],
            spawn_mode="inline_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=True,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=80,
            y=180,
            capability_claims={"input_port_types": ["text"], "output_port_types": ["structured_json", "structured_json"]},
        ),
        _node(
            node_id="node_apply_fix",
            kind="worker",
            role="coder",
            label="Apply Code Fix",
            card_ref="agent_card_code_worker",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Apply only the bounded code change and explain every changed file.",
            tool_classes=["read_file", "edit_file", "shell"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.code_fix_result",
            artifact_specs=[{"kind": "code_diff", "id": "bounded_patch"}],
            spawn_mode="subagent_worker",
            timeout_ms=180000,
            risk_class="high",
            allow_provider_calls=True,
            allow_code_changes=True,
            allow_install=False,
            requires_human_approval=True,
            x=330,
            y=180,
            approval_kind="filesystem_write_gate",
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "plan_input", "label": "Plan Input", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.plan_fix_result"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json"], "output_port_types": ["structured_json", "code_diff"]},
        ),
        _node(
            node_id="node_run_tests",
            kind="validator",
            role="validator",
            label="Run Tests",
            card_ref="agent_card_test_validator",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Run the smallest sufficient test scope and report failures precisely.",
            tool_classes=["shell", "read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.test_result",
            artifact_specs=[{"kind": "test_report", "id": "test_report"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=600,
            y=100,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "fix_result", "label": "Fix Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.code_fix_result"},
                {"port_id": "patch_input", "label": "Patch Input", "port_type": "code_diff", "shape": "single", "required": False, "artifact_kind": "code_diff"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json", "code_diff"], "output_port_types": ["structured_json", "agent_report"]},
        ),
        _node(
            node_id="node_review",
            kind="reviewer",
            role="reviewer",
            label="Review Result",
            card_ref="agent_card_reviewer",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Review the patch and tests together; call out residual risk and approval posture.",
            tool_classes=["read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.review_result",
            artifact_specs=[{"kind": "validation_report", "id": "review_report"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=600,
            y=260,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "fix_result", "label": "Fix Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.code_fix_result"},
                {"port_id": "patch_input", "label": "Patch Input", "port_type": "code_diff", "shape": "single", "required": False, "artifact_kind": "code_diff"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json", "code_diff"], "output_port_types": ["structured_json", "agent_report"]},
        ),
    ]
    edges = [
        _edge(edge_id="edge_plan_fix", from_node_id="node_plan_fix", to_node_id="node_apply_fix", edge_type="context_handoff", schema_ref="schema.plan_fix_result", message_template="Use the approved file set and implementation plan.", x=205, y=180, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "plan_input"}]),
        _edge(edge_id="edge_fix_test", from_node_id="node_apply_fix", to_node_id="node_run_tests", edge_type="artifact_handoff", schema_ref="schema.code_fix_result", message_template="Validate the bounded patch and summarize failing evidence.", x=465, y=125, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "fix_result"}, {"from_port_id": "bounded_patch", "to_port_id": "patch_input"}]),
        _edge(edge_id="edge_fix_review", from_node_id="node_apply_fix", to_node_id="node_review", edge_type="artifact_handoff", schema_ref="schema.code_fix_result", message_template="Review the patch quality and residual risk.", x=465, y=235, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "fix_result"}, {"from_port_id": "bounded_patch", "to_port_id": "patch_input"}]),
    ]
    return _base_graph(
        graph_id="graph_code_fix_review_v1",
        title="Code Fix / Test / Review",
        template_id="code_fix_test_review",
        tags=["coding", "review", "bounded-change"],
        entry_node_ids=["node_plan_fix"],
        nodes=nodes,
        edges=edges,
        schema_registry=schemas,
    )


def _supervisor_worker_synthesizer_example() -> dict[str, Any]:
    schemas = {
        "schema.supervisor_plan": {"type": "object", "required": ["goal", "constraints"]},
        "schema.worker_result": {"type": "object", "required": ["result", "evidence"]},
        "schema.synthesis_result": {"type": "object", "required": ["summary", "open_questions"]},
    }
    nodes = [
        _node(
            node_id="node_supervisor",
            kind="supervisor",
            role="supervisor",
            label="Supervisor",
            card_ref="agent_card_supervisor",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Define a bounded plan, a success bar, and the worker evidence requirements.",
            tool_classes=["read_file", "web"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.supervisor_plan",
            artifact_specs=[{"kind": "structured_json", "id": "supervisor_plan"}],
            spawn_mode="inline_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=True,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=80,
            y=200,
            capability_claims={"input_port_types": ["text"], "output_port_types": ["structured_json"]},
        ),
        _node(
            node_id="node_worker",
            kind="worker",
            role="worker",
            label="Worker",
            card_ref="agent_card_worker",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Execute only the approved task slice and return evidence-backed output.",
            tool_classes=["read_file", "shell"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.worker_result",
            artifact_specs=[{"kind": "text_report", "id": "worker_report"}],
            spawn_mode="subagent_worker",
            timeout_ms=180000,
            risk_class="moderate",
            allow_provider_calls=True,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=350,
            y=200,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "supervisor_plan", "label": "Supervisor Plan", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.supervisor_plan"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json"], "output_port_types": ["structured_json", "text"]},
            input_mode="typed_ports",
            input_port_ids=["supervisor_plan"],
        ),
        _node(
            node_id="node_synth",
            kind="synthesizer",
            role="synthesizer",
            label="Synthesizer",
            card_ref="agent_card_synthesizer",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Merge the worker result into one bounded answer and keep unresolved questions explicit.",
            tool_classes=["read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.synthesis_result",
            artifact_specs=[{"kind": "run_summary", "id": "final_summary"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=620,
            y=200,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "worker_result", "label": "Worker Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.worker_result"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json"], "output_port_types": ["structured_json", "agent_report"]},
            input_mode="typed_ports",
            input_port_ids=["worker_result"],
        ),
    ]
    edges = [
        _edge(edge_id="edge_supervisor_worker", from_node_id="node_supervisor", to_node_id="node_worker", edge_type="context_handoff", schema_ref="schema.supervisor_plan", message_template="Use the supervisor plan as the worker contract.", x=215, y=200, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "supervisor_plan"}]),
        _edge(edge_id="edge_worker_synth", from_node_id="node_worker", to_node_id="node_synth", edge_type="artifact_handoff", schema_ref="schema.worker_result", message_template="Synthesize the worker result into the final bounded answer.", x=485, y=200, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "worker_result"}]),
    ]
    return _base_graph(
        graph_id="graph_supervisor_worker_synthesizer_v1",
        title="Supervisor / Worker / Synthesizer",
        template_id="supervisor_worker_synthesizer",
        tags=["supervisor", "worker", "synthesis"],
        entry_node_ids=["node_supervisor"],
        nodes=nodes,
        edges=edges,
        schema_registry=schemas,
    )


def _provider_update_smoke_example() -> dict[str, Any]:
    schemas = {
        "schema.provider_update_discovery": {"type": "object", "required": ["provider_changes", "candidate_models"]},
        "schema.provider_smoke_matrix": {"type": "object", "required": ["matrix", "blocked_cases"]},
        "schema.provider_gate_decision": {"type": "object", "required": ["decision", "notes"]},
    }
    nodes = [
        _node(
            node_id="node_discover",
            kind="extractor",
            role="researcher",
            label="Discover Provider Update",
            card_ref="agent_card_provider_discovery",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Collect provider release changes and normalize the findings into a candidate update bundle.",
            tool_classes=["web", "read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.provider_update_discovery",
            artifact_specs=[{"kind": "structured_json", "id": "provider_change_bundle"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=80,
            y=180,
            capability_claims={"input_port_types": ["text"], "output_port_types": ["structured_json", "structured_json"]},
        ),
        _node(
            node_id="node_smoke",
            kind="validator",
            role="validator",
            label="Smoke Matrix",
            card_ref="agent_card_smoke_validator",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Run the compatibility smoke matrix and classify blocked cases explicitly.",
            tool_classes=["read_file", "shell"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.provider_smoke_matrix",
            artifact_specs=[{"kind": "validation_report", "id": "smoke_matrix"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=350,
            y=180,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "provider_bundle", "label": "Provider Bundle", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.provider_update_discovery"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json"], "output_port_types": ["structured_json", "agent_report"]},
        ),
        _node(
            node_id="node_gate",
            kind="gate",
            role="gate",
            label="Manual Promotion Gate",
            card_ref="agent_card_manual_gate",
            provider_id=None,
            model_id=None,
            prompt="Present the smoke evidence bundle for a bounded human promotion decision.",
            tool_classes=[],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.provider_gate_decision",
            artifact_specs=[{"kind": "approval_record", "id": "promotion_decision"}],
            spawn_mode="manual_only",
            timeout_ms=0,
            risk_class="high",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=True,
            x=640,
            y=180,
            approval_kind="provider_call_gate",
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "smoke_matrix", "label": "Smoke Matrix", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.provider_smoke_matrix"},
            ],
            input_mode="typed_ports",
            input_port_ids=["smoke_matrix"],
        ),
    ]
    edges = [
        _edge(edge_id="edge_discover_smoke", from_node_id="node_discover", to_node_id="node_smoke", edge_type="artifact_handoff", schema_ref="schema.provider_update_discovery", message_template="Validate the provider update bundle with the smoke matrix.", x=215, y=180, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "provider_bundle"}]),
        _edge(edge_id="edge_smoke_gate", from_node_id="node_smoke", to_node_id="node_gate", edge_type="approval_dependency", schema_ref="schema.provider_smoke_matrix", message_template="Review the smoke matrix and blocked cases before promotion.", x=495, y=180, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "smoke_matrix"}]),
    ]
    return _base_graph(
        graph_id="graph_provider_update_smoke_v1",
        title="Provider Update / Smoke / Gate",
        template_id="provider_update_smoke_gate",
        tags=["providers", "smoke", "gate"],
        entry_node_ids=["node_discover"],
        nodes=nodes,
        edges=edges,
        schema_registry=schemas,
    )


def _fanout_research_synthesis_example() -> dict[str, Any]:
    schemas = {
        "schema.research_plan": {"type": "object", "required": ["questions", "branches"]},
        "schema.branch_findings": {"type": "object", "required": ["findings", "sources"]},
        "schema.research_synthesis": {"type": "object", "required": ["synthesis", "gaps"]},
    }
    nodes = [
        _node(
            node_id="node_plan",
            kind="supervisor",
            role="planner",
            label="Research Planner",
            card_ref="agent_card_research_supervisor",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Decompose the research goal into bounded branch questions and expected outputs.",
            tool_classes=["web", "read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.research_plan",
            artifact_specs=[{"kind": "structured_json", "id": "branch_plan"}],
            spawn_mode="inline_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=True,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=80,
            y=200,
            capability_claims={"input_port_types": ["text"], "output_port_types": ["structured_json", "structured_json"]},
        ),
        _node(
            node_id="node_branch_a",
            kind="worker",
            role="researcher",
            label="Research Branch A",
            card_ref="agent_card_research_worker",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Research branch A only and attribute every finding.",
            tool_classes=["web", "read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.branch_findings",
            artifact_specs=[{"kind": "text_report", "id": "branch_a_report"}],
            spawn_mode="subagent_worker",
            timeout_ms=180000,
            risk_class="moderate",
            allow_provider_calls=True,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=360,
            y=120,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "branch_plan", "label": "Branch Plan", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.research_plan"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json"], "output_port_types": ["structured_json", "text"]},
        ),
        _node(
            node_id="node_branch_b",
            kind="worker",
            role="researcher",
            label="Research Branch B",
            card_ref="agent_card_research_worker",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Research branch B only and attribute every finding.",
            tool_classes=["web", "read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.branch_findings",
            artifact_specs=[{"kind": "text_report", "id": "branch_b_report"}],
            spawn_mode="subagent_worker",
            timeout_ms=180000,
            risk_class="moderate",
            allow_provider_calls=True,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=360,
            y=280,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "branch_plan", "label": "Branch Plan", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.research_plan"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json"], "output_port_types": ["structured_json", "text"]},
        ),
        _node(
            node_id="node_synth",
            kind="synthesizer",
            role="synthesizer",
            label="Research Synthesizer",
            card_ref="agent_card_research_synthesizer",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Merge branch findings into one bounded synthesis and call out unresolved gaps.",
            tool_classes=["read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.research_synthesis",
            artifact_specs=[{"kind": "run_summary", "id": "research_synthesis"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=650,
            y=200,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "branch_a_findings", "label": "Branch A Findings", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.branch_findings"},
                {"port_id": "branch_b_findings", "label": "Branch B Findings", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.branch_findings"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json"], "output_port_types": ["structured_json", "agent_report"]},
        ),
    ]
    edges = [
        _edge(edge_id="edge_plan_a", from_node_id="node_plan", to_node_id="node_branch_a", edge_type="fanout_branch", schema_ref="schema.research_plan", message_template="Use only branch A of the research plan.", x=220, y=150, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "branch_plan"}]),
        _edge(edge_id="edge_plan_b", from_node_id="node_plan", to_node_id="node_branch_b", edge_type="fanout_branch", schema_ref="schema.research_plan", message_template="Use only branch B of the research plan.", x=220, y=250, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "branch_plan"}]),
        _edge(edge_id="edge_a_synth", from_node_id="node_branch_a", to_node_id="node_synth", edge_type="fanin_merge", schema_ref="schema.branch_findings", message_template="Merge branch A findings into the synthesis.", x=510, y=150, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "branch_a_findings"}]),
        _edge(edge_id="edge_b_synth", from_node_id="node_branch_b", to_node_id="node_synth", edge_type="fanin_merge", schema_ref="schema.branch_findings", message_template="Merge branch B findings into the synthesis.", x=510, y=250, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "branch_b_findings"}]),
    ]
    return _base_graph(
        graph_id="graph_fanout_research_synthesis_v1",
        title="Fan-out Research / Fan-in Synthesis",
        template_id="fanout_fanin_research",
        tags=["research", "fanout", "synthesis"],
        entry_node_ids=["node_plan"],
        nodes=nodes,
        edges=edges,
        schema_registry=schemas,
    )


def _multimodal_capability_adapter_example() -> dict[str, Any]:
    schemas = {
        "schema.multimodal_probe": {"type": "object", "required": ["detected_modalities", "fallback_plan"]},
        "schema.multimodal_adapted": {"type": "object", "required": ["adapted_prompt", "selected_route"]},
        "schema.multimodal_validation": {"type": "object", "required": ["status", "fallback_used"]},
    }
    nodes = [
        _node(
            node_id="node_probe_input",
            kind="extractor",
            role="extractor",
            label="Probe Input",
            card_ref="agent_card_multimodal_probe",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Probe the incoming request, detect available modalities, and propose a safe fallback route.",
            tool_classes=["read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.multimodal_probe",
            artifact_specs=[{"kind": "image", "id": "input_image"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=80,
            y=200,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "user_image", "label": "User Image", "port_type": "image", "shape": "single", "required": False},
            ],
            capability_claims={"input_port_types": ["text", "image"], "output_port_types": ["structured_json", "image"]},
        ),
        _node(
            node_id="node_adapt_contract",
            kind="worker",
            role="custom",
            label="Adapt Contract",
            card_ref="agent_card_multimodal_adapter",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Adapt the prompt and declared communication contract to the supported multimodal route only.",
            tool_classes=["read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.multimodal_adapted",
            artifact_specs=[{"kind": "document_extract", "id": "adapted_contract"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=350,
            y=200,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "probe_result", "label": "Probe Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.multimodal_probe"},
                {"port_id": "probe_image", "label": "Probe Image", "port_type": "image", "shape": "single", "required": False, "artifact_kind": "image"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json", "image"], "output_port_types": ["structured_json", "document"]},
            input_mode="typed_ports",
            input_port_ids=["probe_result", "probe_image"],
        ),
        _node(
            node_id="node_validate_fallback",
            kind="validator",
            role="validator",
            label="Validate Fallback",
            card_ref="agent_card_multimodal_validator",
            provider_id="qwen",
            model_id="qwen3-coder-plus",
            prompt="Verify that the adapted route preserves required semantics and declares fallback behavior.",
            tool_classes=["read_file"],
            output_mode="structured_and_artifacts",
            machine_result_schema_ref="schema.multimodal_validation",
            artifact_specs=[{"kind": "validation_report", "id": "multimodal_validation"}],
            spawn_mode="isolated_lane",
            timeout_ms=120000,
            risk_class="moderate",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=620,
            y=200,
            input_ports=[
                {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                {"port_id": "adapted_contract_input", "label": "Adapted Contract", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.multimodal_adapted"},
                {"port_id": "contract_doc", "label": "Contract Doc", "port_type": "document", "shape": "single", "required": False, "artifact_kind": "document_extract"},
            ],
            capability_claims={"input_port_types": ["text", "structured_json", "document"], "output_port_types": ["structured_json", "agent_report"]},
            input_mode="typed_ports",
            input_port_ids=["adapted_contract_input", "contract_doc"],
        ),
    ]
    edges = [
        _edge(edge_id="edge_probe_adapt", from_node_id="node_probe_input", to_node_id="node_adapt_contract", edge_type="artifact_handoff", schema_ref="schema.multimodal_probe", message_template="Adapt the route using the probe result and any detected image payload.", x=215, y=200, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "probe_result"}, {"from_port_id": "input_image", "to_port_id": "probe_image"}]),
        _edge(edge_id="edge_adapt_validate", from_node_id="node_adapt_contract", to_node_id="node_validate_fallback", edge_type="artifact_handoff", schema_ref="schema.multimodal_adapted", message_template="Validate the adapted multimodal contract and fallback semantics.", x=485, y=200, port_bindings=[{"from_port_id": "machine_result", "to_port_id": "adapted_contract_input"}, {"from_port_id": "adapted_contract", "to_port_id": "contract_doc"}]),
    ]
    return _base_graph(
        graph_id="graph_multimodal_capability_adapter_v1",
        title="Multimodal Capability Adapter",
        template_id="multimodal_capability_adapter",
        tags=["multimodal", "adapter", "fallback"],
        entry_node_ids=["node_probe_input"],
        nodes=nodes,
        edges=edges,
        schema_registry=schemas,
    )


def _custom_blank_graph_example() -> dict[str, Any]:
    schemas = {
        "schema.blank_entry": {"type": "object", "required": ["goal", "next_nodes"]},
    }
    nodes = [
        _node(
            node_id="node_start_here",
            kind="artifact_source",
            role="custom",
            label="Start Here",
            card_ref="agent_card_blank_entry",
            provider_id=None,
            model_id=None,
            prompt="Use this starter node as the seed for a custom graph.",
            tool_classes=[],
            output_mode="structured_only",
            machine_result_schema_ref="schema.blank_entry",
            artifact_specs=[],
            spawn_mode="inline_lane",
            timeout_ms=60000,
            risk_class="low",
            allow_provider_calls=False,
            allow_code_changes=False,
            allow_install=False,
            requires_human_approval=False,
            x=140,
            y=200,
            input_mode="task_context_and_typed_ports",
            input_port_ids=["task_context"],
            output_ports=[
                {"port_id": "machine_result", "label": "Machine Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.blank_entry"},
            ],
        ),
    ]
    return _base_graph(
        graph_id="graph_custom_blank_graph_v1",
        title="Custom Blank Graph",
        template_id="custom_blank_graph",
        tags=["custom", "blank", "starter"],
        entry_node_ids=["node_start_here"],
        nodes=nodes,
        edges=[],
        schema_registry=schemas,
    )
