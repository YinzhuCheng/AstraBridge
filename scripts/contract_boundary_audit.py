from __future__ import annotations

import argparse
import json
import subprocess
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
from astrabridge_sidecar.protocol.compatibility import compatibility_manifest  # noqa: E402
from astrabridge_sidecar.protocol.generated.v1 import (  # noqa: E402
    SCHEMA_VERSION,
    validation_verdict,
)
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
PROTOCOL_SCHEMA_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "protocol" / "schema" / "v1" / "protocol.json"
PROTOCOL_MANIFEST_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "protocol" / "compatibility_manifest.json"
PROTOCOL_GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_protocol_types.py"
PROTOCOL_PY_GENERATED_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "protocol" / "generated" / "v1.py"
PROTOCOL_TS_GENERATED_PATH = REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "astrabridge_protocol" / "generated" / "v1.ts"
PROTOCOL_FIXTURE_PATH = REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "astrabridge_protocol" / "fixtures" / "protocol_v1.json"
RUNTIME_CLIENT_POOL_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_client_pool.py"
DURABLE_RUN_STORE_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "durable_run_store.py"
GRAPH_SCHEDULER_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "graph_scheduler.py"
MCP_SERVER_CORE_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "mcp_server_core.py"
MCP_BROKER_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "mcp_broker_service.py"
MCP_NODE_POLICY_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "mcp_node_policy.py"
MULTIMODAL_RESULT_ENVELOPE_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "multimodal_result_envelope.py"
RUNTIME_OBSERVABILITY_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_observability.py"
RUNTIME_STABILITY_GATE_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_stability_gate.py"
RUNTIME_ROLLOUT_GATE_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_rollout_gate.py"
NODE_TYPE_REGISTRY_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "node_type_registry.py"
COMFYUI_WORKFLOW_ADAPTER_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "comfyui_workflow_adapter.py"
LANGGRAPH_STATEGRAPH_ADAPTER_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "langgraph_stategraph_adapter.py"
DESKTOP_SIDECAR_SUPERVISION_PATH = REPO_ROOT / "apps" / "astrabridge-desktop" / "src-tauri" / "src" / "sidecar_supervision.rs"
DESKTOP_TAURI_MAIN_PATH = REPO_ROOT / "apps" / "astrabridge-desktop" / "src-tauri" / "src" / "main.rs"
DESKTOP_API_PATH = REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "api.ts"
SIDECAR_SERVER_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "server.py"
RUNTIME_SUPERVISOR_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_supervisor_service.py"
RUN_RUNTIME_STABILITY_GATE_SCRIPT_PATH = REPO_ROOT / "scripts" / "run_runtime_stability_gate.py"
RUN_RUNTIME_ROLLOUT_GATE_SCRIPT_PATH = REPO_ROOT / "scripts" / "run_runtime_rollout_gate.py"
RUN_LOCAL_GATE_PATH = REPO_ROOT / "scripts" / "run_local_gate.py"
RUNTIME_ROLLOUT_RUNBOOK_PATH = REPO_ROOT / "docs" / "RUNTIME_ROLLOUT_AND_MAINTENANCE_RUNBOOK.md"
MCP_SERVER_ADAPTER_PATHS = {
    "capabilities": SIDECAR_ROOT / "astrabridge_sidecar" / "astrabridge_capabilities_mcp_server.py",
    "web": SIDECAR_ROOT / "astrabridge_sidecar" / "astrabridge_web_mcp_server.py",
    "yunwu": SIDECAR_ROOT / "astrabridge_sidecar" / "yunwu_image_mcp_server.py",
    "probe_fixture": SIDECAR_ROOT / "astrabridge_sidecar" / "codex_mcp_probe_fixture_server.py",
}

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
        "runtime_client_pool": RUNTIME_CLIENT_POOL_PATH,
        "durable_run_store": DURABLE_RUN_STORE_PATH,
        "graph_scheduler": GRAPH_SCHEDULER_PATH,
        "mcp_server_core": MCP_SERVER_CORE_PATH,
        "mcp_broker": MCP_BROKER_PATH,
        "mcp_node_policy": MCP_NODE_POLICY_PATH,
        "multimodal_result_envelope": MULTIMODAL_RESULT_ENVELOPE_PATH,
        "runtime_observability": RUNTIME_OBSERVABILITY_PATH,
        "runtime_stability_gate": RUNTIME_STABILITY_GATE_PATH,
        "runtime_rollout_gate": RUNTIME_ROLLOUT_GATE_PATH,
        "node_type_registry": NODE_TYPE_REGISTRY_PATH,
        "comfyui_workflow_adapter": COMFYUI_WORKFLOW_ADAPTER_PATH,
        "langgraph_stategraph_adapter": LANGGRAPH_STATEGRAPH_ADAPTER_PATH,
        "desktop_sidecar_supervision": DESKTOP_SIDECAR_SUPERVISION_PATH,
        "desktop_tauri_main": DESKTOP_TAURI_MAIN_PATH,
        "desktop_api": DESKTOP_API_PATH,
        "sidecar_server": SIDECAR_SERVER_PATH,
        "runtime_supervisor": RUNTIME_SUPERVISOR_PATH,
        "runtime_stability_gate_script": RUN_RUNTIME_STABILITY_GATE_SCRIPT_PATH,
        "runtime_rollout_gate_script": RUN_RUNTIME_ROLLOUT_GATE_SCRIPT_PATH,
        "run_local_gate": RUN_LOCAL_GATE_PATH,
        "runtime_rollout_runbook": RUNTIME_ROLLOUT_RUNBOOK_PATH,
    }
    missing = [name for name, path in required_paths.items() if not path.exists()]
    if missing:
        errors.append(f"missing stability ownership inputs: {', '.join(sorted(missing))}")

    ownership_text = OWNERSHIP_DOC_PATH.read_text(encoding="utf-8") if OWNERSHIP_DOC_PATH.exists() else ""
    stability_text = STABILITY_PLAN_PATH.read_text(encoding="utf-8") if STABILITY_PLAN_PATH.exists() else ""
    capability_text = CAPABILITY_PLAN_PATH.read_text(encoding="utf-8") if CAPABILITY_PLAN_PATH.exists() else ""

    ownership_markers = (
        "astrabridge_sidecar.protocol",
        "astrabridge_sidecar.mcp_server_core",
        "astrabridge_sidecar.mcp_broker_service",
        "astrabridge_sidecar.mcp_node_policy",
        "astrabridge_sidecar.multimodal_result_envelope",
        "astrabridge_sidecar.runtime_observability",
        "astrabridge_sidecar.runtime_stability_gate",
        "astrabridge_sidecar.runtime_rollout_gate",
        "astrabridge_sidecar.node_type_registry",
        "astrabridge_sidecar.comfyui_workflow_adapter",
        "astrabridge_sidecar.langgraph_stategraph_adapter",
        "Cross-layer trace lineage, reliability metrics/SLOs, and redacted diagnostics",
        "Deterministic fault injection and runtime stability release gate",
        "Final runtime rollout, migration, shadow comparison, rollback-readback, and release closure",
        "Canonical NodeType registry and compiled graph executable metadata",
        "Loss-aware ComfyUI workflow import/export bridge",
        "Optional LangGraph StateGraph interop bridge",
        "Desktop-Sidecar host supervision, readiness, launch ownership, and run reattachment handshake",
        "sidecar_supervision.rs",
        "/readyz",
        "graceful host shutdown",
        "Provider runtime client lanes and lifecycle leases",
        "Agent Envelope, delivery events, and artifact references",
        "MCP protocol core and broker boundary",
        "Per-node MCP tool/resource least-privilege policy",
        "Typed multimodal MCP results and workspace-safe artifact projection",
        "Durable graph run state, scheduler commands, and ordered events",
        "DurableRunEventStore",
        "DurableGraphScheduler",
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
        "owner": "docs/CODE_OWNERSHIP_AND_CONTRACTS.md + astrabridge_sidecar.protocol + astrabridge_sidecar.mcp_server_core + astrabridge_sidecar.mcp_broker_service + astrabridge_sidecar.mcp_node_policy + astrabridge_sidecar.multimodal_result_envelope + astrabridge_sidecar.runtime_observability + apps/astrabridge-desktop/src-tauri/src/sidecar_supervision.rs + astrabridge_sidecar/server.py",
        "status": "pass" if not errors else "fail",
        "required_inputs": {name: str(path.relative_to(REPO_ROOT)) for name, path in required_paths.items()},
        "errors": errors,
    }


def _audit_desktop_sidecar_supervision() -> dict[str, Any]:
    errors: list[str] = []
    supervision_source = DESKTOP_SIDECAR_SUPERVISION_PATH.read_text(encoding="utf-8") if DESKTOP_SIDECAR_SUPERVISION_PATH.exists() else ""
    tauri_main_source = DESKTOP_TAURI_MAIN_PATH.read_text(encoding="utf-8") if DESKTOP_TAURI_MAIN_PATH.exists() else ""
    desktop_api_source = DESKTOP_API_PATH.read_text(encoding="utf-8") if DESKTOP_API_PATH.exists() else ""
    server_source = SIDECAR_SERVER_PATH.read_text(encoding="utf-8") if SIDECAR_SERVER_PATH.exists() else ""
    for marker in (
        "struct SidecarSupervisor",
        "SIDECAR_READY_ROUTE",
        "sidecar_circuit_breaker_opened",
        "sidecar_launch_requested",
        "request_graceful_shutdown",
        "cleanup_stale_leases",
        "hard_kill_verified",
    ):
        if marker not in supervision_source:
            errors.append(f"desktop sidecar supervision owner missing required marker: {marker}")
    if "mod sidecar_supervision;" not in tauri_main_source or "app.manage(supervisor);" not in tauri_main_source:
        errors.append("Tauri main entry is not wiring the shared sidecar supervision owner")
    if 'return invoke<string>("sidecar_url")' not in desktop_api_source:
        errors.append("Desktop API is not resolving the current sidecar URL from the shared supervisor owner")
    for marker in (
        'if path == "/readyz":',
        'if path == "/host/shutdown":',
        "DURABLE_RUN_STORE_SCHEMA_VERSION",
        "build_version",
        "boot_id",
        "AstraBridgeSidecarHttpServer",
    ):
        if marker not in server_source:
            errors.append(f"sidecar server supervision bridge missing required marker: {marker}")
    return {
        "contract": "desktop_sidecar_supervision_and_readyz_handshake",
        "owner": "apps/astrabridge-desktop/src-tauri/src/sidecar_supervision.rs + astrabridge_sidecar/server.py",
        "status": "pass" if not errors else "fail",
        "paths": {
            "desktop_supervision": str(DESKTOP_SIDECAR_SUPERVISION_PATH.relative_to(REPO_ROOT)),
            "tauri_main": str(DESKTOP_TAURI_MAIN_PATH.relative_to(REPO_ROOT)),
            "desktop_api": str(DESKTOP_API_PATH.relative_to(REPO_ROOT)),
            "sidecar_server": str(SIDECAR_SERVER_PATH.relative_to(REPO_ROOT)),
        },
        "errors": errors,
    }


def _audit_runtime_observability() -> dict[str, Any]:
    errors: list[str] = []
    observability_source = RUNTIME_OBSERVABILITY_PATH.read_text(encoding="utf-8") if RUNTIME_OBSERVABILITY_PATH.exists() else ""
    runtime_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_service.py").read_text(encoding="utf-8")
    supervisor_source = RUNTIME_SUPERVISOR_PATH.read_text(encoding="utf-8") if RUNTIME_SUPERVISOR_PATH.exists() else ""
    desktop_app_source = (REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "App.tsx").read_text(encoding="utf-8")
    for marker in (
        "RUNTIME_OBSERVABILITY_SCHEMA_VERSION",
        "build_runtime_observability_summary",
        "load_host_lineage_events",
        "extract_trace_context",
        "duplicate_effect_count",
        "mcp_conformance_rate",
        "node_latency_p95_ms",
        "first_token_latency_p95_ms",
    ):
        if marker not in observability_source:
            errors.append(f"runtime observability owner missing required marker: {marker}")
    if "enrich_runtime_event" not in runtime_source or "load_host_lineage_events" not in runtime_source:
        errors.append("runtime service is not routing persisted runtime events and host lineage through the shared observability owner")
    if "build_runtime_observability_summary" not in supervisor_source or '"observability": observability' not in supervisor_source:
        errors.append("runtime supervisor status is not projecting the shared observability summary")
    if "supervisor?.observability" not in desktop_app_source and "observability?.metrics" not in desktop_app_source:
        errors.append("Desktop status evidence is not consuming the shared observability summary")
    return {
        "contract": "cross_layer_trace_metrics_and_redacted_diagnostics",
        "owner": "astrabridge_sidecar.runtime_observability",
        "status": "pass" if not errors else "fail",
        "path": str(RUNTIME_OBSERVABILITY_PATH.relative_to(REPO_ROOT)),
        "errors": errors,
    }


def _audit_runtime_stability_gate() -> dict[str, Any]:
    errors: list[str] = []
    gate_source = RUNTIME_STABILITY_GATE_PATH.read_text(encoding="utf-8") if RUNTIME_STABILITY_GATE_PATH.exists() else ""
    wrapper_source = RUN_RUNTIME_STABILITY_GATE_SCRIPT_PATH.read_text(encoding="utf-8") if RUN_RUNTIME_STABILITY_GATE_SCRIPT_PATH.exists() else ""
    local_gate_source = RUN_LOCAL_GATE_PATH.read_text(encoding="utf-8") if RUN_LOCAL_GATE_PATH.exists() else ""
    for marker in (
        "RUNTIME_STABILITY_GATE_SCHEMA_VERSION",
        "runtime_stability_gate_suite_specs",
        "run_runtime_stability_gate",
        "capture_runtime_stability_fixture_evidence",
        "scan_runtime_stability_artifacts",
        "PRIVATE\" / \"runtime-stability",
        "\"normal_gate_mode\": \"fast\"",
        "\"release_gate_mode\": \"release\"",
    ):
        if marker not in gate_source:
            errors.append(f"runtime stability gate owner missing required marker: {marker}")
    if "from astrabridge_sidecar.runtime_stability_gate import run_runtime_stability_gate" not in wrapper_source:
        errors.append("runtime stability gate CLI wrapper is not delegating to the shared owner")
    if '"--mode",' not in local_gate_source or '"fast"' not in local_gate_source or "run_runtime_stability_gate.py" not in local_gate_source:
        errors.append("run_local_gate.py is not projecting the shared fast runtime stability gate")
    return {
        "contract": "deterministic_fault_injection_and_runtime_stability_gate",
        "owner": "astrabridge_sidecar.runtime_stability_gate",
        "status": "pass" if not errors else "fail",
        "paths": {
            "runtime_stability_gate": str(RUNTIME_STABILITY_GATE_PATH.relative_to(REPO_ROOT)),
            "runtime_stability_gate_script": str(RUN_RUNTIME_STABILITY_GATE_SCRIPT_PATH.relative_to(REPO_ROOT)),
            "run_local_gate": str(RUN_LOCAL_GATE_PATH.relative_to(REPO_ROOT)),
        },
        "errors": errors,
    }


def _audit_node_type_registry() -> dict[str, Any]:
    errors: list[str] = []
    registry_source = NODE_TYPE_REGISTRY_PATH.read_text(encoding="utf-8") if NODE_TYPE_REGISTRY_PATH.exists() else ""
    contract_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "agent_orchestration_contract.py").read_text(encoding="utf-8")
    compiler_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "agent_orchestration_compiler.py").read_text(encoding="utf-8")
    task_contract_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "task_graph_contract.py").read_text(encoding="utf-8")
    task_service_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "task_service.py").read_text(encoding="utf-8")
    server_source = SIDECAR_SERVER_PATH.read_text(encoding="utf-8") if SIDECAR_SERVER_PATH.exists() else ""
    desktop_api_source = DESKTOP_API_PATH.read_text(encoding="utf-8") if DESKTOP_API_PATH.exists() else ""
    for marker in (
        "NODE_TYPE_REGISTRY_SCHEMA_VERSION",
        "class NodeTypeSpec",
        "build_node_type_registry",
        "node_type_registry_snapshot",
        "resolve_node_type",
        "project_task_graph_kind",
        "registry_fingerprint",
        "agent_model",
        "mcp_tool",
        "mcp_resource",
        "transform",
        "router_condition",
        "loop",
        "subgraph",
        "human_approval",
        "artifact_source",
        "artifact_sink",
    ):
        if marker not in registry_source:
            errors.append(f"node type registry owner missing required marker: {marker}")
    for marker in (
        "resolve_node_type(",
        "compatible_roles_for_kind(",
        "default_role_for_kind(",
    ):
        if marker not in contract_source:
            errors.append(f"agent orchestration contract is not consuming the shared node type registry marker: {marker}")
    for marker in (
        "resolve_node_type(",
        '"compiler_executor_id"',
        '"node_type_registry_fingerprint"',
    ):
        if marker not in compiler_source:
            errors.append(f"agent orchestration compiler is not projecting shared node type registry metadata: {marker}")
    if "task_graph_node_kind_ids" not in task_contract_source:
        errors.append("task graph contract is not deriving allowed node kinds from the shared node type registry")
    if "node_type_registry_snapshot(" not in task_service_source:
        errors.append("task service is not exposing the shared node type registry snapshot")
    if 'if path == "/api/task-graphs/node-types":' not in server_source:
        errors.append("server is not exposing the shared node type registry API route")
    if '"/api/task-graphs/node-types"' not in desktop_api_source or "taskGraphNodeTypes" not in desktop_api_source:
        errors.append("desktop API is not projecting the shared node type registry route")
    return {
        "contract": "canonical_node_type_registry_and_compiler_interface",
        "owner": "astrabridge_sidecar.node_type_registry + agent_orchestration_compiler.py",
        "status": "pass" if not errors else "fail",
        "paths": {
            "node_type_registry": str(NODE_TYPE_REGISTRY_PATH.relative_to(REPO_ROOT)),
            "agent_orchestration_contract": str((SIDECAR_ROOT / "astrabridge_sidecar" / "agent_orchestration_contract.py").relative_to(REPO_ROOT)),
            "agent_orchestration_compiler": str((SIDECAR_ROOT / "astrabridge_sidecar" / "agent_orchestration_compiler.py").relative_to(REPO_ROOT)),
            "task_graph_contract": str((SIDECAR_ROOT / "astrabridge_sidecar" / "task_graph_contract.py").relative_to(REPO_ROOT)),
            "task_service": str((SIDECAR_ROOT / "astrabridge_sidecar" / "task_service.py").relative_to(REPO_ROOT)),
            "server": str(SIDECAR_SERVER_PATH.relative_to(REPO_ROOT)),
            "desktop_api": str(DESKTOP_API_PATH.relative_to(REPO_ROOT)),
        },
        "errors": errors,
    }


def _audit_comfyui_workflow_adapter() -> dict[str, Any]:
    errors: list[str] = []
    adapter_source = COMFYUI_WORKFLOW_ADAPTER_PATH.read_text(encoding="utf-8") if COMFYUI_WORKFLOW_ADAPTER_PATH.exists() else ""
    task_service_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "task_service.py").read_text(encoding="utf-8")
    desktop_api_source = DESKTOP_API_PATH.read_text(encoding="utf-8") if DESKTOP_API_PATH.exists() else ""
    desktop_app_source = (REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "App.tsx").read_text(encoding="utf-8")
    for marker in (
        "COMFYUI_WORKFLOW_ADAPTER_SCHEMA_VERSION",
        "COMFYUI_WORKFLOW_SOURCE_FORMAT",
        "COMFYUI_WORKFLOW_EXTENSION_NAMESPACE",
        "COMFYUI_SUPPORTED_NODE_TYPES",
        "ComfyUiWorkflowLossError",
        "looks_like_comfyui_workflow",
        "import_comfyui_workflow",
        "export_comfyui_workflow",
        "task_graph_overlays",
        "opaque_nodes",
        "loss_report",
        "artifact_uri",
    ):
        if marker not in adapter_source:
            errors.append(f"ComfyUI workflow adapter owner missing required marker: {marker}")
    for marker in (
        "import_comfyui_workflow(",
        "export_comfyui_workflow(",
        "looks_like_comfyui_workflow(",
        "_graph_interop_source_format(",
        "_apply_task_graph_overlays(",
    ):
        if marker not in task_service_source:
            errors.append(f"task service is not routing ComfyUI interop through the shared adapter marker: {marker}")
    if 'exportTaskGraphFile: (payload: { graph_id: string; export_path?: string | null; format?: string | null })' not in desktop_api_source:
        errors.append("desktop API is not projecting the shared optional ComfyUI export-format field")
    for marker in (
        'Import task graph / workflow',
        'Export task graph / workflow',
        'comfyui_workflow',
        'formatTaskGraphImportExportError',
    ):
        if marker not in desktop_app_source:
            errors.append(f"Desktop app is not consuming the shared ComfyUI import/export bridge marker: {marker}")
    return {
        "contract": "loss_aware_comfyui_workflow_import_export_bridge",
        "owner": "astrabridge_sidecar.comfyui_workflow_adapter",
        "status": "pass" if not errors else "fail",
        "paths": {
            "comfyui_workflow_adapter": str(COMFYUI_WORKFLOW_ADAPTER_PATH.relative_to(REPO_ROOT)),
            "task_service": str((SIDECAR_ROOT / "astrabridge_sidecar" / "task_service.py").relative_to(REPO_ROOT)),
            "desktop_api": str(DESKTOP_API_PATH.relative_to(REPO_ROOT)),
            "desktop_app": "apps/astrabridge-desktop/src/App.tsx",
        },
        "errors": errors,
    }


def _audit_langgraph_stategraph_adapter() -> dict[str, Any]:
    errors: list[str] = []
    adapter_source = LANGGRAPH_STATEGRAPH_ADAPTER_PATH.read_text(encoding="utf-8") if LANGGRAPH_STATEGRAPH_ADAPTER_PATH.exists() else ""
    task_service_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "task_service.py").read_text(encoding="utf-8")
    desktop_app_source = (REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "App.tsx").read_text(encoding="utf-8")
    for marker in (
        "LANGGRAPH_STATEGRAPH_ADAPTER_SCHEMA_VERSION",
        "LANGGRAPH_STATEGRAPH_SOURCE_FORMAT",
        "LANGGRAPH_STATEGRAPH_EXTENSION_NAMESPACE",
        "LANGGRAPH_SUPPORTED_NODE_TYPES",
        "LangGraphStateGraphLossError",
        "langgraph_optional_dependency_status",
        "looks_like_langgraph_stategraph_manifest",
        "import_langgraph_stategraph_manifest",
        "export_langgraph_stategraph_manifest",
        "generate_langgraph_stategraph_python",
        "interrupt_before",
        "checkpointer",
        "subgraph",
        "thread_lineage",
    ):
        if marker not in adapter_source:
            errors.append(f"LangGraph StateGraph adapter owner missing required marker: {marker}")
    for marker in (
        "import_langgraph_stategraph_manifest(",
        "export_langgraph_stategraph_manifest(",
        "looks_like_langgraph_stategraph_manifest(",
        "LANGGRAPH_STATEGRAPH_SOURCE_FORMAT",
        "_graph_interop_source_format(",
        "_apply_task_graph_overlays(",
    ):
        if marker not in task_service_source:
            errors.append(f"task service is not routing LangGraph interop through the shared adapter marker: {marker}")
    for marker in (
        'TASK_GRAPH_LANGGRAPH_SOURCE_FORMAT',
        'PRIVATE/langgraph-stategraph/',
        'LangGraph StateGraph manifest',
    ):
        if marker not in desktop_app_source:
            errors.append(f"Desktop app is not consuming the shared LangGraph import/export bridge marker: {marker}")
    return {
        "contract": "optional_langgraph_stategraph_interop_bridge",
        "owner": "astrabridge_sidecar.langgraph_stategraph_adapter",
        "status": "pass" if not errors else "fail",
        "paths": {
            "langgraph_stategraph_adapter": str(LANGGRAPH_STATEGRAPH_ADAPTER_PATH.relative_to(REPO_ROOT)),
            "task_service": str((SIDECAR_ROOT / "astrabridge_sidecar" / "task_service.py").relative_to(REPO_ROOT)),
            "desktop_app": "apps/astrabridge-desktop/src/App.tsx",
        },
        "errors": errors,
    }


def _audit_runtime_rollout_gate() -> dict[str, Any]:
    errors: list[str] = []
    rollout_source = RUNTIME_ROLLOUT_GATE_PATH.read_text(encoding="utf-8") if RUNTIME_ROLLOUT_GATE_PATH.exists() else ""
    wrapper_source = RUN_RUNTIME_ROLLOUT_GATE_SCRIPT_PATH.read_text(encoding="utf-8") if RUN_RUNTIME_ROLLOUT_GATE_SCRIPT_PATH.exists() else ""
    runbook_source = RUNTIME_ROLLOUT_RUNBOOK_PATH.read_text(encoding="utf-8") if RUNTIME_ROLLOUT_RUNBOOK_PATH.exists() else ""
    for marker in (
        "RUNTIME_ROLLOUT_GATE_SCHEMA_VERSION",
        "RUNTIME_ROLLOUT_FEATURE_FLAG_SCHEMA_VERSION",
        "runtime_rollout_feature_flags",
        "run_runtime_rollout_gate",
        "capture_runtime_rollout_shadow_comparison",
        "capture_runtime_rollout_migration_evidence",
        "capture_runtime_rollout_rollback_readback",
        "_capture_desktop_visual_qa",
        "run_runtime_stability_gate",
        "scan_runtime_stability_artifacts",
    ):
        if marker not in rollout_source:
            errors.append(f"runtime rollout gate owner missing required marker: {marker}")
    if "from astrabridge_sidecar.runtime_rollout_gate import run_runtime_rollout_gate" not in wrapper_source:
        errors.append("runtime rollout gate CLI wrapper is not delegating to the shared owner")
    for marker in (
        "Runtime Rollout And Maintenance Runbook",
        "Shadow comparison must not execute the same side effect twice.",
        "Rollback in this scope means compatibility readback, not destructive reset.",
        "run_runtime_rollout_gate.py",
    ):
        if marker not in runbook_source:
            errors.append(f"runtime rollout runbook missing required marker: {marker}")
    return {
        "contract": "final_runtime_rollout_and_release_closure",
        "owner": "astrabridge_sidecar.runtime_rollout_gate",
        "status": "pass" if not errors else "fail",
        "paths": {
            "runtime_rollout_gate": str(RUNTIME_ROLLOUT_GATE_PATH.relative_to(REPO_ROOT)),
            "runtime_rollout_gate_script": str(RUN_RUNTIME_ROLLOUT_GATE_SCRIPT_PATH.relative_to(REPO_ROOT)),
            "runtime_rollout_runbook": str(RUNTIME_ROLLOUT_RUNBOOK_PATH.relative_to(REPO_ROOT)),
        },
        "errors": errors,
    }


def _audit_mcp_server_core() -> dict[str, Any]:
    errors: list[str] = []
    source = MCP_SERVER_CORE_PATH.read_text(encoding="utf-8") if MCP_SERVER_CORE_PATH.exists() else ""
    if not source:
        errors.append("shared MCP server core implementation is missing")
    for marker in (
        "class McpServerCore",
        "MCP_LATEST_PROTOCOL_VERSION",
        "MCP_SUPPORTED_PROTOCOL_VERSIONS",
        "def read_stdio_message(",
        "def run_stdio_mcp_server(",
        "class StreamableHttpMcpServer",
        "notifications/cancelled",
        "notifications/progress",
    ):
        if marker not in source:
            errors.append(f"shared MCP server core missing required marker: {marker}")
    adapter_report: dict[str, str] = {}
    for name, path in MCP_SERVER_ADAPTER_PATHS.items():
        adapter_source = path.read_text(encoding="utf-8") if path.exists() else ""
        adapter_report[name] = str(path.relative_to(REPO_ROOT))
        if not adapter_source:
            errors.append(f"MCP adapter missing: {name}")
            continue
        if "McpServerCore" not in adapter_source or "run_stdio_mcp_server" not in adapter_source:
            errors.append(f"MCP adapter does not use the shared core: {name}")
        if "def _read_first_nonempty_byte" in adapter_source or "def _read_json_object" in adapter_source:
            errors.append(f"MCP adapter still defines duplicate stdio framing helpers: {name}")
    return {
        "contract": "shared_mcp_server_core",
        "owner": "astrabridge_sidecar.mcp_server_core.McpServerCore",
        "status": "pass" if not errors else "fail",
        "path": str(MCP_SERVER_CORE_PATH.relative_to(REPO_ROOT)),
        "adapters": adapter_report,
        "errors": errors,
    }


def _audit_mcp_broker() -> dict[str, Any]:
    errors: list[str] = []
    broker_source = MCP_BROKER_PATH.read_text(encoding="utf-8") if MCP_BROKER_PATH.exists() else ""
    if not broker_source:
        errors.append("shared MCP broker implementation is missing")
    for marker in (
        "class McpBrokerService",
        "def invoke_tool(",
        "def invoke_capability(",
        "LoopbackMcpSession",
        "mcp_broker_tool_call",
    ):
        if marker not in broker_source:
            errors.append(f"shared MCP broker missing required marker: {marker}")
    runtime_source_path = SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_service.py"
    runtime_source = runtime_source_path.read_text(encoding="utf-8") if runtime_source_path.exists() else ""
    web_source_path = SIDECAR_ROOT / "astrabridge_sidecar" / "web_tool_service.py"
    web_source = web_source_path.read_text(encoding="utf-8") if web_source_path.exists() else ""
    server_source_path = SIDECAR_ROOT / "astrabridge_sidecar" / "server.py"
    server_source = server_source_path.read_text(encoding="utf-8") if server_source_path.exists() else ""
    if "_mcp_broker.invoke_tool(" not in runtime_source or "_mcp_broker.invoke_capability(" not in runtime_source:
        errors.append("runtime service is not routing normal dynamic capability calls through the shared MCP broker")
    if "set_mcp_broker" not in web_source or "self._mcp_broker.invoke_tool(" not in web_source:
        errors.append("web lane service is not routing through the shared MCP broker")
    if "self.context.mcp_broker.invoke_tool(" not in server_source or "self.context.mcp_broker.invoke_capability(" not in server_source:
        errors.append("HTTP capability routes are not routing through the shared MCP broker")
    return {
        "contract": "shared_mcp_broker_boundary",
        "owner": "astrabridge_sidecar.mcp_broker_service.McpBrokerService",
        "status": "pass" if not errors else "fail",
        "path": str(MCP_BROKER_PATH.relative_to(REPO_ROOT)),
        "errors": errors,
    }


def _audit_mcp_node_policy() -> dict[str, Any]:
    errors: list[str] = []
    source = MCP_NODE_POLICY_PATH.read_text(encoding="utf-8") if MCP_NODE_POLICY_PATH.exists() else ""
    if not source:
        errors.append("shared MCP node policy implementation is missing")
    for marker in (
        "MCP_NODE_TOOL_POLICY_SCHEMA_VERSION",
        "class McpToolPolicyDenied",
        "def resolve_node_mcp_tool_policy(",
        "def authorize_mcp_tool_call(",
        "approval_reused",
        "resource_uri_patterns",
        "budget_exhausted",
        "fingerprint",
    ):
        if marker not in source:
            errors.append(f"shared MCP node policy missing required marker: {marker}")
    contract_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "agent_orchestration_contract.py").read_text(encoding="utf-8")
    compiler_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "agent_orchestration_compiler.py").read_text(encoding="utf-8")
    runtime_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_service.py").read_text(encoding="utf-8")
    task_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "task_service.py").read_text(encoding="utf-8")
    broker_source = MCP_BROKER_PATH.read_text(encoding="utf-8") if MCP_BROKER_PATH.exists() else ""
    if "resolve_node_mcp_tool_policy" not in contract_source:
        errors.append("agent orchestration contract is not validating the shared MCP node policy fields")
    if "mcp_tool_policy" not in compiler_source:
        errors.append("agent orchestration compiler is not snapshotting node MCP tool policy")
    if "_graph_node_mcp_tool_policy_snapshots" not in runtime_source or "dynamic_tool_policy_blocked" not in runtime_source:
        errors.append("runtime service is not enforcing or snapshotting per-node MCP tool policy")
    if "_compiled_node_mcp_tool_policies" not in task_source or '"mcp_tool_policy"' not in task_source:
        errors.append("task service is not preserving node MCP tool policy snapshots through run refs and worker bindings")
    if "authorize_mcp_tool_call" not in broker_source:
        errors.append("shared MCP broker is not re-authorizing dispatch through the shared node policy owner")
    return {
        "contract": "node_scoped_mcp_tool_and_resource_policy",
        "owner": "astrabridge_sidecar.mcp_node_policy",
        "status": "pass" if not errors else "fail",
        "path": str(MCP_NODE_POLICY_PATH.relative_to(REPO_ROOT)),
        "errors": errors,
    }


def _audit_multimodal_result_envelope() -> dict[str, Any]:
    errors: list[str] = []
    source = MULTIMODAL_RESULT_ENVELOPE_PATH.read_text(encoding="utf-8") if MULTIMODAL_RESULT_ENVELOPE_PATH.exists() else ""
    if not source:
        errors.append("shared multimodal result envelope implementation is missing")
    for marker in (
        "MCP_TYPED_RESULT_SCHEMA_VERSION",
        "def enrich_capability_result(",
        "def enrich_yunwu_image_result(",
        "def enrich_web_result(",
        "workspace://",
        "digest_sha256",
        "size_bytes",
    ):
        if marker not in source:
            errors.append(f"shared multimodal result envelope missing required marker: {marker}")
    capability_server_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "astrabridge_capabilities_mcp_server.py").read_text(encoding="utf-8")
    web_server_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "astrabridge_web_mcp_server.py").read_text(encoding="utf-8")
    yunwu_server_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "yunwu_image_mcp_server.py").read_text(encoding="utf-8")
    artifacts_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "capabilities" / "artifacts.py").read_text(encoding="utf-8")
    web_service_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "web_tool_service.py").read_text(encoding="utf-8")
    if "typed_result_text_summary" not in capability_server_source:
        errors.append("capability MCP server is not projecting typed multimodal result summaries")
    if "enrich_web_result" not in web_server_source:
        errors.append("web MCP server is not projecting typed web result envelopes")
    if "enrich_yunwu_image_result" not in yunwu_server_source:
        errors.append("Yunwu MCP server is not projecting typed image result envelopes")
    if "protocol_artifact_snapshot" not in artifacts_source:
        errors.append("capability artifact snapshot is not projecting protocol-safe artifact metadata")
    if "enrich_web_result" not in web_service_source:
        errors.append("web lane persistence is not projecting typed web result metadata")
    return {
        "contract": "typed_multimodal_mcp_results_and_safe_artifacts",
        "owner": "astrabridge_sidecar.multimodal_result_envelope",
        "status": "pass" if not errors else "fail",
        "path": str(MULTIMODAL_RESULT_ENVELOPE_PATH.relative_to(REPO_ROOT)),
        "errors": errors,
    }


def _audit_durable_run_store() -> dict[str, Any]:
    """Verify the workspace-local durable run/event owner without opening a DB."""

    errors: list[str] = []
    if not DURABLE_RUN_STORE_PATH.exists():
        errors.append("durable run store implementation is missing")
        source = ""
    else:
        source = DURABLE_RUN_STORE_PATH.read_text(encoding="utf-8")
    required_markers = (
        "DURABLE_RUN_STORE_SCHEMA_VERSION",
        "DURABLE_RUN_STORE_FILENAME",
        "PRAGMA journal_mode=WAL",
        "CREATE TABLE IF NOT EXISTS runs",
        "CREATE TABLE IF NOT EXISTS run_events",
        "CREATE TABLE IF NOT EXISTS node_attempts",
        "CREATE TABLE IF NOT EXISTS leases",
        "CREATE TABLE IF NOT EXISTS inbox",
        "CREATE TABLE IF NOT EXISTS outbox",
        "CREATE TABLE IF NOT EXISTS external_operations",
        "StateVersionConflict",
        "compare_and_swap_run",
        "migrate_legacy_state",
        "rebuild_run_projection",
    )
    for marker in required_markers:
        if marker not in source:
            errors.append(f"durable run store missing required marker: {marker}")
    return {
        "contract": "workspace_local_durable_run_and_event_store",
        "owner": "astrabridge_sidecar.durable_run_store.DurableRunEventStore",
        "status": "pass" if not errors else "fail",
        "path": str(DURABLE_RUN_STORE_PATH.relative_to(REPO_ROOT)),
        "errors": errors,
    }


def _audit_graph_scheduler() -> dict[str, Any]:
    """Verify the async graph scheduler is the runtime dispatch owner."""

    errors: list[str] = []
    source = GRAPH_SCHEDULER_PATH.read_text(encoding="utf-8") if GRAPH_SCHEDULER_PATH.exists() else ""
    if not source:
        errors.append("graph scheduler implementation is missing")
    for marker in (
        "class DurableGraphScheduler",
        "def submit(",
        "def wait(",
        "def shutdown(",
        "_worker_loop",
        "redact_sensitive",
    ):
        if marker not in source:
            errors.append(f"graph scheduler missing required marker: {marker}")
    runtime_source_path = SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_service.py"
    runtime_source = runtime_source_path.read_text(encoding="utf-8") if runtime_source_path.exists() else ""
    for marker in ("queue_task_graph_run", "_run_graph_scheduler_job", "graph_run_status"):
        if marker not in runtime_source:
            errors.append(f"runtime scheduler bridge missing required marker: {marker}")
    return {
        "contract": "async_durable_graph_scheduler",
        "owner": "astrabridge_sidecar.graph_scheduler.DurableGraphScheduler + RuntimeService",
        "status": "pass" if not errors else "fail",
        "path": str(GRAPH_SCHEDULER_PATH.relative_to(REPO_ROOT)),
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


def _audit_protocol_schema_generation() -> dict[str, Any]:
    """Verify the canonical schema, projections, fixtures, and compatibility manifest."""

    required_paths = {
        "schema": PROTOCOL_SCHEMA_PATH,
        "manifest": PROTOCOL_MANIFEST_PATH,
        "generator": PROTOCOL_GENERATOR_PATH,
        "python_projection": PROTOCOL_PY_GENERATED_PATH,
        "typescript_projection": PROTOCOL_TS_GENERATED_PATH,
        "fixtures": PROTOCOL_FIXTURE_PATH,
    }
    errors: list[str] = []
    missing = [name for name, path in required_paths.items() if not path.exists()]
    if missing:
        errors.append(f"missing canonical protocol inputs: {', '.join(sorted(missing))}")
    generator_result: subprocess.CompletedProcess[str] | None = None
    fixture_counts = {"valid": 0, "invalid": 0}
    definition_names: list[str] = []
    if not missing:
        generator_result = subprocess.run(
            [sys.executable, str(PROTOCOL_GENERATOR_PATH), "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if generator_result.returncode != 0:
            errors.append("generated Python/TypeScript protocol projections are stale")
        try:
            schema = json.loads(PROTOCOL_SCHEMA_PATH.read_text(encoding="utf-8"))
            manifest = compatibility_manifest()
            fixtures = json.loads(PROTOCOL_FIXTURE_PATH.read_text(encoding="utf-8"))
            definition_names = sorted(dict(schema.get("$defs") or {}))
            required_definitions = {
                "ArtifactRef",
                "ContentPart",
                "AgentEnvelope",
                "AgentTask",
                "RunEvent",
                "CapabilityInput",
                "CapabilityOutput",
                "GraphDefinition",
                "CompiledPlan",
            }
            missing_definitions = sorted(required_definitions.difference(definition_names))
            if missing_definitions:
                errors.append(f"canonical protocol schema missing definitions: {', '.join(missing_definitions)}")
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                errors.append("canonical protocol schema must declare JSON Schema 2020-12")
            if schema.get("$id") != "https://astrabridge.dev/schemas/protocol/v1.json":
                errors.append("canonical protocol schema id drifted")
            if schema.get("x-astrabridge-schema-version") != SCHEMA_VERSION:
                errors.append("canonical protocol schema version drifted")
            if manifest.get("target_schema") != SCHEMA_VERSION or not bool(manifest.get("idempotent")):
                errors.append("compatibility manifest does not declare current-write/idempotent migration rules")
            for kind, payload in dict(fixtures.get("valid") or {}).items():
                fixture_counts["valid"] += 1
                if not validation_verdict(str(kind), payload):
                    errors.append(f"canonical positive fixture rejected: {kind}")
            for case_id, case in dict(fixtures.get("invalid") or {}).items():
                fixture_counts["invalid"] += 1
                if validation_verdict(str(case.get("kind") or ""), case.get("payload")):
                    errors.append(f"canonical negative fixture accepted: {case_id}")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"canonical protocol schema audit could not load inputs: {exc}")
    return {
        "contract": "canonical_protocol_schema_and_codegen",
        "owner": "astrabridge_sidecar.protocol.schema.v1 + scripts/generate_protocol_types.py",
        "status": "pass" if not errors else "fail",
        "schema_version": SCHEMA_VERSION,
        "definition_names": definition_names,
        "fixture_counts": fixture_counts,
        "generator_returncode": None if generator_result is None else generator_result.returncode,
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
        _audit_mcp_server_core(),
        _audit_mcp_broker(),
        _audit_mcp_node_policy(),
        _audit_multimodal_result_envelope(),
        _audit_runtime_observability(),
        _audit_runtime_stability_gate(),
        _audit_runtime_rollout_gate(),
        _audit_node_type_registry(),
        _audit_comfyui_workflow_adapter(),
        _audit_langgraph_stategraph_adapter(),
        _audit_desktop_sidecar_supervision(),
        _audit_durable_run_store(),
        _audit_graph_scheduler(),
        _audit_protocol_schema_generation(),
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
