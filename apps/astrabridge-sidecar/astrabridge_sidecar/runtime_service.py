from __future__ import annotations

import base64
import binascii
import hashlib
import json
import mimetypes
import os
import posixpath
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time
import zlib
from collections import deque
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent_orchestration_compiler import compile_agent_orchestration_graph
from .app_server_client import AppServerClient, JsonRpcError, app_server_command
from .coding_kernel import (
    ContextSection,
    build_context_budget,
    build_context_compaction_handoff_contract,
    compact_context_compaction_handoff_contract,
    estimate_tool_schema_tokens,
    normalize_context_budget_policy,
    project_turn_to_coding_events,
    selected_text_by_section,
)
from .common import WORKSPACE_STATE_DIRNAME, append_jsonl, new_id, now_iso, read_json, write_json
from .codex_kernel_probe import discover_codex_binary_and_version, resolve_codex_binary_metadata
from .codex_kernel_snapshot import build_codex_kernel_probe_snapshot, observe_protocol_features
from .codex_mcp_probe import probe_mcp_compatibility
from .codex_plugin_fixture_catalog import materialize_controlled_plugin_fixture_catalog
from .codex_plugin_install_apply import execute_plugin_install
from .codex_plugin_install_plan import build_plugin_install_plan
from .codex_plugin_skill_registry import build_plugin_skill_registry_snapshot
from .codex_plugin_probe import probe_plugin_discovery
from .codex_skill_plugin_creator_scenario import execute_plugin_creator_skill_scenario
from .codex_skill_enablement import (
    apply_skill_enablement_snapshot,
    register_pending_skill_approval_rules,
    update_skill_enablement_snapshot,
)
from .codex_skill_probe import probe_skill_discovery
from .dogfood_run_service import MAX_BROWSER_SMOKE_ACTIONS
from .durable_run_store import LeaseBusy, StateVersionConflict
from .graph_dispatch_control import GraphDispatchController, GraphDispatchRequest
from .graph_scheduler import DurableGraphScheduler
from .astrabridge_capabilities_mcp_server import _tools as astrabridge_capability_dynamic_tools
from .astrabridge_web_mcp_server import _tools as astrabridge_web_dynamic_tools
from .capabilities.capability_routes import resolve_capability_route_entry
from .capabilities.runtime import CapabilityRuntime
from .mcp_config_service import McpConfigService
from .modal_service import ModalService
from .model_catalog import (
    ASTRABRIDGE_MODELS_CACHE_FILENAME,
    ASTRABRIDGE_MODEL_CATALOG_FILENAME,
    preferred_provider_model_record,
)
from .mcp_broker_service import McpBrokerService
from .profile_service import ProfileService
from .providers import (
    REASONING_ARTIFACT_PROVENANCE_SCHEMA_VERSION,
    REASONING_ARTIFACT_REPLAY_SCOPE,
    REASONING_ARTIFACT_RETENTION,
    HistoryProjector,
    NeutralMessage,
    ReasoningArtifact,
    build_neutral_transcript,
    build_turn_transition,
    classify_runtime_failure,
    compact_turn_transition,
    complete_turn_transition,
    get_provider_profile,
    legacy_runtime_route_admission,
    normalize_endpoint_identity,
    resolve_runtime_route_admission,
    assert_turn_transition_admitted,
)
from .providers.transports import transport_class_for_profile
from .providers.transports.base import transport_signature_for_class
from .mcp_node_policy import (
    McpToolPolicyDenied,
    allowed_mcp_dynamic_tool_names,
    resolve_node_mcp_tool_policy,
)
from .node_type_registry import journaled_compiled_plan_executor_capability_report
from .router_service import ROUTER_ENV_KEY, ROUTER_PORT
from .runtime_config_service import RuntimeConfigService, codex_model_id, codex_reasoning_effort
from .runtime_client_pool import RuntimeClientPool
from .runtime_graph_run_dispatch_service import RuntimeGraphRunDispatchService
from .runtime_guardrails import evaluate_runtime_guardrails
from .runtime_observability import enrich_runtime_event, load_host_lineage_events
from .communication_isolation import validate_typed_communication_isolation
from .security import SecurityError, redact_sensitive, resolve_under, scan_text_for_secrets
from .secret_service import SecretService
from .task_service import GraphContractValidationError, _compact_text, _display_thread_name
from .task_graph_contract import validate_graph_definition
from .protocol.generated.v1 import validate_protocol_payload
from .tool_context_service import ToolContextService, sanitize_tool_context
from .usage_signal import normalize_usage_signal, usage_not_available
from .web_tool_service import AstraBridgeWebService
from .wsl_dependency_service import ASTRABRIDGE_WSL_BIN, ASTRABRIDGE_WSL_CODEX_HOME, ASTRABRIDGE_WSL_ROOT
from .yunwu_image_mcp_server import _summarize_image_result as summarize_yunwu_image_result
from .yunwu_image_mcp_server import _tools as yunwu_image_dynamic_tools
from .yunwu_image_service import YunwuImageService


EVENT_RESPONSE_STRING_LIMIT = 4000
EVENT_RESPONSE_LIST_LIMIT = 40
EVENT_RESPONSE_DEPTH_LIMIT = 6
EVENT_HYDRATE_TAIL_LIMIT = 5000
EVENT_HYDRATE_MAX_BYTES = 4 * 1024 * 1024
ATTACHMENT_STAGE_MAX_FILES = 200
ATTACHMENT_STAGE_MAX_FILE_BYTES = 25 * 1024 * 1024
ATTACHMENT_STAGE_MAX_TOTAL_BYTES = 64 * 1024 * 1024
APP_SERVER_INIT_TIMEOUT_SECONDS = 20.0
THREAD_START_TIMEOUT_SECONDS = 20.0
THREAD_FORK_TIMEOUT_SECONDS = 20.0
THREAD_READ_TIMEOUT_SECONDS = 20.0
STARTUP_THREAD_PROBE_TIMEOUT_SECONDS = 2.0
THREAD_LIST_TIMEOUT_SECONDS = 20.0
THREAD_CREATE_RUNTIME_LOCK_TIMEOUT_SECONDS = 12.0
THREAD_CREATE_OPERATION_TTL_SECONDS = 60.0 * 60.0
THREAD_CREATE_OPERATION_LIMIT = 128
TURN_START_TIMEOUT_SECONDS = 45.0
GRAPH_LIVE_LEASE_TTL_SECONDS = 60
GRAPH_LIVE_LEASE_HEARTBEAT_SECONDS = 15
GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_HISTORY_MESSAGES = 12
GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_REPLAYABLE_ARTIFACTS = 4
GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_JSON_BYTES = 32768
APP_SERVER_IMAGE_VERIFY_TIMEOUT_SECONDS = 60.0
APP_SERVER_IMAGE_VERIFY_MAX_ATTEMPTS = 2
TURN_RUNTIME_PIN_SECONDS = 300.0
TERMINAL_TURN_NOTIFICATION_METHODS = {
    "turn/completed",
    "turn/failed",
    "turn/cancelled",
    "turn/errored",
    "turn/aborted",
}
TERMINAL_TURN_STATUSES = {"completed", "failed", "cancelled", "errored"}
TERMINAL_TURN_NOTIFICATION_LIMIT = 256
TERMINAL_RESULT_GRACE_SECONDS = 2.0
VALID_COLLABORATION_MODES = {"default", "plan"}
VALID_CONTEXT_MODES = {"default", "full", "minimal_text", "minimal_visual", "no_context"}
VALID_EXECUTION_BACKENDS = {"app_server", "native_kernel"}
VALID_TURN_EXECUTION_POLICIES = {"standard", "patch_only", "no_tools"}
PATCH_ONLY_EXECUTION_POLICY = "patch_only"
NO_TOOLS_EXECUTION_POLICY = "no_tools"
BROWSER_SMOKE_TOOL_NAME = "astrabridge_browser_smoke"
BROWSER_SMOKE_TOOL_ALIASES = {BROWSER_SMOKE_TOOL_NAME}
THREAD_CREATE_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,96}$")
_OPENAI_DEFAULT_MODEL = str(
    (preferred_provider_model_record("openai", include_deprecated=False) or {}).get("native_model") or "gpt-5.5"
)

def _is_astrabridge_web_tool(tool: str) -> bool:
    return str(tool or "").strip().startswith("astrabridge_web_")


class _GraphDurablePause(RuntimeError):
    """Preserve durable graph state without finalizing a failure."""


class ContextBudgetPreflightError(ValueError):
    """A request cannot safely enter a provider route with its current context."""

    def __init__(self, report: dict[str, Any], message: str) -> None:
        super().__init__(message)
        self.report = dict(report or {})


class RuntimeRouteAdmissionError(ValueError):
    """A selected model route cannot start without an explicit safe posture."""

    def __init__(self, admission: dict[str, Any], *, operation: str) -> None:
        self.admission = deepcopy(dict(admission or {}))
        self.operation = str(operation or "runtime_start")
        status = str(self.admission.get("status") or "blocked").strip() or "blocked"
        reasons = list(dict(self.admission.get("degradation") or {}).get("reasons") or [])
        first_reason = next(
            (
                str(dict(item).get("message") or "").strip()
                for item in reasons
                if isinstance(item, dict) and str(dict(item).get("message") or "").strip()
            ),
            "The selected model route is not admitted for this task start.",
        )
        if status == "confirmation_required":
            message = f"Route confirmation is required before {self.operation}: {first_reason}"
        else:
            message = f"Route admission blocked {self.operation}: {first_reason}"
        super().__init__(message)


class _GraphDispatchCrashBeforeExternalCall(_GraphDurablePause):
    """Test-only hook that simulates a process crash before provider dispatch."""


class _GraphDispatchCrashAfterHandleAccepted(_GraphDurablePause):
    """Test-only hook that simulates a crash after a remote handle is known."""


class RuntimeService:
    def __init__(
        self,
        project_service,
        modal_service: ModalService,
        runtime_config: RuntimeConfigService | None = None,
        secret_service: SecretService | None = None,
        mcp_config: McpConfigService | None = None,
        asset_registry: Any | None = None,
        project_context: Any | None = None,
        task_service: Any | None = None,
        task_conversation: Any | None = None,
        dogfood_run: Any | None = None,
        web_tool_service: Any | None = None,
        profile_service: ProfileService | None = None,
        router_service: Any | None = None,
        router_config_service: Any | None = None,
        key_injector: Any | None = None,
        mcp_broker_service: Any | None = None,
    ) -> None:
        self._projects = project_service
        self._modals = modal_service
        self._secrets = secret_service or SecretService()
        self._mcp_config = mcp_config or getattr(runtime_config, "_mcp_config", None) or McpConfigService()
        self._asset_registry = asset_registry
        self._project_context = project_context
        self._tasks = task_service
        self._task_conversation = task_conversation
        self._dogfood_run = dogfood_run
        self._web_tools = web_tool_service or AstraBridgeWebService(project_service)
        self._tool_context = ToolContextService(project_service, task_service)
        codex_home_resolver = getattr(self._projects, "current_runtime_codex_home", None)
        self._runtime_config = runtime_config or RuntimeConfigService(
            codex_home_resolver=codex_home_resolver if callable(codex_home_resolver) else None,
            secret_service=self._secrets,
            mcp_config=self._mcp_config,
        )
        self._profiles = profile_service or ProfileService()
        self._router = router_service
        self._router_config = router_config_service
        self._key_injector = key_injector
        self._project_tools = None
        self._native_turn_loop = None
        self._client: AppServerClient | None = None
        self._runtime_signature: tuple[Any, ...] | None = None
        self._runtime_client_pool = RuntimeClientPool()
        self._runtime_lane_environments: dict[str, dict[str, str]] = {}
        self._runtime_projection_is_pooled = False
        self._events: list[dict[str, Any]] = []
        self._hydrated_event_log_path: Path | None = None
        self._context_guard_continue_once: set[str] = set()
        self._lock = threading.RLock()
        self._thread_cache_lock = threading.RLock()
        self._runtime_operation_lock = threading.RLock()
        self._runtime_operation_local = threading.local()
        self._thread_create_operation_lock = threading.RLock()
        self._thread_create_operations: dict[str, dict[str, Any]] = {}
        self._runtime_start_turn_in_progress = False
        self._runtime_thread_start_in_progress = False
        self._runtime_pin_signature: tuple[Any, ...] | None = None
        self._runtime_pin_until_monotonic = 0.0
        self._runtime_pin_thread_id: str | None = None
        self._runtime_pin_turn_id: str | None = None
        self._mcp_status_thread_signature: tuple[Any, ...] | None = None
        self._mcp_status_thread_id: str | None = None
        self._active_turn_execution_policies: dict[str, dict[str, Any]] = {}
        self._terminal_snapshot_keys: set[str] = set()
        self._terminal_turn_notifications: dict[tuple[str, str], dict[str, Any]] = {}
        self._observed_turn_aliases: dict[tuple[str, str], dict[str, Any]] = {}
        self._fail_closed_turn_interrupts: set[tuple[str, str]] = set()
        self._graph_scheduler = DurableGraphScheduler(
            self._run_graph_scheduler_job,
            max_workers=4,
            max_queue_size=128,
        )
        self._graph_dispatch_control = GraphDispatchController()
        self._graph_run_dispatch = RuntimeGraphRunDispatchService(self)
        self._yunwu_image = YunwuImageService()
        self._capability_runtime = (
            CapabilityRuntime(router_config=self._router_config, key_injector=self._key_injector)
            if self._router_config is not None
            else None
        )
        self._mcp_broker = mcp_broker_service or McpBrokerService(
            project_service=self._projects,
            capability_runtime=self._capability_runtime,
            yunwu_image_service=self._yunwu_image,
            mcp_config=self._mcp_config,
        )
        set_broker = getattr(self._web_tools, "set_mcp_broker", None)
        if callable(set_broker):
            set_broker(self._mcp_broker)
        self._reconcile_durable_graph_scheduler_runs()

    @staticmethod
    def _graph_live_operation_id(*, run_id: str, node_id: str, attempt: int, kind: str) -> str:
        seed = f"{str(kind or 'provider_turn_start').strip()}:{str(run_id or '').strip()}:{str(node_id or '').strip()}:{max(1, int(attempt))}"
        return f"graph-op-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}"

    @staticmethod
    def _graph_live_completion_inbox_key(
        *,
        run_id: str,
        node_id: str,
        attempt: int,
        execution_thread_id: str,
        turn_id: str,
    ) -> str:
        seed = ":".join(
            (
                str(run_id or "").strip(),
                str(node_id or "").strip(),
                str(max(1, int(attempt))),
                str(execution_thread_id or "").strip(),
                str(turn_id or "").strip(),
            )
        )
        return f"graph-inbox-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}"

    @staticmethod
    def _graph_live_parse_external_handle(value: str | None) -> tuple[str, str]:
        clean = str(value or "").strip()
        if not clean or ":" not in clean:
            return "", ""
        thread_id, turn_id = clean.rsplit(":", 1)
        return thread_id.strip(), turn_id.strip()

    @staticmethod
    def _graph_live_resume_payload(payload: dict[str, Any]) -> dict[str, Any]:
        resume_payload = {
            "graph_id": payload.get("graph_id"),
            "budget": deepcopy(dict(payload.get("budget") or {})) if isinstance(payload.get("budget"), dict) else {},
        }
        parent_thread_id = str(payload.get("parent_thread_id") or "").strip()
        if parent_thread_id:
            resume_payload["parent_thread_id"] = parent_thread_id
        if "_scheduler_lease_ttl_seconds" in payload:
            resume_payload["_scheduler_lease_ttl_seconds"] = deepcopy(payload["_scheduler_lease_ttl_seconds"])
        return resume_payload

    @staticmethod
    def _graph_live_parent_context(payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        raw = payload.get("_parent_run_context")
        return dict(raw) if isinstance(raw, dict) else {}

    @staticmethod
    def _graph_live_seed_incoming_handoffs(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        if not isinstance(payload, dict):
            return {}
        raw = payload.get("_seed_incoming_handoffs")
        if not isinstance(raw, dict):
            return {}
        seeded: dict[str, list[dict[str, Any]]] = {}
        for node_id, entries in raw.items():
            clean_node_id = str(node_id or "").strip()
            if not clean_node_id:
                continue
            normalized_entries = [deepcopy(dict(item)) for item in list(entries or []) if isinstance(item, dict)]
            if normalized_entries:
                seeded[clean_node_id] = normalized_entries
        return seeded

    @staticmethod
    def _graph_live_effective_timeout_ms(*, graph_node: dict[str, Any], compiled_node: dict[str, Any]) -> int | None:
        candidates = (
            dict(graph_node.get("execution_policy") or {}).get("timeout_ms"),
            graph_node.get("timeout_ms"),
            dict(compiled_node.get("execution_policy") or {}).get("timeout_ms"),
            compiled_node.get("timeout_ms"),
        )
        for candidate in candidates:
            try:
                value = int(candidate)
            except Exception:
                continue
            if value > 0:
                return value
        return None

    def _graph_live_resolve_subgraph_definition(
        self,
        *,
        graph_ref: str,
        current_graph_id: str,
        parent_context: dict[str, Any],
    ) -> dict[str, Any]:
        clean_graph_ref = str(graph_ref or "").strip()
        if not clean_graph_ref:
            raise GraphContractValidationError("Subgraph graph_ref is required.")
        resolved = self._tasks.graph_definition(clean_graph_ref)
        if not resolved:
            raise GraphContractValidationError(
                f"Subgraph graph_ref `{clean_graph_ref}` does not resolve to a saved graph in the current task."
            )
        resolved_graph = validate_graph_definition(deepcopy(resolved))
        resolved_graph_id = str(resolved_graph.get("graph_id") or "").strip()
        if not resolved_graph_id:
            raise GraphContractValidationError(f"Subgraph graph_ref `{clean_graph_ref}` resolved to an invalid graph_id.")
        if resolved_graph_id == str(current_graph_id or "").strip():
            raise GraphContractValidationError("Subgraph graph_ref cannot recursively target the current graph.")
        ancestor_graph_ids = {
            str(item).strip()
            for item in list(parent_context.get("ancestor_graph_ids") or [])
            if str(item or "").strip()
        }
        if resolved_graph_id in ancestor_graph_ids:
            raise GraphContractValidationError(
                f"Subgraph graph_ref `{clean_graph_ref}` would create a recursive graph invocation chain."
            )
        return resolved_graph

    def _graph_live_build_seed_subgraph_handoff(
        self,
        *,
        parent_graph: dict[str, Any],
        parent_graph_id: str,
        parent_run_id: str,
        parent_node_id: str,
        worker_thread_id: str,
        child_graph: dict[str, Any],
        child_entry_node: dict[str, Any],
        typed_input_value: Any,
        artifact_root: Path,
    ) -> dict[str, Any]:
        target_inputs = self._tasks._graph_node_port_map(child_entry_node, direction="inputs")
        target_ports = [
            dict(item)
            for item in target_inputs.values()
            if isinstance(item, dict)
        ]
        typed_value_is_text = isinstance(typed_input_value, str)
        typed_value_is_structured = isinstance(typed_input_value, (dict, list))

        def _target_port_rank(port: dict[str, Any]) -> tuple[int, int, int]:
            port_id = str(port.get("port_id") or "").strip()
            port_type = str(port.get("port_type") or "").strip()
            explicit_business_input = 0 if port_id in {"task_context", "context", "task_input"} else 1
            type_match = 1 if (
                (typed_value_is_text and port_type == "text")
                or (typed_value_is_structured and port_type == "structured_json")
            ) else 0
            required = 1 if bool(port.get("required")) else 0
            return (explicit_business_input, type_match, required)

        target_ports.sort(key=_target_port_rank, reverse=True)
        target_port = target_ports[0] if target_ports else None
        if not isinstance(target_port, dict):
            raise GraphContractValidationError(
                f"{self._tasks._graph_node_label(child_graph, str(child_entry_node.get('node_id') or ''))} does not expose a typed input port for live subgraph injection."
            )
        target_port_id = str(target_port.get("port_id") or "").strip()
        if not target_port_id:
            raise GraphContractValidationError("Live subgraph entry port is missing a port_id.")
        target_port_type = str(target_port.get("port_type") or "structured_json").strip() or "structured_json"
        seeded_value = deepcopy(typed_input_value)
        if target_port_type == "text" and not isinstance(seeded_value, str):
            seeded_value = json.dumps(seeded_value, ensure_ascii=False)
        synthetic_source_node = {
            "node_id": f"{parent_node_id}__subgraph_seed_source",
            "label": f"{parent_node_id} subgraph seed",
            "provider_id": None,
            "model_id": None,
            "ports": {
                "outputs": [
                    {
                        "port_id": "seed_output",
                        "port_type": target_port_type,
                        "shape": str(target_port.get("shape") or "single").strip() or "single",
                        "required": True,
                        **({"schema_ref": str(target_port.get("schema_ref") or "").strip()} if str(target_port.get("schema_ref") or "").strip() else {}),
                        **({"artifact_kind": str(target_port.get("artifact_kind") or "").strip()} if str(target_port.get("artifact_kind") or "").strip() else {}),
                    }
                ]
            },
        }
        synthetic_edge = {
            "edge_id": f"{parent_node_id}__subgraph_seed_edge",
            "from_node_id": str(synthetic_source_node.get("node_id") or "").strip(),
            "to_node_id": str(child_entry_node.get("node_id") or "").strip(),
            "edge_type": "subgraph_seed",
            "handoff_contract": {
                "port_bindings": [{"from_port_id": "seed_output", "to_port_id": target_port_id}],
                "required_output_schema_refs": [
                    str(target_port.get("schema_ref") or "").strip()
                ]
                if str(target_port.get("schema_ref") or "").strip()
                else [],
            },
        }
        synthetic_graph = {
            "graph_id": str(child_graph.get("graph_id") or "").strip(),
            "schema_registry": deepcopy(dict(child_graph.get("schema_registry") or {})),
            "nodes": [deepcopy(synthetic_source_node), deepcopy(child_entry_node)],
            "edges": [deepcopy(synthetic_edge)],
        }
        seed_root = artifact_root / "subgraph-seed"
        seed_root.mkdir(parents=True, exist_ok=True)
        output_json_rel = (seed_root / "parent-output.json").relative_to(self._projects.require_workspace_root()).as_posix()
        output_envelope_rel = (seed_root / "parent-output-envelope.json").relative_to(self._projects.require_workspace_root()).as_posix()
        input_envelope_rel = (seed_root / "parent-input-envelope.json").relative_to(self._projects.require_workspace_root()).as_posix()
        agent_envelope_rel = (seed_root / "agent-envelope.json").relative_to(self._projects.require_workspace_root()).as_posix()
        output_bundle = {
            "graph_id": parent_graph_id,
            "run_id": parent_run_id,
            "task_id": str(parent_graph.get("task_id") or child_graph.get("task_id") or "").strip(),
            "trace_id": f"trace-{parent_run_id}",
            "context_id": f"context-{parent_run_id}",
            "node_id": parent_node_id,
            "worker_thread_id": worker_thread_id,
            "typed_output_values": {"seed_output": deepcopy(seeded_value)},
            "machine_result": {
                "status": "seeded",
                "executor": "subgraph_seed",
                "target_graph_id": str(child_graph.get("graph_id") or "").strip(),
            },
            "human_summary": "",
            "status": "completed",
            "attempt_count": 1,
            "retry_count": 0,
            "budget": {},
            "created_at": now_iso(),
            "provider_id": None,
            "model": None,
        }
        write_json(self._projects.require_workspace_root() / output_json_rel, output_bundle)
        write_json(
            self._projects.require_workspace_root() / input_envelope_rel,
            {
                "schema_version": "astrabridge-subgraph-seed-input-v1",
                "typed_input_port_id": target_port_id,
                "created_at": now_iso(),
            },
        )
        write_json(
            self._projects.require_workspace_root() / output_envelope_rel,
            {
                "schema_version": "astrabridge-subgraph-seed-output-v1",
                "typed_output_values": {"seed_output": deepcopy(seeded_value)},
                "created_at": now_iso(),
            },
        )
        agent_envelope = self._tasks._build_graph_worker_agent_envelope(  # noqa: SLF001
            graph=synthetic_graph,
            edge=synthetic_edge,
            source_node=synthetic_source_node,
            target_node=child_entry_node,
            output_bundle=output_bundle,
            input_envelope={
                "message_parts": [
                    {
                        "part_type": "machine_result",
                        "port_type": "structured_json",
                        "path": output_json_rel,
                        "preview": _compact_text(dict(output_bundle.get("machine_result") or {}), limit=240),
                    }
                ],
                "artifact_refs": [],
                "resource_refs": [],
                "exclude_private_memory": True,
                "message_part_types": ["machine_result"],
                "context_policy": {
                    "history_mode": "none",
                    "artifact_mode": "none",
                    "exclude_private_memory": True,
                    "include_machine_results": True,
                    "include_human_summaries": False,
                    "summary_strategy": "none",
                    "history_length": 0,
                    "included_artifacts": [],
                    "resource_refs": [],
                },
                "handoff_contract": deepcopy(dict(synthetic_edge.get("handoff_contract") or {})),
            },
            bundle_paths={
                "output_json": output_json_rel,
                "summary_md": output_json_rel,
                "output_envelope_json": output_envelope_rel,
                "input_envelope_json": input_envelope_rel,
            },
        )
        agent_envelope["metadata"] = {
            **dict(agent_envelope.get("metadata") or {}),
            "injection_mode": "subgraph_entry_seed",
        }
        write_json(self._projects.require_workspace_root() / agent_envelope_rel, agent_envelope)
        self._tasks.durable_run_store().record_agent_envelope(agent_envelope)
        return {
            "handoff": {
                "edge_id": str(synthetic_edge.get("edge_id") or "").strip(),
                "to_node_id": str(child_entry_node.get("node_id") or "").strip(),
                "edge_type": "subgraph_seed",
                "downstream_input": {
                    "source": "subgraph_seed",
                    "run_id": parent_run_id,
                    "agent_envelope_path": agent_envelope_rel,
                },
            },
            "agent_envelope_path": agent_envelope_rel,
        }

    def _graph_live_load_node_output_bundle(
        self,
        *,
        run_id: str,
        node_id: str,
    ) -> dict[str, Any] | None:
        output_path = (
            self._projects.require_workspace_root()
            / "PRIVATE"
            / "task-graph"
            / "workers"
            / str(run_id or "").strip()
            / str(node_id or "").strip()
            / "output.json"
        )
        if not output_path.exists():
            return None
        try:
            loaded = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return dict(loaded) if isinstance(loaded, dict) else None

    def _graph_live_project_subgraph_result(
        self,
        *,
        child_graph: dict[str, Any],
        child_run_id: str,
        child_run_ref: dict[str, Any],
    ) -> dict[str, Any]:
        outgoing_nodes = {
            str(item.get("from_node_id") or "").strip()
            for item in list(child_graph.get("edges") or [])
            if isinstance(item, dict) and str(item.get("from_node_id") or "").strip()
        }
        terminal_node_ids = [
            str(item.get("node_id") or "").strip()
            for item in list(child_graph.get("nodes") or [])
            if isinstance(item, dict)
            and str(item.get("node_id") or "").strip()
            and str(item.get("node_id") or "").strip() not in outgoing_nodes
        ]
        terminal_outputs: dict[str, Any] = {}
        for terminal_node_id in terminal_node_ids:
            output_bundle = self._graph_live_load_node_output_bundle(run_id=child_run_id, node_id=terminal_node_id)
            if not output_bundle:
                continue
            terminal_outputs[terminal_node_id] = {
                "typed_output_values": deepcopy(dict(output_bundle.get("typed_output_values") or {})),
                "machine_result": deepcopy(dict(output_bundle.get("machine_result") or {})),
                "status": str(output_bundle.get("status") or "").strip() or "completed",
            }
        return {
            "child_run_id": child_run_id,
            "child_graph_id": str(child_graph.get("graph_id") or "").strip(),
            "child_status": str(child_run_ref.get("status") or "").strip(),
            "child_trace_id": str(child_run_ref.get("trace_id") or f"trace-{child_run_id}").strip() or f"trace-{child_run_id}",
            "terminal_node_ids": terminal_node_ids,
            "terminal_outputs": terminal_outputs,
        }

    def _graph_live_fail_before_dispatch(
        self,
        *,
        graph: dict[str, Any],
        run_id: str,
        node_id: str,
        group_id: str,
        node_states: dict[str, dict[str, Any]],
        event_refs: list[dict[str, Any]],
        reason: str,
        detail: str | None = None,
    ) -> None:
        failed_at = now_iso()
        clean_reason = str(reason or "provider_dispatch_denied").strip()
        clean_detail = str(detail or "").strip()
        label = self._tasks._graph_node_label(graph, node_id)
        summary = f"{label} was blocked before provider dispatch: {clean_reason}."
        if clean_detail:
            summary = f"{summary} {clean_detail}"
        node_states[node_id].update(
            {
                "status": "failed",
                "outcome": "provider_dispatch_denied",
                "updated_at": failed_at,
                "summary": summary,
            }
        )
        event_refs.append(
            {
                "event_id": f"{run_id}-{node_id}-dispatch-denied-{clean_reason}",
                "run_id": run_id,
                "task_id": graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": "node_failed",
                "created_at": failed_at,
                "summary": summary,
                "node_id": node_id,
                "parallel_group_id": group_id,
            }
        )

    @staticmethod
    def _configured_model_lookup(configured_models: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for item in list(configured_models or []):
            if not isinstance(item, dict):
                continue
            clean = dict(item)
            for key in (
                str(clean.get("id") or "").strip(),
                str(clean.get("native_model") or "").strip(),
                (
                    f"{str(clean.get('provider') or '').strip()}/{str(clean.get('native_model') or '').strip()}"
                    if str(clean.get("provider") or "").strip() and str(clean.get("native_model") or "").strip()
                    else ""
                ),
            ):
                if key and key not in lookup:
                    lookup[key] = clean
        return lookup

    def _graph_live_model_capability_snapshots(
        self,
        *,
        node_map: dict[str, dict[str, Any]],
        configured_models: list[dict[str, Any]] | None,
    ) -> dict[str, dict[str, Any]]:
        by_model = self._configured_model_lookup(configured_models)
        snapshots: dict[str, dict[str, Any]] = {}
        for node in node_map.values():
            model_id = str(node.get("model_id") or "").strip()
            if not model_id:
                continue
            record = dict(by_model.get(model_id) or {})
            if not record:
                continue
            snapshots[model_id] = {
                "provider_id": str(record.get("provider") or "").strip() or None,
                "model_id": str(record.get("id") or model_id).strip(),
                "native_model": str(record.get("native_model") or "").strip() or None,
                "snapshot_status": str(record.get("verified_capability_snapshot_status") or "unverified").strip() or "unverified",
                "verification_state": str(record.get("verified_capability_snapshot_verification_state") or "unverified").strip() or "unverified",
                "freshness_status": str(record.get("verified_capability_snapshot_freshness_status") or "").strip() or None,
                "manifest_digest": str(record.get("verified_capability_snapshot_manifest_digest") or "").strip() or None,
                "expires_at": record.get("verified_capability_snapshot_expires_at"),
                "last_verified_at": record.get("verified_capability_snapshot_last_verified_at") or record.get("last_verified_at"),
                "snapshot": deepcopy(dict(record.get("verified_capability_snapshot") or {})),
                "contract": deepcopy(dict(record.get("verified_capability_snapshot_contract") or {})),
            }
        return snapshots

    def _graph_live_require_current_capability_snapshots(
        self,
        *,
        compiled_nodes: dict[str, dict[str, Any]],
        node_map: dict[str, dict[str, Any]],
        configured_models: list[dict[str, Any]] | None,
    ) -> None:
        by_model = self._configured_model_lookup(configured_models)
        for node_id, compiled_node in compiled_nodes.items():
            graph_node = dict(node_map.get(node_id) or {})
            model_id = str(graph_node.get("model_id") or "").strip()
            if not model_id:
                continue
            required_ports = {
                str(item.get("port_type") or "").strip()
                for item in [
                    *list(compiled_node.get("input_ports") or []),
                    *list(compiled_node.get("output_ports") or []),
                ]
                if isinstance(item, dict) and str(item.get("port_type") or "").strip() in {"image", "audio", "video"}
            }
            if not required_ports:
                continue
            model_record = dict(by_model.get(model_id) or {})
            snapshot_status = str(model_record.get("verified_capability_snapshot_status") or "unverified").strip()
            verification_state = str(model_record.get("verified_capability_snapshot_verification_state") or snapshot_status or "unverified").strip().lower()
            snapshot = dict(model_record.get("verified_capability_snapshot") or {})
            graph_capabilities = dict(snapshot.get("graph_capabilities") or {})
            supported_ports = {
                str(item).strip()
                for item in [
                    *list(graph_capabilities.get("input_port_types") or []),
                    *list(graph_capabilities.get("output_port_types") or []),
                ]
                if str(item or "").strip()
            }
            missing_ports = sorted(required_ports.difference(supported_ports))
            if verification_state == "drifted":
                raise ValueError(
                    f"Graph node {node_id} requires a current verified capability snapshot for model {model_id}; "
                    "the stored snapshot is stale after a model or adapter change. Run the provider capability canary again before live admission."
                )
            if verification_state in {"expired", "stale"}:
                raise ValueError(
                    f"Graph node {node_id} requires a fresh verified capability snapshot for model {model_id}; "
                    "the pinned manifest has expired and must be refreshed before live admission."
                )
            if snapshot_status == "stale":
                raise ValueError(
                    f"Graph node {node_id} requires a current verified capability snapshot for model {model_id}; "
                    "the stored snapshot is stale after a model or adapter change. Run the provider capability canary again before live admission."
                )
            if snapshot_status in {"unverified", ""} or not snapshot:
                raise ValueError(
                    f"Graph node {node_id} requires a verified capability snapshot for model {model_id} before live admission. "
                    "Run the provider capability canary first."
                )
            if missing_ports:
                raise ValueError(
                    f"Graph node {node_id} requires verified port capabilities {', '.join(missing_ports)} for model {model_id}, "
                    "but the pinned capability snapshot does not prove them."
                )

    @staticmethod
    def _graph_live_test_hook_enabled(value: Any, *, node_id: str) -> bool:
        if value is True:
            return True
        if isinstance(value, str):
            return node_id in {item.strip() for item in value.split(",") if item.strip()}
        if isinstance(value, (list, tuple, set)):
            return node_id in {str(item).strip() for item in value if str(item).strip()}
        return False

    @staticmethod
    def _graph_live_lease_ttl_seconds(payload: dict[str, Any]) -> int:
        raw_value = payload.get("_scheduler_lease_ttl_seconds")
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = GRAPH_LIVE_LEASE_TTL_SECONDS
        return value if value > 0 else GRAPH_LIVE_LEASE_TTL_SECONDS

    def _start_graph_live_lease_heartbeat(
        self,
        *,
        store: Any,
        lease_id: str,
        owner_boot_id: str,
        ttl_seconds: int,
    ) -> tuple[threading.Event, threading.Thread]:
        stop_event = threading.Event()
        interval = max(1.0, min(float(max(1, ttl_seconds)) / 2.0, float(GRAPH_LIVE_LEASE_HEARTBEAT_SECONDS)))

        def worker() -> None:
            while not stop_event.wait(interval):
                try:
                    store.heartbeat_lease(
                        lease_id,
                        owner_boot_id=owner_boot_id,
                        ttl_seconds=ttl_seconds,
                    )
                except Exception:
                    return

        thread = threading.Thread(
            target=worker,
            name=f"astrabridge-graph-lease-heartbeat-{lease_id}",
            daemon=True,
        )
        thread.start()
        return stop_event, thread

    def _reconcile_durable_graph_scheduler_runs(self) -> None:
        if self._tasks is None:
            return
        try:
            store = self._tasks.durable_run_store()
            now = now_iso()
            for run in store.list_runs(limit=200):
                run_id = str(run.get("run_id") or "").strip()
                status = str(run.get("status") or "").strip()
                if not run_id or status not in {"queued", "running"}:
                    continue
                policy_snapshot = dict(run.get("run_policy_snapshot") or {})
                if str(policy_snapshot.get("scheduler") or "").strip() != "durable_graph_scheduler_v1":
                    continue
                if self._graph_scheduler.get(run_id) is not None:
                    continue
                if status == "running":
                    active_leases = [
                        lease
                        for lease in store.list_leases(run_id=run_id, status="active")
                        if str(lease.get("owner_boot_id") or "").strip() != self._graph_scheduler.owner_id
                        and str(lease.get("expires_at") or "").strip() > now
                    ]
                    if active_leases:
                        continue
                resume_payload = dict(policy_snapshot.get("resume_payload") or {})
                if not str(resume_payload.get("graph_id") or "").strip():
                    continue
                self._graph_scheduler.submit(
                    run_id,
                    resume_payload,
                    max_parallelism=max(1, int(policy_snapshot.get("max_parallelism") or 1)),
                )
        except Exception as exc:
            self._record_event(
                {
                    "type": "durable_graph_scheduler_reconcile_failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                }
            )

    def resolve_capability_route(self, capability_id: str) -> dict[str, Any]:
        configured_models = self._router_config.models() if self._router_config is not None else None
        route_record = None
        if self._router_config is not None:
            route_record = self._router_config.capability_routes().get(str(capability_id or "").strip())
        entry = resolve_capability_route_entry(
            str(capability_id or "").strip(),
            configured_models,
            route_record=route_record,
        )
        if entry.get("resolved_candidate") is None:
            raise RuntimeError(str(entry.get("error") or f"no_capability_candidate: capability `{capability_id}` has no eligible candidate."))
        return entry

    def attach_router(self, router_service: Any) -> None:
        self._router = router_service
        self._initialize_native_turn_loop()

    def attach_project_tools(self, project_tools: Any) -> None:
        self._project_tools = project_tools
        self._initialize_native_turn_loop()

    def _initialize_native_turn_loop(self) -> None:
        if self._router is None or self._project_tools is None:
            return
        if self._native_turn_loop is not None:
            return
        from .coding_kernel import NativeCodingTurnLoop

        self._native_turn_loop = NativeCodingTurnLoop(self, self._router, self._project_tools)

    def environment(self) -> dict[str, Any]:
        execution_host = self._execution_host()
        codex_executable = self._launch_descriptor()
        return {
            "codex_cli": codex_executable,
            "execution_host": execution_host,
            "wsl_distro": self._wsl_distro(),
            "running": self._client.is_running() if self._client else False,
            "runtime_lanes": self._runtime_client_pool.snapshots(),
            "graph_dispatch_control": self._graph_dispatch_control.status(),
            "runtime_config": {
                **self._runtime_config.status(),
                "execution_host": execution_host,
                "wsl_distro": self._wsl_distro(),
            },
        }

    def restart(self) -> dict[str, Any]:
        self._close_client("manual_restart")
        return self.environment()

    def health_environment(self) -> dict[str, Any]:
        execution_host = self._execution_host()
        codex_executable = self._launch_descriptor()
        active_runtime = getattr(self, "_active_runtime", None)
        client = getattr(self, "_client", None)
        if active_runtime is not None:
            runtime_config = {
                "configured": bool(active_runtime.get("configured", True)),
                "codex_home": str(active_runtime.get("codex_home") or self._runtime_config.codex_home),
                "provider_id": active_runtime.get("provider_id"),
                "provider_name": active_runtime.get("provider_name"),
                "base_url": active_runtime.get("base_url"),
                "model": active_runtime.get("model"),
                "reasoning_effort": active_runtime.get("reasoning_effort"),
                "wire_api": active_runtime.get("wire_api"),
                "env_key": active_runtime.get("env_key"),
                "secret_loaded": bool(os.environ.get(str(active_runtime.get("env_key") or ""))),
                "proxy_mode": active_runtime.get("proxy_mode") or "direct",
                "proxy_url": active_runtime.get("proxy_url") or "",
                "execution_host": execution_host,
                "wsl_distro": self._wsl_distro(),
                "secret_source": active_runtime.get("secret_source"),
                "secret_fingerprint": active_runtime.get("secret_fingerprint"),
            }
        else:
            runtime_config = {
                "configured": False,
                "codex_home": str(self._runtime_config.codex_home),
                "provider_id": None,
                "provider_name": None,
                "base_url": None,
                "model": None,
                "reasoning_effort": None,
                "wire_api": None,
                "env_key": None,
                "secret_loaded": False,
                "proxy_mode": "direct",
                "proxy_url": "",
                "execution_host": execution_host,
                "wsl_distro": self._wsl_distro(),
                "secret_source": None,
                "secret_fingerprint": None,
            }
        return {
            "codex_cli": codex_executable,
            "execution_host": execution_host,
            "wsl_distro": self._wsl_distro(),
            "running": client.is_running() if client else False,
            "runtime_config": runtime_config,
        }

    def restart_in_background(self) -> dict[str, Any]:
        """Detach the active app-server client without blocking a UI request."""
        client = self._detach_client()
        if client is None:
            return self.environment()

        def close_detached_client() -> None:
            try:
                client.close()
            finally:
                self._record_event({"type": "runtime_stopped", "reason": "manual_restart"})

        worker = threading.Thread(
            target=close_detached_client,
            name="astrabridge-runtime-restart",
            daemon=True,
        )
        worker.start()
        return self.environment()

    def shutdown(self) -> dict[str, Any]:
        """Close every owned runtime lane during sidecar shutdown."""

        self._graph_scheduler.shutdown(wait=True)
        closed_lanes = self._runtime_client_pool.shutdown()
        with self._lock:
            self._runtime_lane_environments.clear()
            self._client = None
            self._runtime_signature = None
            self._runtime_projection_is_pooled = False
            self._mcp_status_thread_signature = None
            self._mcp_status_thread_id = None
        if closed_lanes:
            self._record_event({"type": "runtime_pool_shutdown", "lane_ids": closed_lanes})
        return self.environment()

    def kernel_probe_snapshot(self, profile: dict[str, Any]) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        execution_host = self._execution_host()
        wsl_distro = self._wsl_distro()
        binary = discover_codex_binary_and_version(
            execution_host=execution_host,
            wsl_distro=wsl_distro,
        )
        protocol_features = observe_protocol_features()
        runtime_roots = self._kernel_probe_runtime_roots(runtime_status)
        app_server_snapshot, client_factory, warnings = self._kernel_probe_app_server_status(runtime_status)
        codex_home = Path(str(runtime_status.get("codex_home") or "")).expanduser().resolve()
        search_roots = self._kernel_probe_search_roots()
        plugin_search_roots, plugin_root_warnings = self._kernel_probe_plugin_search_roots(search_roots)
        mcp_report = probe_mcp_compatibility(
            codex_home=codex_home,
            mcp_config=self._mcp_config.snapshot(),
            client_factory=client_factory,
            request_timeout=10.0,
        )
        plugin_report = probe_plugin_discovery(
            codex_home=codex_home,
            client_factory=client_factory,
            local_search_roots=plugin_search_roots,
            request_timeout=10.0,
        )
        skill_report = probe_skill_discovery(
            codex_home=codex_home,
            client_factory=client_factory,
            local_search_roots=search_roots,
            request_timeout=10.0,
        )
        snapshot = build_codex_kernel_probe_snapshot(
            binary=binary,
            execution_host=execution_host,
            wsl_distro=wsl_distro,
            runtime_status=runtime_status,
            runtime_roots=runtime_roots,
            app_server=app_server_snapshot,
            protocol_features=protocol_features,
            mcp_report=mcp_report,
            plugin_report=plugin_report,
            skill_report=skill_report,
            extra_warnings=[*warnings, *plugin_root_warnings],
            evidence_sources=["apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py"],
        )
        self._record_event(
            {
                "type": "kernel_probe_snapshot_built",
                "profile_id": profile.get("profile_id"),
                "compatibility_status": snapshot.get("inferred", {}).get("compatibility_status"),
                "warnings": len(snapshot.get("known_warnings") or []),
            }
        )
        return snapshot

    def _plugin_skill_registry_snapshot_payload(self, profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        _app_server_snapshot, client_factory, warnings = self._kernel_probe_app_server_status(runtime_status)
        codex_home = Path(str(runtime_status.get("codex_home") or "")).expanduser().resolve()
        search_roots = self._kernel_probe_search_roots()
        plugin_search_roots, plugin_root_warnings = self._kernel_probe_plugin_search_roots(search_roots)
        runtime_roots = self._kernel_probe_runtime_roots(runtime_status)
        plugin_report = probe_plugin_discovery(
            codex_home=codex_home,
            client_factory=client_factory,
            local_search_roots=plugin_search_roots,
            request_timeout=10.0,
        )
        skill_report = probe_skill_discovery(
            codex_home=codex_home,
            client_factory=client_factory,
            local_search_roots=search_roots,
            request_timeout=10.0,
        )
        snapshot = build_plugin_skill_registry_snapshot(
            plugin_report=plugin_report,
            skill_report=skill_report,
            runtime_roots=runtime_roots,
            search_roots=plugin_search_roots,
            extra_notes=[
                *[f"app_server_warning:{text}" for text in warnings if str(text or "").strip()],
                *[f"plugin_probe_root_warning:{text}" for text in plugin_root_warnings if str(text or "").strip()],
            ],
        )
        workspace_root = None
        try:
            workspace_root = self._projects.require_workspace_root().resolve()
        except Exception:  # noqa: BLE001
            workspace_root = None
        snapshot = apply_skill_enablement_snapshot(
            registry_snapshot=snapshot,
            codex_home=codex_home,
            workspace_root=workspace_root,
        )
        return runtime_status, snapshot

    def plugin_skill_registry_snapshot(self, profile: dict[str, Any]) -> dict[str, Any]:
        _runtime_status, snapshot = self._plugin_skill_registry_snapshot_payload(profile)
        self._record_event(
            {
                "type": "plugin_skill_registry_snapshot_built",
                "profile_id": profile.get("profile_id"),
                "plugin_count": len(snapshot.get("plugins") or []),
                "skill_count": len(snapshot.get("skills") or []),
            }
        )
        return snapshot

    def plugin_install_plan(
        self,
        profile: dict[str, Any],
        *,
        plugin_id: str,
        source_catalog_id: str | None = None,
    ) -> dict[str, Any]:
        runtime_status, snapshot = self._plugin_skill_registry_snapshot_payload(profile)
        codex_home = Path(str(runtime_status.get("codex_home") or "")).expanduser().resolve()
        plan = build_plugin_install_plan(
            registry_snapshot=snapshot,
            plugin_id=plugin_id,
            source_catalog_id=source_catalog_id,
            codex_home=codex_home,
        )
        self._record_event(
            {
                "type": "plugin_install_plan_built",
                "profile_id": profile.get("profile_id"),
                "plugin_id": plugin_id,
                "source_catalog_id": source_catalog_id,
                "action": plan.get("action"),
                "status": plan.get("status"),
            }
        )
        return plan

    def plugin_install_apply(
        self,
        profile: dict[str, Any],
        *,
        plugin_id: str,
        source_catalog_id: str | None = None,
    ) -> dict[str, Any]:
        runtime_status, snapshot = self._plugin_skill_registry_snapshot_payload(profile)
        codex_home = Path(str(runtime_status.get("codex_home") or "")).expanduser().resolve()
        workspace_root = self._projects.require_workspace_root().resolve()
        result = execute_plugin_install(
            registry_snapshot=snapshot,
            plugin_id=plugin_id,
            source_catalog_id=source_catalog_id,
            codex_home=codex_home,
            workspace_root=workspace_root,
        )
        if str(result.get("status") or "").strip() in {"applied", "noop"}:
            register_pending_skill_approval_rules(
                codex_home=codex_home,
                plugin_id=str((result.get("plugin") or {}).get("plugin_id") or plugin_id),
                source_catalog_id=str((result.get("plugin") or {}).get("source_catalog_id") or source_catalog_id or "").strip() or None,
                skill_names=list((((result.get("plan") or {}).get("skill_changes") or {}).get("declared_skills") or [])),
            )
        self._record_event(
            {
                "type": "plugin_install_apply_finished",
                "profile_id": profile.get("profile_id"),
                "plugin_id": plugin_id,
                "source_catalog_id": source_catalog_id,
                "action": result.get("action"),
                "status": result.get("status"),
            }
        )
        return result

    def skill_enablement_update(
        self,
        profile: dict[str, Any],
        *,
        record_id: str,
        scope: str,
        enablement_status: str,
    ) -> dict[str, Any]:
        runtime_status, snapshot = self._plugin_skill_registry_snapshot_payload(profile)
        codex_home = Path(str(runtime_status.get("codex_home") or "")).expanduser().resolve()
        workspace_root = None
        try:
            workspace_root = self._projects.require_workspace_root().resolve()
        except Exception:  # noqa: BLE001
            workspace_root = None
        updated_snapshot = update_skill_enablement_snapshot(
            registry_snapshot=snapshot,
            codex_home=codex_home,
            workspace_root=workspace_root,
            record_id=record_id,
            scope=scope,
            enablement_status=enablement_status,
        )
        self._record_event(
            {
                "type": "skill_enablement_updated",
                "profile_id": profile.get("profile_id"),
                "record_id": record_id,
                "scope": scope,
                "enablement_status": enablement_status,
            }
        )
        return updated_snapshot

    def skill_plugin_creator_fixture_scenario(
        self,
        profile: dict[str, Any],
        *,
        skill_name: str = "plugin-creator",
    ) -> dict[str, Any]:
        _runtime_status, snapshot = self._plugin_skill_registry_snapshot_payload(profile)
        skill = next(
            (
                item
                for item in list(snapshot.get("skills") or [])
                if isinstance(item, dict) and str(item.get("skill_name") or "").strip() == skill_name
            ),
            None,
        )
        if not isinstance(skill, dict):
            raise ValueError(f"Skill scenario requires discovered skill `{skill_name}`.")
        source_path = str(((skill.get("provenance") or {}).get("source_path") or "")).strip()
        if not source_path:
            raise ValueError(f"Skill scenario requires a provenance path for `{skill_name}`.")
        skill_path = Path(source_path).expanduser().resolve()
        skill_root = skill_path.parent if skill_path.name.lower() == "skill.md" else skill_path
        result = execute_plugin_creator_skill_scenario(
            workspace_root=self._projects.require_workspace_root().resolve(),
            skill_root=skill_root,
            skill_record_id=str(skill.get("record_id") or "").strip() or None,
            skill_display_name=str(skill.get("display_name") or skill_name).strip() or skill_name,
        )
        self._record_event(
            {
                "type": "skill_plugin_creator_fixture_scenario_finished",
                "profile_id": profile.get("profile_id"),
                "skill_name": skill_name,
                "status": result.get("status"),
                "execution_id": result.get("execution_id"),
            }
        )
        return result

    def restore_startup_runtime(self, profile: dict[str, Any] | None, *, thread_id: str | None = None) -> dict[str, Any]:
        if not profile:
            return {"restored": False, "reason": "no_profile"}
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        result: dict[str, Any] = {
            "restored": True,
            "runtime": runtime_status,
            "client_started": False,
            "thread_id": str(thread_id or "").strip() or None,
            "thread_exists": None,
            "reconciled_thread_id": None,
        }
        try:
            client = self._ensure_client(runtime_status)
            result["client_started"] = client.is_running()
        except Exception as exc:  # noqa: BLE001
            result["client_error"] = str(exc)[:300]
            self._record_event(
                {
                    "type": "startup_runtime_restored",
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "secret_loaded": runtime_status.get("secret_loaded"),
                    "client_started": False,
                    "thread_id": result.get("thread_id"),
                    "thread_exists": None,
                    "error": result["client_error"],
                }
            )
            return result
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id and self._tasks is not None:
            recovery_hint = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
            clean_thread_id = str(recovery_hint.get("thread_id") or "").strip()
            result["thread_id"] = clean_thread_id or None
        if clean_thread_id:
            try:
                exists = self._thread_exists(
                    client,
                    clean_thread_id,
                    timeout=STARTUP_THREAD_PROBE_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                # A stale app-server thread must not keep the sidecar from starting.
                result["thread_exists"] = "unknown"
                result["thread_probe_timeout"] = True
                self._record_event(
                    {
                        "type": "startup_thread_probe_timeout",
                        "profile_id": profile.get("profile_id"),
                        "thread_id": clean_thread_id,
                    }
                )
                return result
            result["thread_exists"] = exists
            if not exists:
                self._mark_provider_thread_missing(clean_thread_id, reason="startup_thread_missing")
                current_project = self._projects.current_project or {}
                reconciled_thread_id = str(current_project.get("current_thread_id") or "").strip()
                if reconciled_thread_id and reconciled_thread_id != clean_thread_id:
                    result["reconciled_thread_id"] = reconciled_thread_id
                else:
                    result["reconciled_thread_id"] = None
                if not result["reconciled_thread_id"]:
                    try:
                        recovered_thread_id = self._recover_startup_provider_thread(
                            client,
                            missing_thread_id=clean_thread_id,
                            profile=profile,
                            runtime_status=runtime_status,
                        )
                    except Exception as exc:  # noqa: BLE001
                        result["recovery_error"] = str(exc)[:300]
                    else:
                        result["recovered_thread_id"] = recovered_thread_id
                        result["reconciled_thread_id"] = recovered_thread_id
        self._record_event(
            {
                "type": "startup_runtime_restored",
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "secret_loaded": runtime_status.get("secret_loaded"),
                "client_started": result.get("client_started"),
                "thread_id": result.get("thread_id"),
                "thread_exists": result.get("thread_exists"),
                "reconciled_thread_id": result.get("reconciled_thread_id"),
            }
        )
        return result

    def _recover_startup_provider_thread(
        self,
        client: AppServerClient,
        *,
        missing_thread_id: str,
        profile: dict[str, Any],
        runtime_status: dict[str, Any],
    ) -> str:
        if self._tasks is None:
            raise RuntimeError("Task continuity is unavailable.")
        if runtime_status.get("secret_loaded") is False:
            raise RuntimeError("Runtime secret is unavailable; startup cannot recover the missing provider thread yet.")
        recovery_hint = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
        permission_mode = str(recovery_hint.get("permission_mode") or "auto")
        collaboration_mode = recovery_hint.get("collaboration_mode")
        model = str(recovery_hint.get("model") or profile.get("model") or "").strip() or None
        effort = str(recovery_hint.get("reasoning_effort") or profile.get("reasoning_effort") or "").strip() or None
        replacement_thread_id, _handoff_event = self._recover_missing_provider_thread(
            client,
            missing_thread_id=missing_thread_id,
            profile=profile,
            model=model,
            effort=effort,
            permission_mode=permission_mode,
            collaboration_mode=collaboration_mode,
            reason="startup_thread_missing",
        )
        return replacement_thread_id

    def load_secret(
        self,
        profile: dict[str, Any],
        session_key: str | None = None,
        key_file_path: str | None = None,
        persist_to_keychain: bool = False,
    ) -> dict[str, Any]:
        profile = dict(profile)
        if persist_to_keychain and session_key and profile.get("provider_id"):
            profile["secret_ref"] = self._secrets.store(str(profile.get("provider_id")), session_key)
            profile["auth_mode"] = "os_keychain"
        runtime_status = self._runtime_config.load_secret(profile, session_key=session_key, key_file_path=key_file_path)
        runtime_status["execution_host"] = self._execution_host()
        runtime_status["wsl_distro"] = self._wsl_distro()
        if profile.get("secret_ref"):
            runtime_status = {**runtime_status, "auth_mode": profile.get("auth_mode"), "secret_ref": profile.get("secret_ref")}
        self._update_project_runtime_defaults(profile, None, None)
        self._refresh_client_if_runtime_changed(runtime_status)
        self._record_event({"type": "runtime_secret_loaded", "runtime": runtime_status})
        return runtime_status

    def list_models(self, profile: dict[str, Any]) -> dict[str, Any]:
        # Model pickers poll this endpoint while users switch routes. Preparing a
        # different profile here rewrites the shared Codex config and restarts an
        # active provider runtime, which can interrupt thread creation or a turn.
        # The desktop already has the effective catalog for picker options, so an
        # alternate runtime is deliberately not started just to enumerate models.
        active_runtime = self._active_runtime_status()
        if active_runtime.get("configured") and self._profile_targets_different_runtime(profile, active_runtime):
            self._record_event(
                {
                    "type": "models_list_deferred_active_runtime",
                    "profile_id": profile.get("profile_id"),
                    "requested_runtime": self._runtime_defer_preview(profile),
                    "active_runtime_signature": list(self._runtime_signature or []),
                    "reason": "model_picker_passive_read",
                }
            )
            return {
                "models": [],
                "next_cursor": None,
                "warning": "model_list_deferred_active_runtime",
                "active_provider_id": active_runtime.get("provider_id"),
            }
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        try:
            client = self._runtime_request_client(runtime_status)
            result = client.request("model/list", {"includeHidden": False, "limit": 200}, timeout=THREAD_LIST_TIMEOUT_SECONDS)
        except RuntimeError as exc:
            if "runtime_switch_deferred_start_turn" not in str(exc):
                raise
            self._record_event(
                {
                    "type": "models_list_deferred_start_turn",
                    "profile_id": profile.get("profile_id"),
                    "runtime": runtime_status,
                }
            )
            return {"models": [], "next_cursor": None, "warning": "runtime_switch_deferred_start_turn"}
        payload = {"models": list(result.get("data") or []), "next_cursor": result.get("nextCursor")}
        self._record_event({"type": "models_listed", "runtime": runtime_status, "count": len(payload["models"])})
        return payload

    def list_threads(self, profile: dict[str, Any], *, archived: bool = False) -> dict[str, Any]:
        if archived:
            return {"threads": [], "next_cursor": None, "backwards_cursor": None}
        active_runtime = self._active_runtime_status()
        if active_runtime.get("configured") and self._profile_targets_different_runtime(profile, active_runtime):
            # Sidebar polling must not replace the active provider just to list a
            # different provider's historical threads. The active runtime can
            # safely answer this read and the task cache remains the UI fallback.
            runtime_status = {
                **active_runtime,
                "execution_host": self._execution_host(),
                "wsl_distro": self._wsl_distro(),
            }
            self._record_event(
                {
                    "type": "threads_list_using_active_runtime",
                    "profile_id": profile.get("profile_id"),
                    "active_provider_id": active_runtime.get("provider_id"),
                    "archived": archived,
                }
            )
        else:
            runtime_status = self._runtime_status_for_profile(profile, require_secret=False)
        if self._runtime_switch_is_pinned(runtime_status):
            cached = self._cached_threads_response(archived=archived, warning="runtime_switch_deferred_active_turn")
            self._record_event(
                {
                    "type": "threads_list_deferred_active_turn",
                    "profile_id": profile.get("profile_id"),
                    "archived": archived,
                    "count": len(cached.get("threads") or []),
                    "runtime": runtime_status,
                }
            )
            return cached
        self._refresh_client_if_runtime_changed(runtime_status)
        cwd = self._runtime_workspace_root()
        try:
            client = self._ensure_client(runtime_status)
            result = client.request("thread/list", {"cwd": cwd, "archived": archived, "limit": 200}, timeout=THREAD_LIST_TIMEOUT_SECONDS)
        except Exception as exc:
            cached = self._cached_threads_response(archived=archived, warning=str(exc))
            self._record_event(
                {
                    "type": "threads_list_fallback",
                    "profile_id": profile.get("profile_id"),
                    "archived": archived,
                    "count": len(cached.get("threads") or []),
                    "error": str(exc),
                }
            )
            return cached
        threads = [self._decorate_thread(thread) for thread in list(result.get("data") or [])]
        if not threads:
            cached = self._cached_threads_response(archived=archived)
            if cached.get("threads"):
                self._record_event(
                    {
                        "type": "threads_list_cache_overlay",
                        "profile_id": profile.get("profile_id"),
                        "archived": archived,
                        "count": len(cached.get("threads") or []),
                    }
                )
                return cached
        self._projects.cache_threads(threads)
        native_threads = self._native_cached_threads()
        seen_ids = {str(thread.get("id") or "") for thread in threads}
        for native_thread in native_threads:
            native_id = str(native_thread.get("id") or "")
            if native_id and native_id not in seen_ids:
                threads.append(native_thread)
        self._record_event({"type": "threads_listed", "count": len(threads), "archived": archived})
        return {
            "threads": threads,
            "next_cursor": result.get("nextCursor"),
            "backwards_cursor": result.get("backwardsCursor"),
        }

    def read_thread(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        native_thread = self._read_native_thread(thread_id)
        if native_thread is not None:
            decorated = self._decorate_thread(native_thread)
            decorated = self._decorate_dynamic_tool_evidence(decorated)
            decorated = self._decorate_turn_coding_events(decorated)
            decorated = self._decorate_turn_completion_quality(decorated)
            decorated = self._decorate_turn_execution_policy(decorated)
            self._record_task_thread_snapshot(decorated)
            return {"thread": decorated}
        active_runtime = self._active_runtime_status()
        # A configured profile is not necessarily an active process. This is
        # common after a runtime restart and in handoff recovery, where the
        # previous client has already been detached. Only defer a cross-
        # provider read while a live client actually owns the runtime lane.
        active_client_running = bool(self._client is not None and self._client.is_running())
        if active_runtime.get("configured") and active_client_running and self._profile_targets_different_runtime(profile, active_runtime):
            cached = self._cached_thread(thread_id, warning="thread_read_deferred_active_runtime")
            if cached:
                self._record_task_thread_snapshot(cached)
                self._record_event(
                    {
                        "type": "thread_read_deferred_active_runtime",
                        "thread_id": thread_id,
                        "profile_id": profile.get("profile_id"),
                        "active_provider_id": active_runtime.get("provider_id"),
                    }
                )
                return {"thread": cached}
            raise RuntimeError("thread_read_deferred_active_runtime")
        runtime_status = self._runtime_status_for_profile(profile, require_secret=False)
        if self._runtime_switch_is_pinned(runtime_status):
            cached = self._cached_thread(thread_id, warning="runtime_switch_deferred_active_turn")
            if cached:
                self._record_task_thread_snapshot(cached)
                self._record_event(
                    {
                        "type": "thread_read_deferred_active_turn",
                        "thread_id": thread_id,
                        "profile_id": profile.get("profile_id"),
                        "runtime": runtime_status,
                    }
                )
                return {"thread": cached}
        self._refresh_client_if_runtime_changed(runtime_status)
        try:
            client = self._ensure_client(runtime_status)
            result = client.request("thread/read", {"threadId": thread_id, "includeTurns": True}, timeout=THREAD_READ_TIMEOUT_SECONDS)
        except Exception as exc:
            cached = self._cached_thread(thread_id, warning=str(exc))
            if cached:
                self._record_task_thread_snapshot(cached)
                self._record_event(
                    {
                        "type": "thread_read_fallback",
                        "thread_id": thread_id,
                        "profile_id": profile.get("profile_id"),
                        "error": str(exc),
                    }
                )
                return {"thread": cached}
            raise
        thread = self._decorate_thread(dict(result.get("thread") or {}))
        thread = self._overlay_dynamic_tool_events(thread)
        thread = self._decorate_dynamic_tool_evidence(thread)
        thread = self._decorate_turn_coding_events(thread)
        thread = self._decorate_turn_completion_quality(thread)
        thread = self._decorate_turn_execution_policy(thread)
        normalized_status = self._normalize_thread_status(thread)
        if isinstance(normalized_status, dict):
            if normalized_status != thread.get("status"):
                thread = {**thread, "status": normalized_status}
            normalized_status = self._overlay_cached_thread_status(thread["id"], normalized_status)
            if normalized_status != thread.get("status"):
                thread = {**thread, "status": normalized_status}
        self._maybe_clear_runtime_pin_from_thread(thread, reason="thread_read_terminal_turn")
        cache_patch: dict[str, Any] = {"name": thread.get("name")}
        if isinstance(thread.get("status"), dict):
            cache_patch["status"] = thread.get("status")
        self._cache_thread_entry(thread["id"], cache_patch)
        self._record_task_thread_snapshot(thread)
        return {"thread": thread}

    def _maybe_clear_runtime_pin_from_thread(self, thread: dict[str, Any], *, reason: str) -> bool:
        thread_id = str(thread.get("id") or "")
        if not thread_id:
            return False
        turns = [item for item in list(thread.get("turns") or []) if isinstance(item, dict)]
        if not turns:
            return False
        pinned_thread_id = str(self._runtime_pin_thread_id or "")
        pinned_turn_id = str(self._runtime_pin_turn_id or "")
        if pinned_thread_id and thread_id != pinned_thread_id:
            return False
        target_turn = None
        if pinned_turn_id:
            target_turn = next((turn for turn in turns if str(turn.get("id") or "") == pinned_turn_id), None)
        if target_turn is None:
            target_turn = turns[-1]
        status = str(target_turn.get("status") or "").lower()
        if status not in TERMINAL_TURN_STATUSES:
            return False
        return self._clear_runtime_pin(
            thread_id=thread_id,
            turn_id=str(target_turn.get("id") or ""),
            reason=f"{reason}:{status}",
        )

    def _record_task_thread_snapshot(self, thread: dict[str, Any]) -> None:
        if self._tasks is not None:
            try:
                coding_events: list[dict[str, Any]] = []
                for turn in list(thread.get("turns") or []):
                    if not isinstance(turn, dict):
                        continue
                    for event in list(turn.get("coding_events") or []):
                        if isinstance(event, dict):
                            coding_events.append(event)
                if coding_events:
                    self._tasks.record_coding_events(coding_events)
            except Exception as exc:  # noqa: BLE001
                self._record_event(
                    {
                        "type": "task_coding_event_projection_failed",
                        "thread_id": str(thread.get("id") or thread.get("thread_id") or ""),
                        "error": str(exc)[:300],
                    }
                )
        if self._task_conversation is None:
            return
        try:
            self._task_conversation.record_thread_snapshot(thread)
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                {
                    "type": "task_thread_snapshot_failed",
                    "thread_id": str(thread.get("id") or thread.get("thread_id") or ""),
                    "error": str(exc)[:300],
                }
            )

    def _schedule_terminal_thread_snapshot(
        self,
        *,
        thread_id: str,
        turn_id: str,
        method: str,
        keep_visible: bool,
    ) -> None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return
        key = f"{clean_thread_id}:{str(turn_id or method).strip() or method}"
        with self._lock:
            if key in self._terminal_snapshot_keys:
                return
            self._terminal_snapshot_keys.add(key)
        worker = threading.Thread(
            target=self._terminal_thread_snapshot_worker,
            kwargs={
                "key": key,
                "thread_id": clean_thread_id,
                "turn_id": str(turn_id or "").strip(),
                "method": method,
                "keep_visible": keep_visible,
            },
            daemon=True,
        )
        worker.start()

    def _terminal_thread_snapshot_worker(
        self,
        *,
        key: str,
        thread_id: str,
        turn_id: str,
        method: str,
        keep_visible: bool,
    ) -> None:
        try:
            time.sleep(0.25)
            with self._lock:
                client = self._client
            if client is None or not client.is_running():
                self._record_event(
                    {
                        "type": "terminal_thread_snapshot_skipped",
                        "thread_id": thread_id,
                        "turn_id": turn_id,
                        "method": method,
                        "reason": "runtime_client_unavailable",
                    }
                )
                return
            result = client.request(
                "thread/read",
                {"threadId": thread_id, "includeTurns": True},
                timeout=min(THREAD_READ_TIMEOUT_SECONDS, 20.0),
            )
            thread = self._decorate_thread(dict(result.get("thread") or {}))
            thread = self._overlay_dynamic_tool_events(thread)
            thread = self._decorate_dynamic_tool_evidence(thread)
            thread = self._decorate_turn_coding_events(thread)
            thread = self._decorate_turn_completion_quality(thread)
            thread = self._decorate_turn_execution_policy(thread)
            normalized_status = self._normalize_thread_status(thread)
            if isinstance(normalized_status, dict):
                if normalized_status != thread.get("status"):
                    thread = {**thread, "status": normalized_status}
                normalized_status = self._overlay_cached_thread_status(thread["id"], normalized_status)
                if normalized_status != thread.get("status"):
                    thread = {**thread, "status": normalized_status}
            self._cache_thread_entry(thread["id"], {"name": thread.get("name"), "status": thread.get("status")})
            self._record_task_thread_snapshot(thread)
            if keep_visible:
                self._projects.switch_thread(thread_id)
                if self._tasks is not None:
                    self._tasks.force_visible_provider_thread(thread_id)
            self._record_event(
                {
                    "type": "terminal_thread_snapshot_synced",
                    "thread_id": thread_id,
                    "turn_id": turn_id,
                    "method": method,
                    "keep_visible": keep_visible,
                    "turn_count": len(list(thread.get("turns") or [])),
                }
            )
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                {
                    "type": "terminal_thread_snapshot_failed",
                    "thread_id": thread_id,
                    "turn_id": turn_id,
                    "method": method,
                    "error": str(exc)[:300],
                }
            )
        finally:
            with self._lock:
                self._terminal_snapshot_keys.discard(key)

    def create_thread(
        self,
        profile: dict[str, Any],
        *,
        model: str | None,
        effort: str | None,
        permission_mode: str,
        task_id: str | None = None,
        name: str | None = None,
        operation_id: str | None = None,
        confirm_route_degradation: bool = False,
        _operation_started: bool = False,
    ) -> dict[str, Any]:
        profile, route_admission = self._admit_runtime_route(
            profile,
            thread_id=None,
            model=model,
            effort=effort,
            permission_mode=permission_mode,
            execution_policy="standard",
            context_mode="default",
            attachments=[],
            confirm_degradation=confirm_route_degradation,
        )
        route_admission = self._admission_for_operation(route_admission, operation="thread_create")
        self._assert_runtime_route_admitted(route_admission, operation="thread_create")
        effective_model = str(profile.get("model") or model or "").strip() or None
        effective_effort = str(dict(route_admission.get("effective") or {}).get("reasoning_effort") or effort or "").strip() or None
        effective_permission_mode = str(dict(route_admission.get("effective") or {}).get("permission_mode") or permission_mode or "ask").strip()
        effective_policy = str(dict(route_admission.get("effective") or {}).get("execution_policy") or "standard").strip()
        if not _operation_started:
            normalized_operation_id = self._normalize_thread_create_operation_id(operation_id)
            operation, should_start = self._begin_thread_create_operation(
                normalized_operation_id,
                profile=profile,
                model=effective_model,
                effort=effective_effort,
                permission_mode=effective_permission_mode,
                name=name,
            )
            if not should_start:
                return self.recover_thread_create(profile, operation_id=normalized_operation_id)
            try:
                with self._runtime_operation_lock:
                    self._runtime_thread_start_in_progress = True
                    self._runtime_operation_local.in_thread_start = True
                    try:
                        response = self.create_thread(
                            profile,
                            model=effective_model,
                            effort=effective_effort,
                            permission_mode=effective_permission_mode,
                            task_id=task_id,
                            name=name,
                            operation_id=normalized_operation_id,
                            confirm_route_degradation=confirm_route_degradation,
                            _operation_started=True,
                        )
                    finally:
                        self._runtime_operation_local.in_thread_start = False
                        self._runtime_thread_start_in_progress = False
            except Exception as exc:
                self._finish_thread_create_operation(normalized_operation_id, status="failed", error=str(exc))
                raise
            self._finish_thread_create_operation(
                normalized_operation_id,
                status="completed",
                thread_id=str(dict(response.get("thread") or {}).get("id") or ""),
            )
            return response
        if not getattr(self._runtime_operation_local, "in_thread_start", False):
            with self._runtime_operation_lock:
                self._runtime_thread_start_in_progress = True
                self._runtime_operation_local.in_thread_start = True
                try:
                    return self.create_thread(
                        profile,
                        model=effective_model,
                        effort=effective_effort,
                        permission_mode=effective_permission_mode,
                        task_id=task_id,
                        name=name,
                        operation_id=operation_id,
                        confirm_route_degradation=confirm_route_degradation,
                        _operation_started=True,
                    )
                finally:
                    self._runtime_operation_local.in_thread_start = False
                    self._runtime_thread_start_in_progress = False
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        client = self._runtime_request_client(runtime_status)
        params = self._thread_start_params(
            profile=profile,
            model=effective_model,
            permission_mode=effective_permission_mode,
            include_dynamic_tools=effective_policy != NO_TOOLS_EXECUTION_POLICY,
        )
        try:
            result = client.request("thread/start", params, timeout=THREAD_START_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            self._record_event({"type": "thread_create_timeout", "profile_id": profile.get("profile_id"), "runtime": runtime_status})
            raise RuntimeError(
                "Send is blocked at thread setup: Codex app-server did not create a thread in time. "
                "Check Codex login/runtime health and the selected model/provider settings."
            ) from exc
        thread = dict(result.get("thread") or {})
        thread_id = str(thread.get("id") or "")
        if not thread_id:
            raise RuntimeError("thread/start did not return a thread id.")
        if name and name.strip():
            client.request("thread/name/set", {"threadId": thread_id, "name": name.strip()})
            thread["name"] = name.strip()
        self._projects.switch_thread(thread_id)
        self._cache_thread_entry(
            thread_id,
            {
                "name": thread.get("name"),
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": effective_model or profile.get("model"),
                "reasoning_effort": effective_effort or profile.get("reasoning_effort"),
                "permission_mode": effective_permission_mode,
                "execution_route_status": route_admission.get("status"),
                "execution_route_driver": dict(route_admission.get("effective") or {}).get("execution_driver"),
            },
        )
        if self._tasks is not None:
            task_settings = self._task_thread_settings(
                profile,
                effective_model,
                effective_effort,
                effective_permission_mode,
                name=thread.get("name"),
            )
            if str(task_id or "").strip():
                self._tasks.bind_thread_to_task_id(
                    task_id=str(task_id),
                    thread_id=thread_id,
                    settings=task_settings,
                    role="provider",
                    make_active=True,
                )
            else:
                self._tasks.create_task(name or thread.get("name") or "New task", thread_id=thread_id, settings=task_settings)
        self._update_project_runtime_defaults(profile, effective_model, effective_effort, route_admission=route_admission)
        self._record_event(
            {
                "type": "thread_created",
                "thread_id": thread_id,
                "runtime": runtime_status,
                "route_admission": deepcopy(route_admission),
            }
        )
        try:
            return {**self.read_thread(profile, thread_id), "route_admission": route_admission}
        except Exception as exc:
            self._record_event({"type": "thread_read_after_create_fallback", "thread_id": thread_id, "error": str(exc)})
            return {
                "thread": self._decorate_thread({**thread, "id": thread_id, "turns": list(thread.get("turns") or [])}),
                "route_admission": route_admission,
            }

    def recover_thread_create(self, profile: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        normalized_operation_id = self._normalize_thread_create_operation_id(operation_id)
        with self._thread_create_operation_lock:
            self._prune_thread_create_operations_locked()
            operation = dict(self._thread_create_operations.get(normalized_operation_id) or {})
        if not operation:
            raise ValueError("Unknown thread-create recovery operation.")
        status = str(operation.get("status") or "pending")
        payload: dict[str, Any] = {
            "operation_id": normalized_operation_id,
            "status": status,
            "retry_after_ms": 1500 if status == "pending" else None,
        }
        if status == "failed":
            payload["error"] = str(operation.get("error") or "Thread creation did not complete.")
            return payload
        if status != "completed":
            return payload
        thread_id = str(operation.get("thread_id") or "")
        if not thread_id:
            payload.update({"status": "failed", "error": "Thread creation completed without a thread id."})
            return payload
        cached = self._cached_thread(thread_id)
        if cached:
            payload["thread"] = cached
            return payload
        try:
            payload.update(self.read_thread(profile, thread_id))
        except Exception as exc:  # noqa: BLE001
            payload.update(
                {
                    "thread": self._decorate_thread({"id": thread_id, "name": operation.get("name"), "turns": []}),
                    "warning": f"thread_create_recovery_read_fallback:{str(exc)[:200]}",
                }
            )
        return payload

    def begin_thread_create(
        self,
        profile: dict[str, Any],
        *,
        model: str | None,
        effort: str | None,
        permission_mode: str,
        name: str | None = None,
        operation_id: str | None = None,
        confirm_route_degradation: bool = False,
    ) -> dict[str, Any]:
        """Start a user-requested thread without holding the HTTP response open.

        The worker owns the existing serialized runtime start path. Callers only
        receive the operation state and must reconcile a completed thread through
        ``recover_thread_create``; this prevents a timeout from starting a second
        provider thread.
        """
        profile, route_admission = self._admit_runtime_route(
            profile,
            thread_id=None,
            model=model,
            effort=effort,
            permission_mode=permission_mode,
            execution_policy="standard",
            context_mode="default",
            attachments=[],
            confirm_degradation=confirm_route_degradation,
        )
        route_admission = self._admission_for_operation(route_admission, operation="thread_create_receipt")
        self._assert_runtime_route_admitted(route_admission, operation="thread_create_receipt")
        effective_model = str(profile.get("model") or model or "").strip() or None
        effective_effort = str(dict(route_admission.get("effective") or {}).get("reasoning_effort") or effort or "").strip() or None
        effective_permission_mode = str(dict(route_admission.get("effective") or {}).get("permission_mode") or permission_mode or "ask").strip()
        normalized_operation_id = self._normalize_thread_create_operation_id(operation_id)
        operation, should_start = self._begin_thread_create_operation(
            normalized_operation_id,
            profile=profile,
            model=effective_model,
            effort=effective_effort,
            permission_mode=effective_permission_mode,
            name=name,
        )
        if should_start:
            worker = threading.Timer(
                0.01,
                self._complete_thread_create_operation,
                kwargs={
                    "profile": dict(profile),
                    "model": effective_model,
                    "effort": effective_effort,
                    "permission_mode": effective_permission_mode,
                    "name": name,
                    "operation_id": normalized_operation_id,
                    "confirm_route_degradation": confirm_route_degradation,
                },
            )
            worker.name = f"astrabridge-thread-create-{normalized_operation_id[-12:]}"
            worker.daemon = True
            worker.start()
            # Return the receipt before the worker can contend for runtime or
            # task state. The UI must always have this operation id available
            # for bounded, idempotent recovery queries.
            return {
                "operation_id": normalized_operation_id,
                "status": "pending",
                "retry_after_ms": 1500,
                "route_admission": route_admission,
            }
        return {**self.recover_thread_create(profile, operation_id=normalized_operation_id), "route_admission": route_admission}

    def _complete_thread_create_operation(
        self,
        *,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        name: str | None,
        operation_id: str,
        confirm_route_degradation: bool = False,
    ) -> None:
        self._record_event(
            {
                "type": "thread_create_operation_started",
                "operation_id": operation_id,
                "profile_id": str(profile.get("profile_id") or ""),
            }
        )
        acquired_runtime_lock = False
        try:
            acquired_runtime_lock = self._runtime_operation_lock.acquire(
                timeout=THREAD_CREATE_RUNTIME_LOCK_TIMEOUT_SECONDS
            )
            if not acquired_runtime_lock:
                raise RuntimeError(
                    "Task creation could not acquire the runtime lane in time. "
                    "Wait for the active operation to finish, then retry creating the task."
                )
            self._runtime_thread_start_in_progress = True
            self._runtime_operation_local.in_thread_start = True
            try:
                response = self.create_thread(
                    profile,
                    model=model,
                    effort=effort,
                    permission_mode=permission_mode,
                    name=name,
                    operation_id=operation_id,
                    confirm_route_degradation=confirm_route_degradation,
                    _operation_started=True,
                )
            finally:
                self._runtime_operation_local.in_thread_start = False
                self._runtime_thread_start_in_progress = False
        except Exception as exc:  # noqa: BLE001
            self._finish_thread_create_operation(operation_id, status="failed", error=str(exc))
            return
        finally:
            if acquired_runtime_lock:
                self._runtime_operation_lock.release()
        self._finish_thread_create_operation(
            operation_id,
            status="completed",
            thread_id=str(dict(response.get("thread") or {}).get("id") or ""),
        )

    def _normalize_thread_create_operation_id(self, operation_id: str | None) -> str:
        candidate = str(operation_id or "").strip() or new_id()
        if not THREAD_CREATE_OPERATION_ID_RE.fullmatch(candidate):
            raise ValueError("Invalid thread-create operation id.")
        return candidate

    def _begin_thread_create_operation(
        self,
        operation_id: str,
        *,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        name: str | None,
    ) -> tuple[dict[str, Any], bool]:
        with self._thread_create_operation_lock:
            self._prune_thread_create_operations_locked()
            existing = self._thread_create_operations.get(operation_id)
            if existing is not None:
                return dict(existing), False
            operation = {
                "operation_id": operation_id,
                "status": "pending",
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "started_monotonic": time.monotonic(),
                "profile_id": str(profile.get("profile_id") or ""),
                "model": str(model or profile.get("model") or ""),
                "effort": str(effort or profile.get("reasoning_effort") or ""),
                "permission_mode": str(permission_mode or "auto"),
                "name": str(name or "")[:160],
            }
            self._thread_create_operations[operation_id] = operation
            return dict(operation), True

    def _finish_thread_create_operation(
        self,
        operation_id: str,
        *,
        status: str,
        thread_id: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._thread_create_operation_lock:
            operation = self._thread_create_operations.get(operation_id)
            if operation is None:
                return
            operation["status"] = status
            operation["updated_at"] = now_iso()
            if thread_id:
                operation["thread_id"] = thread_id
            if error:
                operation["error"] = str(redact_sensitive(error))[:500]
        self._record_event(
            {
                "type": f"thread_create_operation_{status}",
                "operation_id": operation_id,
                "thread_id": thread_id or None,
                "error": str(redact_sensitive(error))[:500] if error else None,
            }
        )

    def _prune_thread_create_operations_locked(self) -> None:
        cutoff = time.monotonic() - THREAD_CREATE_OPERATION_TTL_SECONDS
        stale_ids = [
            operation_id
            for operation_id, operation in self._thread_create_operations.items()
            if float(operation.get("started_monotonic") or 0) < cutoff
        ]
        for operation_id in stale_ids:
            self._thread_create_operations.pop(operation_id, None)
        while len(self._thread_create_operations) > THREAD_CREATE_OPERATION_LIMIT:
            oldest = min(
                self._thread_create_operations,
                key=lambda operation_id: float(self._thread_create_operations[operation_id].get("started_monotonic") or 0),
            )
            self._thread_create_operations.pop(oldest, None)

    def fork_thread(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        model: str | None,
        effort: str | None,
        permission_mode: str,
        name: str | None = None,
        confirm_route_degradation: bool = False,
    ) -> dict[str, Any]:
        if not getattr(self._runtime_operation_local, "in_thread_start", False):
            with self._runtime_operation_lock:
                self._runtime_thread_start_in_progress = True
                self._runtime_operation_local.in_thread_start = True
                try:
                    return self.fork_thread(
                        profile,
                        thread_id=thread_id,
                        model=model,
                        effort=effort,
                        permission_mode=permission_mode,
                        name=name,
                        confirm_route_degradation=confirm_route_degradation,
                    )
                finally:
                    self._runtime_operation_local.in_thread_start = False
                    self._runtime_thread_start_in_progress = False
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        profile, route_admission = self._admit_runtime_route(
            profile,
            thread_id=thread_id,
            model=model,
            effort=effort,
            permission_mode=permission_mode,
            execution_policy="standard",
            context_mode="default",
            attachments=[],
            confirm_degradation=confirm_route_degradation,
        )
        route_admission = self._admission_for_operation(route_admission, operation="thread_fork")
        self._assert_runtime_route_admitted(route_admission, operation="thread_fork", thread_id=thread_id)
        effective_model = str(profile.get("model") or model or "").strip() or None
        effective_effort = str(dict(route_admission.get("effective") or {}).get("reasoning_effort") or effort or "").strip() or None
        effective_permission_mode = str(dict(route_admission.get("effective") or {}).get("permission_mode") or permission_mode or "ask").strip()
        effective_policy = str(dict(route_admission.get("effective") or {}).get("execution_policy") or "standard").strip()
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        client = self._ensure_client(runtime_status)
        params = {
            "threadId": thread_id,
            **self._thread_start_params(
                profile=profile,
                model=effective_model,
                permission_mode=effective_permission_mode,
                include_dynamic_tools=effective_policy != NO_TOOLS_EXECUTION_POLICY,
            ),
        }
        try:
            result = client.request("thread/fork", params, timeout=THREAD_FORK_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            self._record_event({"type": "thread_fork_timeout", "thread_id": thread_id, "profile_id": profile.get("profile_id")})
            raise RuntimeError(
                "Fork is blocked at thread setup: Codex app-server did not fork the thread in time. "
                "Check runtime health and the active provider/model settings."
            ) from exc
        thread = dict(result.get("thread") or {})
        fork_id = str(thread.get("id") or "")
        if not fork_id:
            raise RuntimeError("thread/fork did not return a thread id.")
        if name and name.strip():
            client.request("thread/name/set", {"threadId": fork_id, "name": name.strip()})
            thread["name"] = name.strip()
        self._projects.switch_thread(fork_id)
        self._cache_thread_entry(
            fork_id,
            {
                "name": thread.get("name"),
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": effective_model or profile.get("model"),
                "reasoning_effort": effective_effort or profile.get("reasoning_effort"),
                "permission_mode": effective_permission_mode,
                "execution_route_status": route_admission.get("status"),
                "execution_route_driver": dict(route_admission.get("effective") or {}).get("execution_driver"),
            },
        )
        if self._tasks is not None:
            self._tasks.bind_thread(
                thread_id=fork_id,
                settings=self._task_thread_settings(
                    profile,
                    effective_model,
                    effective_effort,
                    effective_permission_mode,
                    name=thread.get("name"),
                ),
                role="fork",
                make_active=True,
            )
        self._update_project_runtime_defaults(profile, effective_model, effective_effort, route_admission=route_admission)
        self._record_event(
            {
                "type": "thread_forked",
                "thread_id": fork_id,
                "from_thread_id": thread_id,
                "route_admission": deepcopy(route_admission),
            }
        )
        try:
            return {**self.read_thread(profile, fork_id), "route_admission": route_admission}
        except Exception as exc:
            self._record_event({"type": "thread_read_after_fork_fallback", "thread_id": fork_id, "error": str(exc)})
            return {
                "thread": self._decorate_thread({**thread, "id": fork_id, "turns": list(thread.get("turns") or [])}),
                "route_admission": route_admission,
            }

    def rename_thread(self, profile: dict[str, Any], thread_id: str, name: str) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        if not name.strip():
            raise ValueError("name is required.")
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        client.request("thread/name/set", {"threadId": thread_id, "name": name.strip()})
        self._cache_thread_entry(thread_id, {"name": name.strip()})
        self._record_event({"type": "thread_renamed", "thread_id": thread_id, "name": name.strip()})
        return {"thread_id": thread_id, "name": name.strip()}

    def start_graph_worker(
        self,
        profile: dict[str, Any],
        *,
        graph_id: str,
        run_id: str,
        node_id: str,
        parent_thread_id: str,
        model: str | None = None,
        effort: str | None = None,
        permission_mode: str = "auto",
        artifact_refs: list[dict[str, Any]] | None = None,
        mcp_tool_policy_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._tasks is None:
            raise ValueError("Task service is required for graph worker execution.")
        clean_graph_id = str(graph_id or "").strip()
        clean_run_id = str(run_id or "").strip()
        clean_node_id = str(node_id or "").strip()
        clean_parent_thread_id = str(parent_thread_id or "").strip()
        if not clean_graph_id or not clean_run_id or not clean_node_id:
            raise ValueError("graph_id, run_id, and node_id are required.")

        graph = self._tasks.graph_definition(clean_graph_id)
        if not graph:
            raise ValueError("Unknown graph_id for graph worker execution.")
        node = next(
            (
                dict(item)
                for item in list(graph.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() == clean_node_id
            ),
            None,
        )
        if not node:
            raise ValueError(f"Unknown graph worker node_id: {clean_node_id}")
        graph_policy = dict(graph.get("graph_policy") or {})
        execution_policy = dict(node.get("execution_policy") or {})
        subagent_policy = dict(execution_policy.get("subagent_policy") or node.get("subagent_policy") or {})
        tools = dict(node.get("tools") or {})
        output_contract = dict(node.get("output_contract") or {})
        spawn_mode = str(execution_policy.get("spawn_mode") or "isolated_lane").strip() or "isolated_lane"
        worker_origin = "codex_subagent" if spawn_mode == "subagent_worker" else "provider_lane"
        agent_role = str(node.get("kind") or "").strip() or "worker"
        agent_nickname = str(node.get("label") or "").strip() or clean_node_id
        effective_model = model or str(node.get("model_id") or "").strip() or profile.get("model")
        effective_effort = effort or str(node.get("reasoning_effort") or "").strip() or profile.get("reasoning_effort")
        requested_permission_mode = str(permission_mode or node.get("permission_mode") or "auto").strip().lower() or "auto"
        requested_collaboration_mode = str(node.get("collaboration_mode") or "").strip() or None
        effective_collaboration_mode = self._normalize_graph_worker_collaboration_mode(
            node,
            collaboration_mode=requested_collaboration_mode,
        )
        effective_execution_backend = str(node.get("execution_backend") or "").strip() or None
        timeout_ms = self._graph_worker_timeout_ms(execution_policy.get("timeout_ms"))
        normalized_subagent_policy = self._normalize_graph_worker_subagent_policy(
            subagent_policy,
            node_id=clean_node_id,
            spawn_mode=spawn_mode,
        )
        tool_policy = self._graph_worker_tool_policy(
            tools,
            node=node,
            graph_policy=graph_policy,
            node_id=clean_node_id,
            mcp_tool_policy_snapshot=mcp_tool_policy_snapshot,
        )
        turn_execution_policy = self._graph_worker_turn_execution_policy(tool_policy)
        allowed_mcp_tool_names, allow_browser_smoke = self._graph_worker_dynamic_tool_filter(tool_policy)
        effective_permission_mode = "ask" if turn_execution_policy == NO_TOOLS_EXECUTION_POLICY else requested_permission_mode
        profile, route_admission = self._admit_runtime_route(
            profile,
            thread_id=clean_parent_thread_id or None,
            model=effective_model,
            effort=effective_effort,
            permission_mode=effective_permission_mode,
            execution_policy=turn_execution_policy,
            context_mode="default",
            attachments=[],
            confirm_degradation=False,
        )
        route_admission = self._admission_for_operation(route_admission, operation="graph_worker_start")
        self._assert_runtime_route_admitted(route_admission, operation="graph_worker_start", thread_id=clean_parent_thread_id or None)
        effective_model = str(profile.get("model") or effective_model or "").strip() or None
        effective_admission = dict(route_admission.get("effective") or {})
        effective_effort = str(effective_admission.get("reasoning_effort") or effective_effort or "").strip() or None
        effective_permission_mode = str(effective_admission.get("permission_mode") or effective_permission_mode or "ask").strip()
        turn_execution_policy = self._normalize_turn_execution_policy(
            str(effective_admission.get("execution_policy") or turn_execution_policy)
        )
        effective_execution_backend = str(effective_admission.get("execution_backend") or effective_execution_backend or "app_server").strip()
        runtime_contract = self._graph_worker_runtime_contract(
            profile=profile,
            node=node,
            model=effective_model,
            effort=effective_effort,
            permission_mode=effective_permission_mode,
            collaboration_mode=effective_collaboration_mode,
            execution_backend=effective_execution_backend,
            timeout_ms=timeout_ms,
            spawn_mode=spawn_mode,
            subagent_policy=normalized_subagent_policy,
            tool_policy=tool_policy,
        )
        runtime_contract["route_admission"] = deepcopy(route_admission)
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        client = self._ensure_client(runtime_status)

        params = self._thread_start_params(
            profile=profile,
            model=effective_model,
            permission_mode=effective_permission_mode,
            include_dynamic_tools=turn_execution_policy != NO_TOOLS_EXECUTION_POLICY,
            allowed_mcp_tool_names=allowed_mcp_tool_names,
            allow_browser_smoke=allow_browser_smoke,
        )
        if spawn_mode == "subagent_worker" and clean_parent_thread_id:
            params["source"] = {
                "subagent": {
                    "thread_spawn": {
                        "parent_thread_id": clean_parent_thread_id,
                        "depth": 1,
                        "agent_path": None,
                        "agent_nickname": agent_nickname,
                        "agent_role": agent_role,
                        "max_turns": int(normalized_subagent_policy.get("max_turns") or 1),
                        "isolation_mode": str(normalized_subagent_policy.get("isolation_mode") or "lane"),
                        "allow_direct_teammate_messages": bool(normalized_subagent_policy.get("allow_direct_teammate_messages")),
                        "share_worktree": bool(normalized_subagent_policy.get("share_worktree")),
                        "allow_nested_subagents": bool(normalized_subagent_policy.get("allow_nested_subagents")),
                    }
                }
            }
        result = client.request("thread/start", params, timeout=THREAD_START_TIMEOUT_SECONDS)
        thread = dict(result.get("thread") or {})
        worker_thread_id = str(thread.get("id") or "")
        if not worker_thread_id:
            raise RuntimeError("thread/start did not return a worker thread id.")
        if agent_nickname:
            try:
                client.request("thread/name/set", {"threadId": worker_thread_id, "name": agent_nickname})
            except Exception:
                pass
        settings = self._task_thread_settings(
            profile,
            effective_model,
            effective_effort,
            effective_permission_mode,
            collaboration_mode=effective_collaboration_mode,
            execution_backend=effective_execution_backend,
            name=agent_nickname,
        )
        self._cache_thread_entry(worker_thread_id, settings)
        lineage = self._tasks.record_graph_worker(
            {
                "graph_id": clean_graph_id,
                "run_id": clean_run_id,
                "node_id": clean_node_id,
                "worker_thread_id": worker_thread_id,
                "parent_thread_id": clean_parent_thread_id,
                "spawn_mode": spawn_mode,
                "worker_origin": worker_origin,
                "agent_role": agent_role,
                "agent_nickname": agent_nickname,
                "status": "ready",
                "execution_backend": settings.get("execution_backend"),
                "artifact_refs": list(artifact_refs or []),
                "runtime_contract": runtime_contract,
            },
            graph_definition=graph,
        )
        self._record_event(
            {
                "type": "graph_worker_started",
                "graph_id": clean_graph_id,
                "run_id": clean_run_id,
                "node_id": clean_node_id,
                "worker_thread_id": worker_thread_id,
                "parent_thread_id": clean_parent_thread_id,
                "spawn_mode": spawn_mode,
                "worker_origin": worker_origin,
                "agent_role": agent_role,
                "agent_nickname": agent_nickname,
                "output_contract_artifact_only": bool(output_contract.get("artifact_only")),
                "runtime": runtime_status,
                "runtime_contract": runtime_contract,
                "turn_execution_policy": turn_execution_policy,
            }
        )
        if requested_collaboration_mode and requested_collaboration_mode != effective_collaboration_mode:
            self._record_event(
                {
                    "type": "graph_worker_collaboration_mode_normalized",
                    "graph_id": clean_graph_id,
                    "run_id": clean_run_id,
                    "node_id": clean_node_id,
                    "worker_thread_id": worker_thread_id,
                    "requested_collaboration_mode": requested_collaboration_mode,
                    "effective_collaboration_mode": effective_collaboration_mode or "default",
                    "reason": "bounded_graph_workers_must_finish_in_one_structured_turn",
                }
            )
        return {
            "worker": {
                "thread_id": worker_thread_id,
                "parent_thread_id": clean_parent_thread_id,
                "graph_id": clean_graph_id,
                "run_id": clean_run_id,
                "node_id": clean_node_id,
                "spawn_mode": spawn_mode,
                "worker_origin": worker_origin,
                "agent_role": agent_role,
                "agent_nickname": agent_nickname,
                "settings": settings,
            },
            "lineage": lineage,
        }

    def _validate_graph_live_run_submission(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate/compile a live run without creating a provider client.

        Admission is deliberately separate from execution.  This keeps the
        HTTP receipt path bounded while ensuring the background worker cannot
        discover a graph, budget, policy, or provider-profile error after it
        has already started a live attempt.
        """

        if self._tasks is None:
            raise ValueError("Task service is required for live task-graph execution.")
        if not isinstance(payload, dict):
            raise TypeError("Task-graph live run payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        raw_graph = self._tasks.graph_definition(graph_id)
        if not raw_graph:
            raise ValueError("Unknown graph_id for live task-graph execution.")
        graph = validate_graph_definition(raw_graph)
        task = self._tasks.current_task() or {}
        run_budget = dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else {}
        run_token_limit = self._graph_live_run_token_limit(run_budget)
        if run_token_limit is None:
            raise ValueError(
                "Live task-graph execution requires a positive budget.limits.total_tokens value."
            )
        profiles_snapshot = self._profiles.list_profiles() if self._profiles is not None else None
        configured_models = self._router_config.models() if self._router_config is not None else None
        dry_run_result = self._tasks.dry_run_graph(
            {"graph_id": graph_id, "budget": run_budget, "validation_mode": "live"},
            profiles_snapshot=profiles_snapshot,
            configured_models=configured_models,
        )
        dry_run = dict(dry_run_result.get("dry_run") or {})
        if str(dry_run.get("overall_status") or "").strip() != "pass":
            graph_reasons = [
                str(item).strip()
                for item in list(dict(dry_run.get("graph_result") or {}).get("reasons") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Task graph live run is blocked until dry-run passes. "
                + (graph_reasons[0] if graph_reasons else "Resolve the dry-run findings first.")
            )

        orchestration_graph = self._tasks._orchestration_graph_for_task_graph(graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._tasks._known_model_capabilities_for_graph(
                orchestration_graph,
                configured_models=configured_models,
            ),
        )
        compiled_nodes = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(compiled_plan.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        dispatch_limits = self._graph_run_dispatch.resolve_dispatch_limits(
            payload=payload,
            compiled_plan=compiled_plan,
        )
        guardrail_decision = evaluate_runtime_guardrails(
            graph=orchestration_graph,
            compiled_plan=compiled_plan,
            run_budget=run_budget,
            dispatch_limits=dispatch_limits,
            parent_context=self._graph_live_parent_context(payload),
            mode="live_run",
            require_complete_budget=bool(
                payload.get("_require_complete_runtime_budget")
                or payload.get("skill_ref")
                or payload.get("resolution_ref")
                or payload.get("skill_id")
            ),
        )
        if str(guardrail_decision.get("status") or "").strip() != "pass":
            guardrail_blockers = [
                str(item).strip()
                for item in list(guardrail_decision.get("blockers") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Runtime guardrails blocked live task-graph admission. "
                + (guardrail_blockers[0] if guardrail_blockers else "Resolve the bounded runtime policy first.")
            )
        communication_isolation = validate_typed_communication_isolation(
            orchestration_graph,
            compiled_plan,
        )
        if str(communication_isolation.get("status") or "").strip() != "pass":
            communication_blockers = [
                str(item).strip()
                for item in list(communication_isolation.get("blockers") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Typed communication isolation blocked live task-graph admission. "
                + (communication_blockers[0] if communication_blockers else "Resolve the graph handoff isolation policy first.")
            )
        run_token_limit = int(
            dict(guardrail_decision.get("normalized_budget") or {}).get("max_total_tokens")
            or run_token_limit
        )
        executor_report = journaled_compiled_plan_executor_capability_report(
            compiled_plan,
            execution_mode="live_run",
            workspace_root=self._projects.require_workspace_root(),
            activation_scope=f"runtime_live_run:{str(graph.get('graph_id') or '') or str(task_id or 'task')}",
        )
        if not bool(executor_report.get("ok")):
            blockers = [
                str(item).strip()
                for item in list(executor_report.get("blockers") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Task graph live run is blocked until executor compatibility passes. "
                + (blockers[0] if blockers else "Resolve the executor availability findings first.")
            )
        executor_contracts_by_node = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(executor_report.get("entries") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        self._graph_live_require_current_capability_snapshots(
            compiled_nodes=compiled_nodes,
            node_map=node_map,
            configured_models=configured_models,
        )
        model_capability_snapshots = self._graph_live_model_capability_snapshots(
            node_map=node_map,
            configured_models=configured_models,
        )
        parent_thread_id = str(
            payload.get("parent_thread_id")
            or self._tasks.visible_provider_thread_id(include_missing_fallback=True)
            or ""
        ).strip()
        if any(
            str(dict(compiled_nodes.get(node_id) or {}).get("spawn_mode") or "").strip() == "subagent_worker"
            for node_id in compiled_nodes
        ) and not parent_thread_id:
            raise ValueError(
                "Live task-graph execution requires an active provider thread before starting subagent worker nodes."
            )
        prepared_nodes = self._prepare_graph_live_run_nodes(
            task=task,
            graph=graph,
            compiled_nodes=compiled_nodes,
            node_map=node_map,
            run_token_limit=run_token_limit,
        )
        return {
            "graph": graph,
            "task": task,
            "graph_id": graph_id,
            "run_budget": run_budget,
            "run_token_limit": run_token_limit,
            "compiled_plan": compiled_plan,
            "compiled_nodes": compiled_nodes,
            "node_map": node_map,
            "prepared_nodes": prepared_nodes,
            "parent_thread_id": parent_thread_id,
            "model_capability_snapshots": model_capability_snapshots,
            "runtime_guardrails": guardrail_decision,
            "communication_isolation": communication_isolation,
            "dispatch_limits": dict(guardrail_decision.get("effective_dispatch_limits") or dispatch_limits),
        }

    def queue_task_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._graph_run_dispatch.queue_task_graph_run(payload)

    def _run_graph_scheduler_job(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        worker_payload = dict(payload)
        worker_payload["_scheduler_run_id"] = str(run_id or "").strip()
        try:
            return self.execute_task_graph_run(worker_payload)
        except _GraphDurablePause:
            raise
        except Exception as exc:  # noqa: BLE001
            self._mark_graph_scheduler_failure(str(run_id or "").strip(), exc)
            raise

    def _mark_graph_scheduler_failure(self, run_id: str, exc: Exception) -> None:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id or self._tasks is None:
            return
        if isinstance(exc, _GraphDurablePause):
            return
        error_text = str(redact_sensitive(str(exc) or type(exc).__name__))[:500]
        try:
            store = self._tasks.durable_run_store()
            current = store.load_run(clean_run_id)
            if current is not None and str(current.get("status") or "") not in {
                "completed",
                "failed",
                "cancelled",
                "partial",
            }:
                updated_at = now_iso()
                store.compare_and_swap_run(
                    clean_run_id,
                    int(current.get("state_version") or 0),
                    status="failed",
                    patch={
                        "failure": {
                            "failure_kind": "scheduler_dispatch",
                            "error": error_text,
                        },
                        "updated_at": updated_at,
                    },
                    event={
                        "event_id": f"{clean_run_id}-scheduler-failed",
                        "run_id": clean_run_id,
                        "task_id": str(current.get("task_id") or ""),
                        "trace_id": str(current.get("trace_id") or f"trace-{clean_run_id}"),
                        "event_type": "run_failed",
                        "created_at": updated_at,
                        "summary": "Durable graph scheduler could not dispatch the run.",
                        "failure_kind": "scheduler_dispatch",
                    },
                )
        except Exception:
            pass
        try:
            compact_ref = self._tasks.graph_run_ref(clean_run_id)
            if compact_ref:
                compact_ref = {
                    **dict(compact_ref),
                    "status": "failed",
                    "latest_event_type": "run_failed",
                    "latest_event_at": now_iso(),
                }
                self._tasks.persist_graph_run_ref(compact_ref)
        except Exception:
            pass

    def graph_scheduler_status(self) -> dict[str, Any]:
        return self._graph_run_dispatch.graph_scheduler_status()

    def graph_run_status(self, run_id: str) -> dict[str, Any]:
        return self._graph_run_dispatch.graph_run_status(run_id)

    def cancel_task_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._graph_run_dispatch.cancel_task_graph_run(payload)

    def recover_task_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._tasks is None:
            raise ValueError("Task service is required for task-graph recovery.")
        if not isinstance(payload, dict):
            raise TypeError("Task-graph recovery payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        strategy = str(payload.get("strategy") or "").strip().lower()
        if not run_id:
            raise ValueError("run_id is required.")
        if not strategy:
            raise ValueError("strategy is required.")
        store = self._tasks.durable_run_store()
        durable_run = store.load_run(run_id, include_events=True)
        if durable_run is None:
            raise ValueError("Task graph run not found.")
        latest_run_ref = self._tasks.graph_run_ref(run_id) or durable_run
        full_source_run = self._tasks._load_full_graph_run(latest_run_ref) or durable_run
        run_policy = dict(full_source_run.get("run_policy_snapshot") or durable_run.get("run_policy_snapshot") or {})
        if str(run_policy.get("mode") or "").strip() != "live_run":
            return self._tasks.recover_graph_run(payload)

        self._reconcile_durable_graph_scheduler_runs()
        current_status = str(full_source_run.get("status") or durable_run.get("status") or "").strip()
        graph_id = str(full_source_run.get("graph_id") or durable_run.get("graph_id") or "").strip()
        graph = self._tasks.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found for live task-graph recovery.")
        validated_graph = validate_graph_definition(graph)
        orchestration_graph = (
            validated_graph
            if validated_graph.get("schema_registry") is not None
            else self._tasks._orchestration_graph_for_task_graph(validated_graph)
        )
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._tasks._known_model_capabilities_for_graph(orchestration_graph),
        )
        compiled_nodes = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(compiled_plan.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        downstream_by_node: dict[str, list[str]] = {}
        for edge in list(compiled_plan.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            from_node_id = str(edge.get("from_node_id") or "").strip()
            to_node_id = str(edge.get("to_node_id") or "").strip()
            if from_node_id and to_node_id:
                downstream_by_node.setdefault(from_node_id, []).append(to_node_id)

        prior_node_states = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(full_source_run.get("node_run_states") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        if not prior_node_states:
            raise ValueError("Source live run does not expose node_run_states for recovery.")

        selected_node_ids = [str(item).strip() for item in list(payload.get("selected_node_ids") or []) if str(item or "").strip()]
        for node_id in selected_node_ids:
            if node_id not in compiled_nodes:
                raise ValueError(f"Unknown selected_node_id for live recovery: {node_id}")

        approval_state = dict(full_source_run.get("approval_state") or {})
        pending_approval = str(approval_state.get("status") or "").strip() == "pending"
        can_resume_in_place = (
            strategy == "resume_run"
            and current_status in {"queued", "running"}
            and not pending_approval
            and not self._graph_live_cancellation_requested(durable_run)
        )
        if can_resume_in_place:
            existing_budget = dict(dict(run_policy.get("budget") or {}).get("run") or {})
            limits = deepcopy(dict(existing_budget.get("limits") or {}))
            resumed = self.execute_task_graph_run(
                {
                    "graph_id": graph_id,
                    "_scheduler_run_id": run_id,
                    "_resume_run_manifest": {
                        "node_run_states": [
                            deepcopy(dict(item))
                            for item in list(full_source_run.get("node_run_states") or [])
                            if isinstance(item, dict)
                        ],
                        "worker_bindings": [
                            deepcopy(dict(item))
                            for item in list(full_source_run.get("worker_bindings") or [])
                            if isinstance(item, dict)
                        ],
                        "artifact_refs": [
                            deepcopy(dict(item))
                            for item in list(full_source_run.get("artifact_refs") or [])
                            if isinstance(item, dict)
                        ],
                        "event_refs": [
                            deepcopy(dict(item))
                            for item in list(full_source_run.get("event_refs") or [])
                            if isinstance(item, dict)
                        ],
                        "status": current_status,
                        "approval_state": deepcopy(approval_state),
                        "updated_at": str(full_source_run.get("updated_at") or durable_run.get("updated_at") or now_iso()).strip()
                        or now_iso(),
                    },
                    **({"budget": {"limits": limits}} if limits else {}),
                }
            )
            return {
                "recovery": {
                    "run_id": run_id,
                    "strategy": strategy,
                    "safe_to_resume": True,
                    "status": "resumed_in_place",
                    "reason": None,
                    "source_run_id": run_id,
                    "rerun_node_ids": [],
                    "reused_node_ids": [],
                },
                **resumed,
            }

        if strategy not in {"resume_run", "retry_failed_nodes", "rerun_selected_nodes", "partial_execution"}:
            raise ValueError("strategy must be resume_run, retry_failed_nodes, rerun_selected_nodes, or partial_execution.")

        initial_targets: list[str]
        if strategy == "resume_run":
            initial_targets = [
                node_id
                for node_id, state in prior_node_states.items()
                if str(state.get("status") or "").strip()
                in {"queued", "ready", "running", "waiting_on_dependencies", "waiting_on_artifact", "waiting_on_approval", "cancelled"}
            ]
            if not initial_targets:
                raise ValueError("No resumable node state exists on the source live run.")
        elif strategy == "retry_failed_nodes":
            initial_targets = [
                node_id
                for node_id, state in prior_node_states.items()
                if str(state.get("status") or "").strip() in {"failed", "blocked", "needs_review"}
                or str(state.get("outcome") or "").strip() in {"failed", "blocked", "needs_review", "executor_failed", "schema_violation"}
            ]
            if not initial_targets:
                raise ValueError("No failed, blocked, or needs_review node exists on the source live run.")
        else:
            if not selected_node_ids:
                raise ValueError("selected_node_ids are required for rerun_selected_nodes and partial_execution.")
            initial_targets = selected_node_ids

        rerun_node_ids = self._tasks._graph_recovery_closure(initial_targets=initial_targets, downstream_by_node=downstream_by_node)  # noqa: SLF001
        rerun_node_ids.update(
            node_id
            for node_id, state in prior_node_states.items()
            if str(state.get("status") or "").strip()
            in {"queued", "ready", "running", "waiting_on_dependencies", "waiting_on_artifact", "waiting_on_approval", "cancelled"}
        )
        ordered_rerun_node_ids = [node_id for node_id in compiled_nodes if node_id in rerun_node_ids]
        reusable_node_ids = [
            node_id
            for node_id in compiled_nodes
            if node_id not in rerun_node_ids
            and str(dict(prior_node_states.get(node_id) or {}).get("status") or "").strip() in {"completed", "partial"}
        ]

        auto_replay_safe_executor_ids = {"artifact_source", "mcp_resource", "transform", "router", "router_condition"}
        unsafe_rerun_nodes = [
            node_id
            for node_id in ordered_rerun_node_ids
            if str(dict(compiled_nodes.get(node_id) or {}).get("compiler_executor_id") or "").strip() not in auto_replay_safe_executor_ids
        ]
        if unsafe_rerun_nodes:
            status_payload = self.graph_run_status(run_id)
            return {
                "recovery": {
                    "run_id": run_id,
                    "source_run_id": run_id,
                    "strategy": strategy,
                    "safe_to_resume": False,
                    "status": "needs_review",
                    "reason": (
                        "Automatic live replay is blocked because the requested recovery path includes "
                        f"non-idempotent or ambiguous nodes: {', '.join(unsafe_rerun_nodes)}."
                    ),
                    "initial_target_node_ids": initial_targets,
                    "rerun_node_ids": ordered_rerun_node_ids,
                    "reused_node_ids": reusable_node_ids,
                },
                "live_run": status_payload["live_run"],
                "run": status_payload["run"],
                "events": status_payload["events"],
                "graph": status_payload["graph"],
                "task": status_payload["task"],
                "scheduler": status_payload["scheduler"],
            }

        previous_bindings = [
            dict(item)
            for item in list(full_source_run.get("worker_bindings") or [])
            if isinstance(item, dict)
        ]
        preloaded_node_states: dict[str, dict[str, Any]] = {}
        preloaded_worker_bindings: list[dict[str, Any]] = []
        for node_id in reusable_node_ids:
            prior_state = dict(prior_node_states.get(node_id) or {})
            if not prior_state:
                continue
            prior_state["reused_existing_output"] = True
            prior_state["reused_from_run_id"] = run_id
            preloaded_node_states[node_id] = prior_state
            binding = next(
                (
                    dict(item)
                    for item in previous_bindings
                    if str(item.get("node_id") or "").strip() == node_id
                ),
                None,
            )
            if binding:
                binding["reused_existing_output"] = True
                binding["reused_from_run_id"] = run_id
                preloaded_worker_bindings.append(binding)

        created_at = now_iso()
        recovery_id = new_id("graph-live-recovery")
        workspace_root = self._projects.require_workspace_root()
        artifact_root = Path(workspace_root) / "PRIVATE" / "task-graph" / "recovery" / recovery_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        manifest_path = artifact_root / "manifest.json"
        report_md_path = artifact_root / "report.md"
        recovery_manifest = {
            "schema_version": "astrabridge-task-graph-live-recovery-v1",
            "recovery_id": recovery_id,
            "source_run_id": run_id,
            "graph_id": graph_id,
            "task_id": str(durable_run.get("task_id") or ""),
            "strategy": strategy,
            "requested_at": created_at,
            "selected_node_ids": selected_node_ids,
            "initial_target_node_ids": initial_targets,
            "rerun_node_ids": ordered_rerun_node_ids,
            "reused_node_ids": reusable_node_ids,
            "effective_node_behaviors": {},
            "source_run_status": current_status,
            "artifact_paths": {
                "manifest_json": manifest_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(manifest_path, recovery_manifest)
        report_md_path.write_text(self._tasks._graph_recovery_report_markdown(recovery_manifest), encoding="utf-8")  # noqa: SLF001

        run_budget = dict(dict(run_policy.get("budget") or {}).get("run") or {})
        limits = deepcopy(dict(run_budget.get("limits") or {}))
        recovered = self.execute_task_graph_run(
            {
                "graph_id": graph_id,
                **({"budget": {"limits": limits}} if limits else {}),
                "_recovery_context": {
                    "recovery_id": recovery_id,
                    "source_run_id": run_id,
                    "strategy": strategy,
                    "selected_node_ids": selected_node_ids,
                    "initial_target_node_ids": initial_targets,
                    "rerun_node_ids": ordered_rerun_node_ids,
                    "reused_node_ids": reusable_node_ids,
                    "preloaded_node_states": preloaded_node_states,
                    "preloaded_worker_bindings": preloaded_worker_bindings,
                    "recovery_manifest": recovery_manifest,
                },
            }
        )
        return {
            "recovery": recovery_manifest,
            **recovered,
        }

    def execute_task_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Synchronous compatibility adapter; normal HTTP callers use the scheduler."""
        if self._tasks is None:
            raise ValueError("Task service is required for live task-graph execution.")
        if not isinstance(payload, dict):
            raise TypeError("Task-graph live run payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        raw_graph = self._tasks.graph_definition(graph_id)
        if not raw_graph:
            raise ValueError("Unknown graph_id for live task-graph execution.")
        graph = validate_graph_definition(raw_graph)
        task = self._tasks.current_task() or {}
        run_budget = dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else {}
        run_token_limit = self._graph_live_run_token_limit(run_budget)
        if run_token_limit is None:
            raise ValueError(
                "Live task-graph execution requires a positive budget.limits.total_tokens value."
            )
        profiles_snapshot = self._profiles.list_profiles() if self._profiles is not None else None
        configured_models = self._router_config.models() if self._router_config is not None else None
        dry_run_result = self._tasks.dry_run_graph(
            {"graph_id": graph_id, "budget": run_budget, "validation_mode": "live"},
            profiles_snapshot=profiles_snapshot,
            configured_models=configured_models,
        )
        dry_run = dict(dry_run_result.get("dry_run") or {})
        if str(dry_run.get("overall_status") or "").strip() != "pass":
            graph_reasons = [
                str(item).strip()
                for item in list(dict(dry_run.get("graph_result") or {}).get("reasons") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Task graph live run is blocked until dry-run passes. "
                + (graph_reasons[0] if graph_reasons else "Resolve the dry-run findings first.")
            )

        orchestration_graph = self._tasks._orchestration_graph_for_task_graph(graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._tasks._known_model_capabilities_for_graph(
                orchestration_graph,
                configured_models=configured_models,
            ),
        )
        compiled_nodes = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(compiled_plan.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        dispatch_limits = self._graph_run_dispatch.resolve_dispatch_limits(
            payload=payload,
            compiled_plan=compiled_plan,
        )
        guardrail_decision = evaluate_runtime_guardrails(
            graph=orchestration_graph,
            compiled_plan=compiled_plan,
            run_budget=run_budget,
            dispatch_limits=dispatch_limits,
            parent_context=self._graph_live_parent_context(payload),
            mode="live_run",
            require_complete_budget=bool(
                payload.get("_require_complete_runtime_budget")
                or payload.get("skill_ref")
                or payload.get("resolution_ref")
                or payload.get("skill_id")
            ),
        )
        if str(guardrail_decision.get("status") or "").strip() != "pass":
            guardrail_blockers = [
                str(item).strip()
                for item in list(guardrail_decision.get("blockers") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Runtime guardrails blocked live task-graph execution. "
                + (guardrail_blockers[0] if guardrail_blockers else "Resolve the bounded runtime policy first.")
            )
        communication_isolation = validate_typed_communication_isolation(
            orchestration_graph,
            compiled_plan,
        )
        if str(communication_isolation.get("status") or "").strip() != "pass":
            communication_blockers = [
                str(item).strip()
                for item in list(communication_isolation.get("blockers") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Typed communication isolation blocked live task-graph execution. "
                + (communication_blockers[0] if communication_blockers else "Resolve the graph handoff isolation policy first.")
            )
        run_token_limit = int(
            dict(guardrail_decision.get("normalized_budget") or {}).get("max_total_tokens")
            or run_token_limit
        )
        payload = {
            **payload,
            "_dispatch_limits": deepcopy(dict(guardrail_decision.get("effective_dispatch_limits") or dispatch_limits)),
            "_runtime_guardrails": deepcopy(guardrail_decision),
            "_communication_isolation": deepcopy(communication_isolation),
        }
        executor_report = journaled_compiled_plan_executor_capability_report(
            compiled_plan,
            execution_mode="live_run",
            workspace_root=self._projects.require_workspace_root(),
            activation_scope=f"runtime_live_resume:{str(graph.get('graph_id') or '') or str(task_id or 'task')}",
        )
        if not bool(executor_report.get("ok")):
            blockers = [
                str(item).strip()
                for item in list(executor_report.get("blockers") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Task graph live run is blocked until executor compatibility passes. "
                + (blockers[0] if blockers else "Resolve the executor availability findings first.")
            )
        executor_contracts_by_node = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(executor_report.get("entries") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        self._graph_live_require_current_capability_snapshots(
            compiled_nodes=compiled_nodes,
            node_map=node_map,
            configured_models=configured_models,
        )
        model_capability_snapshots = self._graph_live_model_capability_snapshots(
            node_map=node_map,
            configured_models=configured_models,
        )
        parent_thread_id = str(
            payload.get("parent_thread_id")
            or self._tasks.visible_provider_thread_id(include_missing_fallback=True)
            or ""
        ).strip()
        if any(
            str(dict(compiled_nodes.get(node_id) or {}).get("spawn_mode") or "").strip() == "subagent_worker"
            for node_id in compiled_nodes
        ) and not parent_thread_id:
            raise ValueError(
                "Live task-graph execution requires an active provider thread before starting subagent worker nodes."
            )
        prepared_nodes = self._prepare_graph_live_run_nodes(
            task=task,
            graph=graph,
            compiled_nodes=compiled_nodes,
            node_map=node_map,
            run_token_limit=run_token_limit,
        )
        recovery_context = dict(payload.get("_recovery_context") or {})

        scheduler_run_id = str(payload.get("_scheduler_run_id") or "").strip()
        if not re.fullmatch(r"graph-run-live-[A-Za-z0-9_-]{8,128}", scheduler_run_id):
            scheduler_run_id = ""
        resume_run_manifest = dict(payload.get("_resume_run_manifest") or {})
        run_id = scheduler_run_id or new_id("graph-run-live")
        created_at = now_iso()
        durable_store = self._tasks.durable_run_store()
        existing_durable_run = None
        if scheduler_run_id:
            stored_durable_run = durable_store.load_run(run_id, include_events=True)
            latest_run_ref = self._tasks.graph_run_ref(run_id) or stored_durable_run
            existing_durable_run = (
                self._tasks._load_full_graph_run(latest_run_ref)
                if latest_run_ref is not None
                else None
            ) or stored_durable_run
        if isinstance(existing_durable_run, dict):
            if scheduler_run_id and resume_run_manifest:
                existing_durable_run = {
                    **dict(existing_durable_run),
                    **resume_run_manifest,
                }
            created_at = str(existing_durable_run.get("created_at") or created_at).strip() or created_at
            if str(existing_durable_run.get("status") or "").strip() in {"completed", "failed", "cancelled", "needs_review"}:
                compact = dict(
                    self._tasks.persist_graph_run_ref(
                        self._tasks._compact_graph_run_ref(existing_durable_run)
                    ).get("run_ref")
                    or self._tasks._compact_graph_run_ref(existing_durable_run)
                )
                return {
                    "schema_version": "astrabridge-task-graph-live-run-v1",
                    "live_run": {
                        "run_id": run_id,
                        "run_status": str(existing_durable_run.get("status") or ""),
                        "run_ref": compact,
                        "artifact_paths": {},
                    },
                    "graph": graph,
                    "task": self._tasks.task_view(self._tasks.current_task(), compact_graph_runs=True),
                }
        workspace_root = Path(self._projects.require_workspace_root())
        artifact_root = workspace_root / "PRIVATE" / "task-graph" / "live-run" / run_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        compiled_plan_path = artifact_root / "compiled-plan.json"
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        run_manifest_path = artifact_root / "run-manifest.json"
        write_json(compiled_plan_path, compiled_plan)

        budget_snapshot = self._tasks._graph_run_budget_snapshot(
            graph=graph,
            compiled_plan=compiled_plan,
            run_budget=run_budget,
        )
        node_mcp_tool_policies = self._graph_node_mcp_tool_policy_snapshots(
            graph=graph,
            compiled_plan=compiled_plan,
        )
        dispatch_limits = self._graph_run_dispatch.resolve_dispatch_limits(payload=payload, compiled_plan=compiled_plan)
        runtime_guardrails = deepcopy(dict(payload.get("_runtime_guardrails") or guardrail_decision))
        communication_isolation = deepcopy(
            dict(payload.get("_communication_isolation") or communication_isolation)
        )
        parallel_groups, _normalized_parallelism = self._graph_run_dispatch.normalize_parallel_groups(
            compiled_plan,
            dispatch_limits=dispatch_limits,
        )
        node_states: dict[str, dict[str, Any]] = {}
        event_refs: list[dict[str, Any]] = [
            {
                "event_id": f"{run_id}-created",
                "run_id": run_id,
                "task_id": graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": "run_created",
                "created_at": created_at,
                "summary": f"{graph['title']} live task-graph run created.",
                **(
                    {
                        "payload": {
                            "parent_run_context": deepcopy(self._graph_live_parent_context(payload)),
                        }
                    }
                    if self._graph_live_parent_context(payload)
                    else {}
                ),
            }
        ]
        for node_id, compiled_node in compiled_nodes.items():
            dependency_node_ids = [
                str(item).strip()
                for item in list(compiled_node.get("dependency_node_ids") or [])
                if str(item or "").strip()
            ]
            node_states[node_id] = {
                "node_id": node_id,
                "run_id": run_id,
                "status": "waiting_on_dependencies" if dependency_node_ids else "queued",
                "outcome": "pending",
                "attempt_count": 0,
                "started_at": created_at,
                "updated_at": created_at,
                "worker_origin": None,
            }
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-queued",
                    "run_id": run_id,
                    "task_id": graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_queued",
                    "created_at": created_at,
                    "summary": f"{self._tasks._graph_node_label(graph, node_id)} queued for live execution.",
                    "node_id": node_id,
                }
            )

        run_artifact_refs = [
            {
                "artifact_id": f"{run_id}-compiled-plan-json",
                "artifact_kind": "graph_definition",
                "task_id": graph["task_id"],
                "run_id": run_id,
                "source_node_id": str((compiled_plan.get("entry_node_ids") or [next(iter(compiled_nodes), "")])[0] or ""),
                "path": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-run-manifest-json",
                "artifact_kind": "structured_json",
                "task_id": graph["task_id"],
                "run_id": run_id,
                "source_node_id": str((compiled_plan.get("entry_node_ids") or [next(iter(compiled_nodes), "")])[0] or ""),
                "path": run_manifest_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
        ]
        run_manifest = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": graph["graph_id"],
            "task_id": graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "running",
            "entry_node_ids": list(compiled_plan.get("entry_node_ids") or []),
            "node_run_states": [deepcopy(item) for item in node_states.values()],
            "artifact_refs": deepcopy(run_artifact_refs),
            "event_refs": deepcopy(event_refs),
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "live_run",
                "scheduler": "provider_graph_live_v1",
                "template_id": graph.get("template_id"),
                "parallel_group_count": int(dict(compiled_plan.get("topology") or {}).get("parallel_group_count") or len(parallel_groups)),
                "max_parallelism": int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or 1),
                "parallel_group_ids": [
                    str(group.get("group_id") or "").strip()
                    for group in parallel_groups
                    if str(group.get("group_id") or "").strip()
                ],
                "model_capability_snapshots": model_capability_snapshots,
                "dispatch_control": deepcopy(dispatch_limits),
                "budget": budget_snapshot,
                "runtime_guardrails": runtime_guardrails,
                "communication_isolation": communication_isolation,
                "executor_contract": {
                    "execution_mode": "live_run",
                    "registry_fingerprint": str(executor_report.get("current_registry_fingerprint") or ""),
                    "compiled_plan_registry_fingerprint": executor_report.get("compiled_plan_registry_fingerprint"),
                    "blocker_count": int(executor_report.get("blocker_count") or 0),
                },
                "node_mcp_tool_policies": node_mcp_tool_policies,
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        if isinstance(existing_durable_run, dict):
            persisted_states = {
                str(item.get("node_id") or "").strip(): dict(item)
                for item in list(existing_durable_run.get("node_run_states") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip()
            }
            if persisted_states:
                node_states = persisted_states
            persisted_events = [
                dict(item)
                for item in list(existing_durable_run.get("event_refs") or [])
                if isinstance(item, dict)
            ]
            if persisted_events:
                event_refs = persisted_events
            persisted_artifacts = [
                dict(item)
                for item in list(existing_durable_run.get("artifact_refs") or [])
                if isinstance(item, dict)
            ]
            if persisted_artifacts:
                default_source_node_id = str(
                    (compiled_plan.get("entry_node_ids") or [next(iter(compiled_nodes), "")])[0] or ""
                )
                normalized_artifacts: list[dict[str, Any]] = []
                for item in persisted_artifacts:
                    normalized = dict(item)
                    path_text = str(normalized.get("path") or "").strip()
                    if not str(normalized.get("artifact_id") or "").strip() or not path_text:
                        continue
                    normalized["artifact_kind"] = str(normalized.get("artifact_kind") or "run_summary").strip() or "run_summary"
                    normalized["task_id"] = str(normalized.get("task_id") or graph["task_id"]).strip() or graph["task_id"]
                    normalized["run_id"] = str(normalized.get("run_id") or run_id).strip() or run_id
                    normalized["source_node_id"] = str(normalized.get("source_node_id") or default_source_node_id).strip() or default_source_node_id
                    normalized["media_type"] = str(normalized.get("media_type") or ("application/json" if path_text.endswith(".json") else "text/plain")).strip() or "application/octet-stream"
                    normalized["status"] = str(normalized.get("status") or "ready").strip() or "ready"
                    normalized["created_at"] = str(normalized.get("created_at") or created_at).strip() or created_at
                    normalized_artifacts.append(normalized)
                merged_artifacts: list[dict[str, Any]] = []
                seen_artifact_keys: set[str] = set()
                for artifact in [*run_artifact_refs, *normalized_artifacts]:
                    if not isinstance(artifact, dict):
                        continue
                    artifact_id = str(artifact.get("artifact_id") or "").strip()
                    path_text = str(artifact.get("path") or "").strip()
                    key = f"{artifact_id}|{path_text}"
                    if not artifact_id or not path_text or key in seen_artifact_keys:
                        continue
                    seen_artifact_keys.add(key)
                    merged_artifacts.append(dict(artifact))
                run_artifact_refs = merged_artifacts[:48]
            run_manifest = {
                **run_manifest,
                **dict(existing_durable_run),
                "node_run_states": [deepcopy(item) for item in node_states.values()],
                "artifact_refs": deepcopy(run_artifact_refs),
                "event_refs": deepcopy(event_refs),
                "run_policy_snapshot": dict(
                    {
                        **dict(run_manifest.get("run_policy_snapshot") or {}),
                        **dict(existing_durable_run.get("run_policy_snapshot") or {}),
                        "node_mcp_tool_policies": dict(
                            dict(existing_durable_run.get("run_policy_snapshot") or {}).get("node_mcp_tool_policies")
                            or dict(run_manifest.get("run_policy_snapshot") or {}).get("node_mcp_tool_policies")
                            or {}
                        ),
                    }
                ),
            }
        preloaded_recovery_bindings: list[dict[str, Any]] = []
        if recovery_context and not isinstance(existing_durable_run, dict):
            source_run_id = str(recovery_context.get("source_run_id") or "").strip()
            preloaded_states = {
                str(node_id).strip(): dict(state)
                for node_id, state in dict(recovery_context.get("preloaded_node_states") or {}).items()
                if str(node_id).strip() and isinstance(state, dict)
            }
            for node_id, state in preloaded_states.items():
                if node_id not in node_states:
                    continue
                cloned_state = deepcopy(state)
                cloned_state["run_id"] = run_id
                cloned_state["updated_at"] = created_at
                cloned_state["reused_existing_output"] = True
                if source_run_id:
                    cloned_state["reused_from_run_id"] = source_run_id
                node_states[node_id] = cloned_state
                event_refs.append(
                    {
                        "event_id": f"{run_id}-{node_id}-reused",
                        "run_id": run_id,
                        "task_id": graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_progress",
                        "created_at": created_at,
                        "summary": (
                            f"{self._tasks._graph_node_label(graph, node_id)} reused preserved output "
                            f"from source run {source_run_id or 'unknown'}."
                        ),
                        "node_id": node_id,
                        "status": "completed",
                    }
                )
            preloaded_recovery_bindings = [
                deepcopy(dict(item))
                for item in list(recovery_context.get("preloaded_worker_bindings") or [])
                if isinstance(item, dict)
            ]
            for binding in preloaded_recovery_bindings:
                binding["run_id"] = run_id
                binding["updated_at"] = created_at
                binding["reused_existing_output"] = True
                if source_run_id:
                    binding["reused_from_run_id"] = source_run_id
                source_node_id = str(binding.get("node_id") or "").strip()
                binding_attempt_count = max(1, int(binding.get("attempt_count") or 1))
                rebound_handoffs: list[dict[str, Any]] = []
                for handoff in list(binding.get("downstream_handoffs") or []):
                    if not isinstance(handoff, dict):
                        continue
                    rebound = deepcopy(handoff)
                    target_node_id = str(rebound.get("to_node_id") or "").strip()
                    edge_id = str(rebound.get("edge_id") or "").strip()
                    if not source_node_id or not target_node_id or not edge_id:
                        rebound_handoffs.append(rebound)
                        continue
                    try:
                        rebound_envelope = self._tasks._load_graph_handoff_agent_envelope(  # noqa: SLF001
                            rebound,
                            expected_target_node_id=target_node_id,
                            graph_definition=graph,
                        )
                    except Exception:
                        rebound_handoffs.append(rebound)
                        continue
                    correlation_id = self._tasks._graph_worker_stable_identifier(  # noqa: SLF001
                        "corr",
                        run_id,
                        source_node_id,
                        binding_attempt_count,
                    )
                    causation_id = self._tasks._graph_worker_stable_identifier(  # noqa: SLF001
                        "cause",
                        run_id,
                        source_node_id,
                        binding_attempt_count,
                        "output",
                    )
                    envelope_id = self._tasks._graph_worker_stable_identifier(  # noqa: SLF001
                        "envelope",
                        run_id,
                        edge_id,
                        source_node_id,
                        target_node_id,
                        binding_attempt_count,
                    )
                    message_id = self._tasks._graph_worker_stable_identifier(  # noqa: SLF001
                        "message",
                        run_id,
                        edge_id,
                        source_node_id,
                        target_node_id,
                        binding_attempt_count,
                    )
                    delivery_idempotency_key = self._tasks._graph_worker_stable_identifier(  # noqa: SLF001
                        "delivery",
                        run_id,
                        edge_id,
                        source_node_id,
                        target_node_id,
                        binding_attempt_count,
                    )
                    rebound_envelope["run_id"] = run_id
                    rebound_envelope["created_at"] = created_at
                    rebound_envelope["envelope_id"] = envelope_id
                    rebound_envelope["message_id"] = message_id
                    rebound_envelope["delivery"] = {
                        **dict(rebound_envelope.get("delivery") or {}),
                        "attempt": binding_attempt_count,
                        "idempotency_key": delivery_idempotency_key,
                        "trace_id": f"trace-{run_id}",
                        "sequence": max(0, binding_attempt_count - 1),
                    }
                    rebound_envelope["metadata"] = {
                        **dict(rebound_envelope.get("metadata") or {}),
                        "context_id": f"context-{run_id}",
                        "correlation_id": correlation_id,
                        "causation_id": causation_id,
                        "provenance": {
                            **dict(dict(rebound_envelope.get("metadata") or {}).get("provenance") or {}),
                            "reused_from_run_id": source_run_id or None,
                        },
                    }
                    rebound_envelope_rel = (
                        Path("PRIVATE")
                        / "task-graph"
                        / "workers"
                        / run_id
                        / source_node_id
                        / f"reused-agent-envelope-{edge_id}.json"
                    ).as_posix()
                    write_json(workspace_root / rebound_envelope_rel, rebound_envelope)
                    downstream_input = {
                        **dict(rebound.get("downstream_input") or {}),
                        "agent_envelope_path": rebound_envelope_rel,
                    }
                    rebound["downstream_input"] = downstream_input
                    rebound["agent_envelope"] = {
                        **dict(rebound.get("agent_envelope") or {}),
                        "envelope_id": envelope_id,
                        "message_id": message_id,
                        "agent_envelope_path": rebound_envelope_rel,
                        "delivery": deepcopy(dict(rebound_envelope.get("delivery") or {})),
                        "sender": deepcopy(dict(rebound_envelope.get("sender") or {})),
                        "recipient": deepcopy(dict(rebound_envelope.get("recipient") or {})),
                        "metadata": deepcopy(dict(rebound_envelope.get("metadata") or {})),
                        "artifact_ref": {
                            "artifact_id": (
                                f"{str(binding.get('worker_thread_id') or source_node_id).strip() or source_node_id}-{edge_id}-agent-envelope-json"
                            ),
                            "artifact_kind": "structured_json",
                            "path": rebound_envelope_rel,
                            "status": "ready",
                        },
                    }
                    rebound_handoffs.append(rebound)
                if rebound_handoffs:
                    binding["downstream_handoffs"] = rebound_handoffs
            if preloaded_recovery_bindings:
                run_manifest["worker_bindings"] = preloaded_recovery_bindings[:80]
            run_manifest["run_policy_snapshot"] = {
                **dict(run_manifest.get("run_policy_snapshot") or {}),
                "recovery": {
                    "recovery_id": str(recovery_context.get("recovery_id") or "").strip() or None,
                    "source_run_id": source_run_id or None,
                    "strategy": str(recovery_context.get("strategy") or "").strip() or None,
                    "selected_node_ids": [str(item).strip() for item in list(recovery_context.get("selected_node_ids") or []) if str(item or "").strip()],
                    "initial_target_node_ids": [str(item).strip() for item in list(recovery_context.get("initial_target_node_ids") or []) if str(item or "").strip()],
                    "rerun_node_ids": [str(item).strip() for item in list(recovery_context.get("rerun_node_ids") or []) if str(item or "").strip()],
                    "reused_node_ids": [str(item).strip() for item in list(recovery_context.get("reused_node_ids") or []) if str(item or "").strip()],
                },
            }
        write_json(run_manifest_path, run_manifest)
        live_run_ref = self._tasks.record_graph_run(run_manifest, graph_definition=graph)
        if scheduler_run_id:
            # The queued receipt was admitted at state_version 1.  Promote the
            # durable projection before any provider turn starts; subsequent
            # snapshots continue through TaskService's CAS bridge.
            live_run_ref = dict(
                self._tasks.persist_graph_run_ref(
                    {
                        **dict(live_run_ref),
                        "status": "running",
                        "latest_event_type": "run_created",
                        "latest_event_at": created_at,
                    }
                ).get("run_ref")
                or live_run_ref
            )

        incoming_handoffs: dict[str, list[dict[str, Any]]] = self._graph_live_seed_incoming_handoffs(payload)
        restored_bindings = [
            dict(item)
            for item in list((existing_durable_run or {}).get("worker_bindings") or [])
            if isinstance(item, dict)
        ]
        if preloaded_recovery_bindings:
            restored_bindings.extend(deepcopy(preloaded_recovery_bindings))
        for binding in restored_bindings:
            source_node_id = str(binding.get("node_id") or "").strip()
            source_label = str(binding.get("agent_nickname") or source_node_id).strip() or source_node_id
            for handoff in list(binding.get("downstream_handoffs") or []):
                if not isinstance(handoff, dict):
                    continue
                target_node_id = str(handoff.get("to_node_id") or "").strip()
                if not target_node_id:
                    continue
                incoming_handoffs.setdefault(target_node_id, []).append(
                    {
                        "source_node_id": source_node_id,
                        "source_label": source_label,
                        "handoff": deepcopy(handoff),
                    }
                )
        original_visible_thread_id = self._tasks.visible_provider_thread_id(include_missing_fallback=True)
        active_node_id: str | None = None
        started_executions: list[dict[str, Any]] = []
        settled_execution_keys: set[tuple[str, str]] = set()
        reconciliation_records: list[dict[str, Any]] = []
        dispatch_limits = dict(dict(run_manifest.get("run_policy_snapshot") or {}).get("dispatch_control") or {})
        approval_state = deepcopy(dict(run_manifest.get("approval_state") or {"status": "not_required"}))

        try:
            for group_index, group in enumerate(parallel_groups):
                group_id = str(group.get("group_id") or "").strip() or f"group_{group_index}"
                current_durable_run = durable_store.load_run(run_id, include_events=False)
                cancellation_requested = self._graph_live_cancellation_requested(current_durable_run)
                group_candidates: list[dict[str, Any]] = []
                for node_id in [
                    str(item).strip()
                    for item in list(group.get("node_ids") or [])
                    if str(item or "").strip() and str(item).strip() in compiled_nodes
                ]:
                    if cancellation_requested:
                        continue
                    compiled_node = dict(compiled_nodes.get(node_id) or {})
                    graph_node = dict(node_map.get(node_id) or {})
                    dependency_node_ids = [
                        str(item).strip()
                        for item in list(compiled_node.get("dependency_node_ids") or [])
                        if str(item or "").strip()
                    ]
                    dependency_states = [dict(node_states.get(dep_id) or {}) for dep_id in dependency_node_ids]
                    if any(str(item.get("outcome") or "").strip() in {"blocked", "failed", "cancelled"} for item in dependency_states):
                        continue
                    if any(str(item.get("status") or "").strip() != "completed" for item in dependency_states):
                        continue
                    current_state = dict(node_states.get(node_id) or {})
                    current_status = str(current_state.get("status") or "").strip()
                    if current_status in {"completed", "failed", "cancelled", "needs_review", "blocked"}:
                        continue
                    raw_incoming_handoffs = incoming_handoffs.get(node_id) or []
                    try:
                        prepared_incoming_handoffs = self._graph_live_prepare_incoming_handoffs(
                            graph=graph,
                            node_id=node_id,
                            incoming_handoffs=raw_incoming_handoffs,
                        )
                    except Exception as exc:
                        failed_at = now_iso()
                        node_states[node_id].update(
                            {
                                "status": "failed",
                                "outcome": "failed",
                                "attempt_count": max(0, int(current_state.get("attempt_count") or 0)),
                                "updated_at": failed_at,
                                "summary": f"{self._tasks._graph_node_label(graph, node_id)} rejected an invalid structured handoff before provider dispatch.",
                            }
                        )
                        for index, item in enumerate(raw_incoming_handoffs, start=1):
                            handoff = dict(dict(item).get("handoff") or {})
                            agent_envelope = dict(handoff.get("agent_envelope") or {})
                            downstream_input = dict(handoff.get("downstream_input") or {})
                            envelope_id = str(agent_envelope.get("envelope_id") or "").strip() or f"invalid-{node_id}-{index}"
                            self._graph_live_append_unique_event(
                                event_refs,
                                {
                                    "event_id": f"{run_id}-{envelope_id}-rejected",
                                    "run_id": run_id,
                                    "task_id": graph["task_id"],
                                    "trace_id": f"trace-{run_id}",
                                    "event_type": "handoff_rejected",
                                    "created_at": failed_at,
                                    "summary": f"Structured handoff for {self._tasks._graph_node_label(graph, node_id)} was rejected before provider dispatch.",
                                    "node_id": node_id,
                                    "payload": {
                                        "envelope_id": envelope_id or None,
                                        "agent_envelope_path": str(downstream_input.get("agent_envelope_path") or "").strip() or None,
                                        "target_node_id": node_id,
                                        "error": str(exc)[:400],
                                    },
                                },
                            )
                        self._graph_live_append_unique_event(
                            event_refs,
                            {
                                "event_id": f"{run_id}-{node_id}-handoff-rejected",
                                "run_id": run_id,
                                "task_id": graph["task_id"],
                                "trace_id": f"trace-{run_id}",
                                "event_type": "node_failed",
                                "created_at": failed_at,
                                "summary": f"{self._tasks._graph_node_label(graph, node_id)} rejected an invalid structured handoff before provider dispatch.",
                                "node_id": node_id,
                                "parallel_group_id": group_id,
                            },
                        )
                        continue
                    inbound_edge_ids = {
                        str(item.get("edge_id") or "").strip()
                        for item in list(graph.get("edges") or [])
                        if isinstance(item, dict)
                        and str(item.get("to_node_id") or "").strip() == node_id
                    }
                    if inbound_edge_ids and not prepared_incoming_handoffs:
                        continue
                    for item in prepared_incoming_handoffs:
                        envelope = dict(item.get("agent_envelope") or {})
                        metadata = dict(envelope.get("metadata") or {})
                        delivery = dict(envelope.get("delivery") or {})
                        envelope_id = str(envelope.get("envelope_id") or "").strip()
                        self._graph_live_append_unique_event(
                            event_refs,
                            {
                                "event_id": f"{run_id}-{envelope_id}-ack",
                                "run_id": run_id,
                                "task_id": graph["task_id"],
                                "trace_id": f"trace-{run_id}",
                                "event_type": "handoff_acknowledged",
                                "created_at": now_iso(),
                                "summary": f"Structured handoff for {self._tasks._graph_node_label(graph, node_id)} was admitted for delivery.",
                                "node_id": node_id,
                                "payload": {
                                    "envelope_id": envelope_id,
                                    "message_id": str(envelope.get("message_id") or "").strip() or None,
                                    "delivery_idempotency_key": str(delivery.get("idempotency_key") or "").strip() or None,
                                    "correlation_id": str(metadata.get("correlation_id") or "").strip() or None,
                                    "causation_id": str(metadata.get("causation_id") or "").strip() or None,
                                    "source_node_id": str(metadata.get("source_node_id") or "").strip() or None,
                                    "target_node_id": str(metadata.get("target_node_id") or "").strip() or None,
                                },
                            },
                        )
                    prepared = dict(prepared_nodes[node_id])
                    prepared["compiled_node"] = compiled_node
                    prepared["executor_contract"] = dict(executor_contracts_by_node.get(node_id) or {})
                    prepared["dependency_node_ids"] = dependency_node_ids
                    prepared["existing_node_state"] = current_state
                    prepared["attempt_count"] = max(1, int(current_state.get("attempt_count") or 1))
                    prepared["incoming_handoffs"] = prepared_incoming_handoffs
                    neutral_context = self._graph_live_prepare_neutral_context_bundle(
                        graph=graph,
                        node=graph_node,
                        run_id=run_id,
                        incoming_handoffs=prepared_incoming_handoffs,
                        artifact_root=artifact_root,
                        attempt_count=int(prepared["attempt_count"] or 1),
                        target_provider_id=str(prepared["profile"].get("provider_id") or graph_node.get("provider_id") or "").strip(),
                    )
                    prepared["attachments"] = [
                        deepcopy(item)
                        for item in list(dict(neutral_context or {}).get("attachments") or [])
                        if isinstance(item, dict)
                    ]
                    prepared["neutral_context"] = dict(dict(neutral_context or {}).get("summary") or {})
                    if isinstance(neutral_context, dict):
                        run_artifact_refs = self._tasks._merge_graph_worker_artifact_refs(
                            run_artifact_refs,
                            [
                                dict(item)
                                for item in list(neutral_context.get("artifact_refs") or [])
                                if isinstance(item, dict)
                            ],
                        )
                    prepared["prompt_text"] = self._graph_live_run_prompt(
                        task=task,
                        graph=graph,
                        node=graph_node,
                        incoming_handoffs=prepared_incoming_handoffs,
                        neutral_context=dict(prepared.get("neutral_context") or {}),
                    )
                    group_candidates.append(prepared)

                # Prepare every worker lane before dispatching any provider turn in the group.
                # A lane-creation failure therefore cannot leave a sibling provider turn running.
                runnable_nodes: list[dict[str, Any]] = []
                for prepared in group_candidates:
                    node_id = str(prepared["node_id"])
                    graph_node = dict(prepared["graph_node"])
                    profile = dict(prepared["profile"])
                    existing_state = dict(prepared.get("existing_node_state") or {})
                    compiled_node = dict(prepared.get("compiled_node") or {})
                    executor_contract = dict(prepared.get("executor_contract") or {})
                    compiler_executor_id = str(
                        executor_contract.get("compiler_executor_id")
                        or compiled_node.get("compiler_executor_id")
                        or ""
                    ).strip() or "agent_lane"
                    if compiler_executor_id != "agent_lane":
                        worker = self._graph_live_local_worker_stub(
                            graph=graph,
                            run_id=run_id,
                            node_id=node_id,
                            graph_node=graph_node,
                            parent_thread_id=parent_thread_id,
                            existing_state=existing_state,
                        )
                    elif str(existing_state.get("status") or "").strip() == "running" and (
                        str(existing_state.get("worker_thread_id") or "").strip()
                        or str(existing_state.get("execution_thread_id") or "").strip()
                    ):
                        worker = {
                            "thread_id": str(existing_state.get("worker_thread_id") or existing_state.get("execution_thread_id") or "").strip(),
                            "parent_thread_id": str(existing_state.get("parent_thread_id") or "").strip() or None,
                            "spawn_mode": str(existing_state.get("spawn_mode") or "").strip() or None,
                            "worker_origin": str(existing_state.get("worker_origin") or "").strip() or "provider_lane",
                            "agent_role": str(existing_state.get("agent_role") or "").strip() or None,
                            "agent_nickname": str(existing_state.get("agent_nickname") or "").strip() or None,
                            "settings": {
                                "execution_backend": str(existing_state.get("execution_backend") or "app_server"),
                            },
                        }
                    else:
                        worker_result = self.start_graph_worker(
                            profile,
                            graph_id=graph_id,
                            run_id=run_id,
                            node_id=node_id,
                            parent_thread_id=parent_thread_id,
                            model=str(graph_node.get("model_id") or "").strip() or None,
                            effort=str(graph_node.get("reasoning_effort") or "").strip() or None,
                            permission_mode=str(graph_node.get("permission_mode") or "auto").strip() or "auto",
                        )
                        worker = dict(worker_result.get("worker") or {})
                    runnable_nodes.append({**prepared, "worker": worker})

                for execution in runnable_nodes:
                    current_durable_run = durable_store.load_run(run_id, include_events=False)
                    cancellation_requested = self._graph_live_cancellation_requested(current_durable_run)
                    if cancellation_requested:
                        break
                    node_id = str(execution["node_id"])
                    graph_node = dict(execution["graph_node"])
                    profile = dict(execution["profile"])
                    worker = dict(execution["worker"])
                    existing_state = dict(execution.get("existing_node_state") or {})
                    dependency_node_ids = list(execution.get("dependency_node_ids") or [])
                    compiled_node = dict(execution.get("compiled_node") or {})
                    executor_contract = dict(execution.get("executor_contract") or {})
                    compiler_executor_id = str(
                        executor_contract.get("compiler_executor_id")
                        or compiled_node.get("compiler_executor_id")
                        or ""
                    ).strip()
                    if compiler_executor_id != "agent_lane":
                        local_result = self._graph_live_execute_local_executor(
                            payload=payload,
                            task=task,
                            graph=graph,
                            graph_id=graph_id,
                            run_id=run_id,
                            group_id=group_id,
                            execution=execution,
                            compiler_executor_id=compiler_executor_id or "unknown_executor",
                            run_manifest=run_manifest,
                            run_manifest_path=run_manifest_path,
                            live_run_ref=live_run_ref,
                            run_artifact_refs=run_artifact_refs,
                            incoming_handoffs=incoming_handoffs,
                            node_states=node_states,
                            event_refs=event_refs,
                        )
                        live_run_ref = dict(local_result.get("live_run_ref") or live_run_ref)
                        if isinstance(local_result.get("approval_state"), dict):
                            approval_state = deepcopy(dict(local_result.get("approval_state") or {}))
                        run_artifact_refs = [
                            dict(item)
                            for item in list(local_result.get("artifact_refs") or run_artifact_refs)
                            if isinstance(item, dict)
                        ]
                        continue
                    retry_policy = dict(execution.get("retry_policy") or self._graph_live_retry_policy(compiled_node=compiled_node, graph_node=graph_node))
                    started_at = now_iso()
                    active_node_id = node_id
                    attempt_count = max(1, int(execution.get("attempt_count") or 1))
                    attempt_provider_id = str(existing_state.get("provider_id") or profile.get("provider_id") or graph_node.get("provider_id") or "").strip()
                    attempt_model = str(existing_state.get("model_id") or graph_node.get("model_id") or profile.get("model") or "").strip()
                    dispatch_request = self._graph_run_dispatch.build_dispatch_request(
                        run_id=run_id,
                        node_id=node_id,
                        provider_id=attempt_provider_id,
                        model_id=attempt_model,
                    )
                    dispatch_token, dispatch_admission = self._graph_dispatch_control.try_acquire(
                        dispatch_request,
                        limits=dispatch_limits,
                    )
                    if dispatch_token is None:
                        self._graph_live_fail_before_dispatch(
                            graph=graph,
                            run_id=run_id,
                            node_id=node_id,
                            group_id=group_id,
                            node_states=node_states,
                            event_refs=event_refs,
                            reason=str(dispatch_admission.get("reason") or "provider_dispatch_denied"),
                            detail=str(dispatch_admission.get("last_failure_category") or "").strip() or None,
                        )
                        continue
                    lease_ttl_seconds = self._graph_live_lease_ttl_seconds(payload)
                    attempt_started_at = str(existing_state.get("started_at") or started_at)
                    attempt_updated_at = str(existing_state.get("updated_at") or attempt_started_at)
                    existing_attempt_payload = next(
                        (
                            dict(item)
                            for item in list(dict(current_durable_run or {}).get("node_run_states") or [])
                            if isinstance(item, dict)
                            and str(item.get("node_id") or "").strip() == node_id
                            and max(1, int(item.get("attempt_count") or 1)) == attempt_count
                        ),
                        None,
                    )
                    if isinstance(existing_attempt_payload, dict):
                        attempt_started_at = str(existing_attempt_payload.get("started_at") or attempt_started_at)
                        attempt_updated_at = str(existing_attempt_payload.get("updated_at") or attempt_updated_at)
                    operation_id = self._graph_live_operation_id(
                        run_id=run_id,
                        node_id=node_id,
                        attempt=attempt_count,
                        kind="provider_turn_start",
                    )
                    lease = durable_store.acquire_lease(
                        run_id,
                        node_id,
                        attempt_count,
                        owner_boot_id=self._graph_scheduler.owner_id,
                        ttl_seconds=lease_ttl_seconds,
                    )
                    if not isinstance(existing_attempt_payload, dict):
                        durable_store.record_node_attempt(
                            run_id,
                            node_id,
                            attempt_count,
                            status="queued",
                            started_at=attempt_started_at,
                            updated_at=attempt_updated_at,
                            payload={
                                "node_id": node_id,
                                "run_id": run_id,
                                "attempt_count": attempt_count,
                                "status": "queued",
                                "outcome": "pending",
                                "started_at": attempt_started_at,
                                "updated_at": attempt_updated_at,
                                "worker_origin": None,
                                "provider_id": attempt_provider_id or None,
                                "model_id": attempt_model or None,
                                "retry_policy": retry_policy,
                                "lease_id": str(lease.get("lease_id") or "").strip() or None,
                                "attempt_operation_id": operation_id,
                            },
                        )
                    durable_store.enqueue_outbox(
                        operation_id,
                        run_id,
                        kind="provider_turn_start",
                        node_id=node_id,
                        payload={
                            "node_id": node_id,
                            "attempt_count": attempt_count,
                            "classification": "non_idempotent_write",
                        },
                    )
                    existing_external_operation = durable_store.get_external_operation(operation_id)
                    node_mcp_tool_policy_snapshot = deepcopy(
                        dict(
                            dict(dict(run_manifest.get("run_policy_snapshot") or {}).get("node_mcp_tool_policies") or {}).get(node_id)
                            or dict(dict(compiled_node.get("tool_policy") or {}).get("mcp_tool_policy") or {})
                        )
                    )
                    tool_policy = self._graph_worker_tool_policy(
                        dict(graph_node.get("tools") or {}),
                        node=graph_node,
                        graph_policy=dict(graph.get("graph_policy") or {}),
                        node_id=node_id,
                        mcp_tool_policy_snapshot=node_mcp_tool_policy_snapshot,
                    )
                    turn_execution_policy = self._graph_worker_turn_execution_policy(tool_policy)
                    worker_thread_id = str(worker.get("thread_id") or "").strip()
                    execution_thread_id = ""
                    turn_id = ""
                    if isinstance(existing_external_operation, dict) and str(existing_external_operation.get("status") or "").strip() == "needs_review":
                        node_states[node_id].update(
                            {
                                "status": "needs_review",
                                "outcome": "needs_review",
                                "attempt_count": attempt_count,
                                "updated_at": started_at,
                                "attempt_operation_id": operation_id,
                                "lease_id": str(lease.get("lease_id") or "").strip() or None,
                            }
                        )
                        if not any(str(item.get("event_id") or "") == f"{run_id}-{node_id}-needs-review" for item in event_refs):
                            event_refs.append(
                                {
                                    "event_id": f"{run_id}-{node_id}-needs-review",
                                    "run_id": run_id,
                                    "task_id": graph["task_id"],
                                    "trace_id": f"trace-{run_id}",
                                    "event_type": "node_blocked",
                                    "created_at": started_at,
                                    "summary": f"{self._tasks._graph_node_label(graph, node_id)} requires manual review before any replay.",
                                    "node_id": node_id,
                                    "parallel_group_id": group_id,
                                }
                            )
                        durable_store.release_lease(str(lease.get("lease_id") or ""), owner_boot_id=self._graph_scheduler.owner_id)
                        continue
                    if isinstance(existing_external_operation, dict) and str(existing_external_operation.get("status") or "").strip() in {"accepted", "completed"}:
                        execution_thread_id, turn_id = self._graph_live_parse_external_handle(existing_external_operation.get("external_handle"))
                    elif self._graph_live_test_hook_enabled(payload.get("_crash_before_provider_dispatch"), node_id=node_id):
                        raise _GraphDispatchCrashBeforeExternalCall(f"graph node {node_id} crashed before provider dispatch")
                    else:
                        try:
                            turn_result = self.start_turn(
                                profile,
                                thread_id=str(worker.get("thread_id") or ""),
                                text=str(execution.get("prompt_text") or ""),
                                attachments=[deepcopy(item) for item in list(execution.get("attachments") or []) if isinstance(item, dict)],
                                model=attempt_model or None,
                                effort=str(graph_node.get("reasoning_effort") or "").strip() or None,
                                permission_mode=str(graph_node.get("permission_mode") or "auto").strip() or "auto",
                                collaboration_mode=self._normalize_graph_worker_collaboration_mode(graph_node),
                                context_mode="no_context",
                                execution_policy=turn_execution_policy,
                                token_budget=int(execution.get("token_budget") or 0) or None,
                                token_budget_objective=(
                                    f"{str(graph.get('title') or graph_id).strip()} / "
                                    f"{self._tasks._graph_node_label(graph, node_id)}"
                                ),
                                mcp_tool_policy_snapshot=node_mcp_tool_policy_snapshot,
                                mcp_tool_policy_context={
                                    "graph_id": graph_id,
                                    "run_id": run_id,
                                    "node_id": node_id,
                                    "attempt_count": attempt_count,
                                    "worker_thread_id": worker_thread_id or None,
                                },
                            )
                        except Exception as exc:
                            durable_store.record_external_operation(
                                operation_id,
                                run_id,
                                kind="provider_turn_start",
                                classification="non_idempotent_write",
                                status="needs_review",
                                payload={
                                    "node_id": node_id,
                                    "attempt_count": attempt_count,
                                    "error_type": type(exc).__name__,
                                },
                            )
                            durable_store.update_outbox_status(
                                operation_id,
                                status="needs_review",
                                payload={
                                    "node_id": node_id,
                                    "attempt_count": attempt_count,
                                    "error_type": type(exc).__name__,
                                },
                            )
                            node_states[node_id].update(
                                {
                                    "status": "needs_review",
                                    "outcome": "needs_review",
                                    "attempt_count": attempt_count,
                                    "updated_at": started_at,
                                    "provider_id": attempt_provider_id or None,
                                    "model_id": attempt_model or None,
                                    "attempt_operation_id": operation_id,
                                    "lease_id": str(lease.get("lease_id") or "").strip() or None,
                                }
                            )
                            if not any(str(item.get("event_id") or "") == f"{run_id}-{node_id}-needs-review" for item in event_refs):
                                event_refs.append(
                                    {
                                        "event_id": f"{run_id}-{node_id}-needs-review",
                                        "run_id": run_id,
                                        "task_id": graph["task_id"],
                                        "trace_id": f"trace-{run_id}",
                                        "event_type": "node_blocked",
                                        "created_at": started_at,
                                        "summary": f"{self._tasks._graph_node_label(graph, node_id)} requires review after an ambiguous provider dispatch error.",
                                        "node_id": node_id,
                                        "parallel_group_id": group_id,
                                    }
                                )
                            durable_store.release_lease(str(lease.get("lease_id") or ""), owner_boot_id=self._graph_scheduler.owner_id)
                            live_run_ref = self._graph_live_run_snapshot(
                                run_ref=live_run_ref,
                                node_states=node_states,
                                event_refs=event_refs,
                                artifact_refs=run_artifact_refs,
                                policy_snapshot=run_manifest["run_policy_snapshot"],
                                status="running",
                            )
                            self._write_graph_live_run_manifest_snapshot(
                                run_manifest_path=run_manifest_path,
                                run_manifest=run_manifest,
                                node_states=node_states,
                                artifact_refs=run_artifact_refs,
                                event_refs=event_refs,
                                status="running",
                                updated_at=str(live_run_ref.get("updated_at") or ""),
                            )
                            continue
                        execution_thread_id = str(turn_result.get("thread_id") or worker_thread_id).strip()
                        turn_id = str(dict(turn_result.get("turn") or {}).get("id") or "").strip()
                    if not execution_thread_id:
                        raise RuntimeError("Task-graph turn start did not return an execution thread id.")
                    if not turn_id:
                        raise RuntimeError("Task-graph turn start did not return a turn id.")
                    durable_store.record_external_operation(
                        operation_id,
                        run_id,
                        kind="provider_turn_start",
                        classification="non_idempotent_write",
                        status="accepted",
                        external_handle=f"{execution_thread_id}:{turn_id}",
                        payload={
                            "node_id": node_id,
                            "attempt_count": attempt_count,
                            "worker_thread_id": worker_thread_id or None,
                            "execution_thread_id": execution_thread_id,
                            "turn_id": turn_id,
                        },
                    )
                    durable_store.update_outbox_status(
                        operation_id,
                        status="accepted",
                        payload={
                            "node_id": node_id,
                            "attempt_count": attempt_count,
                            "worker_thread_id": worker_thread_id or None,
                            "execution_thread_id": execution_thread_id,
                            "turn_id": turn_id,
                        },
                    )
                    node_states[node_id].update(
                        {
                            "status": "running",
                            "outcome": "pending",
                            "attempt_count": attempt_count,
                            "started_at": str(existing_state.get("started_at") or started_at),
                            "updated_at": started_at,
                            "worker_origin": str(worker.get("worker_origin") or "").strip() or "provider_lane",
                            "provider_id": attempt_provider_id or None,
                            "model_id": attempt_model or None,
                            "worker_thread_id": worker_thread_id or None,
                            "execution_thread_id": execution_thread_id,
                            "turn_id": turn_id,
                            "parent_thread_id": str(worker.get("parent_thread_id") or "").strip() or None,
                            "spawn_mode": str(worker.get("spawn_mode") or "").strip() or None,
                            "agent_role": str(worker.get("agent_role") or "").strip() or None,
                            "agent_nickname": str(worker.get("agent_nickname") or "").strip() or None,
                            "execution_backend": str(dict(worker.get("settings") or {}).get("execution_backend") or "app_server"),
                            "token_budget": int(execution.get("token_budget") or 0) or None,
                            "turn_execution_policy": turn_execution_policy,
                            "attempt_operation_id": operation_id,
                            "lease_id": str(lease.get("lease_id") or "").strip() or None,
                            "retry_policy": retry_policy,
                        }
                    )
                    if dependency_node_ids:
                        dependency_outcomes = [
                            str(dict(node_states.get(dep_id) or {}).get("outcome") or "").strip() or "unknown"
                            for dep_id in dependency_node_ids
                        ]
                        if not any(str(item.get("event_id") or "") == f"{run_id}-{node_id}-join-ready" for item in event_refs):
                            event_refs.append(
                                {
                                    "event_id": f"{run_id}-{node_id}-join-ready",
                                    "run_id": run_id,
                                    "task_id": graph["task_id"],
                                    "trace_id": f"trace-{run_id}",
                                    "event_type": "node_progress",
                                    "created_at": started_at,
                                    "summary": (
                                        f"{self._tasks._graph_node_label(graph, node_id)} satisfied join "
                                        f"`{str(compiled_node.get('join_mode') or 'all_required')}` after dependencies "
                                        f"{', '.join(dependency_node_ids)} resolved as {', '.join(dependency_outcomes)}."
                                    ),
                                    "node_id": node_id,
                                    "parallel_group_id": group_id,
                                }
                            )
                    if not any(str(item.get("event_id") or "") == f"{run_id}-{node_id}-started" for item in event_refs):
                        event_refs.append(
                            {
                                "event_id": f"{run_id}-{node_id}-started",
                                "run_id": run_id,
                                "task_id": graph["task_id"],
                                "trace_id": f"trace-{run_id}",
                                "event_type": "node_started",
                                "created_at": started_at,
                                "summary": f"{self._tasks._graph_node_label(graph, node_id)} live execution started.",
                                "node_id": node_id,
                                "parallel_group_id": group_id,
                                "worker_thread_id": worker_thread_id or None,
                                "execution_thread_id": execution_thread_id,
                            }
                        )
                    self._record_event(
                        {
                            "type": "graph_worker_turn_thread_resolved",
                            "graph_id": graph_id,
                            "run_id": run_id,
                            "node_id": node_id,
                            "worker_thread_id": worker_thread_id,
                            "execution_thread_id": execution_thread_id,
                            "turn_id": turn_id,
                            "provider_handoff": execution_thread_id != worker_thread_id,
                            "token_budget": int(execution.get("token_budget") or 0) or None,
                        }
                    )
                    live_run_ref = self._graph_live_run_snapshot(
                        run_ref=live_run_ref,
                        node_states=node_states,
                        event_refs=event_refs,
                        artifact_refs=run_artifact_refs,
                        policy_snapshot=run_manifest["run_policy_snapshot"],
                        status="running",
                    )
                    self._write_graph_live_run_manifest_snapshot(
                        run_manifest_path=run_manifest_path,
                        run_manifest=run_manifest,
                        node_states=node_states,
                        artifact_refs=run_artifact_refs,
                        event_refs=event_refs,
                        status="running",
                        updated_at=str(live_run_ref.get("updated_at") or ""),
                    )
                    if self._graph_live_test_hook_enabled(payload.get("_crash_after_provider_handle"), node_id=node_id):
                        raise _GraphDispatchCrashAfterHandleAccepted(f"graph node {node_id} crashed after provider handle acceptance")
                    execution.update(
                        {
                            "dispatch_request": dispatch_request,
                            "dispatch_token": dispatch_token,
                            "execution_thread_id": execution_thread_id,
                            "turn_id": turn_id,
                            "started_monotonic": time.monotonic(),
                            "attempt_count": attempt_count,
                            "lease_id": str(lease.get("lease_id") or "").strip() or None,
                            "attempt_operation_id": operation_id,
                            "attempt_provider_id": attempt_provider_id or None,
                            "attempt_model": attempt_model or None,
                            "retry_policy": retry_policy,
                        }
                    )
                    started_executions.append(execution)
                for execution in [
                    item
                    for item in runnable_nodes
                    if str(item.get("execution_thread_id") or "").strip()
                    and str(item.get("turn_id") or "").strip()
                ]:
                    node_id = str(execution["node_id"])
                    active_node_id = node_id
                    graph_node = dict(execution["graph_node"] or {})
                    profile = dict(execution["profile"] or {})
                    worker = dict(execution["worker"] or {})
                    retry_policy = dict(execution.get("retry_policy") or {})
                    worker_output: dict[str, Any] | None = None
                    while True:
                        attempt_count = max(1, int(execution.get("attempt_count") or 1))
                        attempt_provider_id = str(execution.get("attempt_provider_id") or profile.get("provider_id") or graph_node.get("provider_id") or "").strip()
                        attempt_model = str(execution.get("attempt_model") or graph_node.get("model_id") or profile.get("model") or "").strip()
                        lease_id = str(execution.get("lease_id") or "").strip()
                        heartbeat_stop: threading.Event | None = None
                        heartbeat_thread: threading.Thread | None = None
                        retry_next_attempt: dict[str, Any] | None = None
                        runtime_status = self._prepare_runtime(profile, require_secret=True)
                        client = self._ensure_client(runtime_status)
                        try:
                            if lease_id:
                                heartbeat_stop, heartbeat_thread = self._start_graph_live_lease_heartbeat(
                                    store=durable_store,
                                    lease_id=lease_id,
                                    owner_boot_id=self._graph_scheduler.owner_id,
                                    ttl_seconds=self._graph_live_lease_ttl_seconds(payload),
                                )
                            terminal_thread = self._wait_for_probe_turn_terminal(
                                client,
                                thread_id=str(execution.get("execution_thread_id") or worker.get("thread_id") or ""),
                                turn_id=str(execution.get("turn_id") or ""),
                                timeout_seconds=float(execution.get("timeout_seconds") or 210.0),
                                operation_label=f"task graph node {self._tasks._graph_node_label(graph, node_id)}",
                            )
                            if int(execution.get("token_budget") or 0) > 0:
                                self._stop_bounded_turn_follow_on_execution(
                                    profile,
                                    client,
                                    thread_id=str(execution.get("execution_thread_id") or worker.get("thread_id") or ""),
                                    completed_turn_id=str(execution.get("turn_id") or ""),
                                )
                            else:
                                self._clear_active_turn_execution_policy(
                                    thread_id=str(execution.get("execution_thread_id") or worker.get("thread_id") or ""),
                                    turn_id=str(execution.get("turn_id") or ""),
                                )
                            thread_status, final_text, reasoning_text = self._probe_turn_result(
                                terminal_thread,
                                turn_id=str(execution.get("turn_id") or ""),
                            )
                            execution_key = (
                                str(execution.get("execution_thread_id") or ""),
                                str(execution.get("turn_id") or ""),
                            )
                            settled_execution_keys.add(execution_key)
                            completion_inbox_key = self._graph_live_completion_inbox_key(
                                run_id=run_id,
                                node_id=node_id,
                                attempt=attempt_count,
                                execution_thread_id=str(execution.get("execution_thread_id") or ""),
                                turn_id=str(execution.get("turn_id") or ""),
                            )
                            if not durable_store.record_inbox(
                                completion_inbox_key,
                                run_id=run_id,
                                event_id=f"{run_id}-{node_id}-terminal-{attempt_count}",
                                payload={"node_id": node_id, "attempt_count": attempt_count},
                            ):
                                duplicate_operation_id = str(execution.get("attempt_operation_id") or node_states.get(node_id, {}).get("attempt_operation_id") or "").strip()
                                if duplicate_operation_id:
                                    durable_store.record_external_operation(
                                        duplicate_operation_id,
                                        run_id,
                                        kind="provider_turn_start",
                                        classification="non_idempotent_write",
                                        status="completed",
                                        external_handle=f"{str(execution.get('execution_thread_id') or '')}:{str(execution.get('turn_id') or '')}",
                                        payload={"node_id": node_id, "attempt_count": attempt_count},
                                    )
                                    durable_store.update_outbox_status(
                                        duplicate_operation_id,
                                        status="completed",
                                        payload={"node_id": node_id, "attempt_count": attempt_count},
                                    )
                                self._record_event(
                                    {
                                        "type": "duplicate_effect_suppressed",
                                        "trace_id": f"trace-{run_id}",
                                        "run_id": run_id,
                                        "node_id": node_id,
                                        "attempt_count": attempt_count,
                                        "thread_id": str(execution.get("execution_thread_id") or "").strip() or None,
                                        "turn_id": str(execution.get("turn_id") or "").strip() or None,
                                        "operation_id": duplicate_operation_id or None,
                                        "reason": "delivery_completion_inbox_duplicate",
                                    }
                                )
                                worker_output = {"worker_binding": {}, "run_ref": self._tasks.graph_run_ref(run_id)}
                                break
                            finished_at = now_iso()
                            elapsed_ms = max(
                                0,
                                int((time.monotonic() - float(execution.get("started_monotonic") or time.monotonic())) * 1000),
                            )
                            usage_signal = self._graph_live_turn_usage_signal(
                                thread_id=str(execution.get("execution_thread_id") or ""),
                                turn_id=str(execution.get("turn_id") or ""),
                                provider_id=attempt_provider_id or None,
                                model=attempt_model or None,
                            )
                            policy_violation = self._turn_execution_policy_violation(
                                thread_id=str(execution.get("execution_thread_id") or ""),
                                turn_id=str(execution.get("turn_id") or ""),
                            )
                            token_budget = int(execution.get("token_budget") or 0)
                            observed_tokens = dict(usage_signal.get("tokens") or {}).get("total_tokens")
                            budget_exceeded = (
                                token_budget > 0
                                and isinstance(observed_tokens, int)
                                and observed_tokens > token_budget
                            )
                            parsed_output = self._graph_live_run_parse_response(final_text)
                            terminal_outcome = self._graph_live_run_terminal_outcome(
                                node_label=self._tasks._graph_node_label(graph, node_id),
                                thread_status=thread_status,
                                final_text=final_text,
                                reasoning_text=reasoning_text,
                                parsed_output=parsed_output,
                                policy_violation=policy_violation,
                                budget_exceeded=budget_exceeded,
                                observed_tokens=observed_tokens,
                                token_budget=token_budget,
                            )
                            node_status = str(terminal_outcome.get("node_status") or "failed")
                            outcome = str(terminal_outcome.get("outcome") or "failed")
                            summary = str(terminal_outcome.get("summary") or "").strip() or (
                                f"{self._tasks._graph_node_label(graph, node_id)} finished with status {thread_status or 'failed'}."
                            )
                            output_human_summary = str(terminal_outcome.get("output_human_summary") or "").strip()
                            machine_result = dict(terminal_outcome.get("machine_result") or {})
                            contract_failure = None
                            if node_status == "completed":
                                contract_failure = self._graph_live_validate_machine_result_contract(
                                    graph=graph,
                                    node_id=node_id,
                                    node_label=self._tasks._graph_node_label(graph, node_id),
                                    machine_result=machine_result,
                                )
                            if isinstance(contract_failure, dict):
                                node_status = str(contract_failure.get("node_status") or "failed")
                                outcome = str(contract_failure.get("outcome") or "schema_violation")
                                summary = str(contract_failure.get("summary") or "").strip() or summary
                                output_human_summary = str(contract_failure.get("output_human_summary") or "").strip()
                                machine_result = dict(contract_failure.get("machine_result") or {})
                                terminal_outcome["next_action_hints"] = list(contract_failure.get("next_action_hints") or [])
                            effective_policy_violation = dict(terminal_outcome.get("policy_violation") or {}) or None
                            tool_call_count = int(dict(effective_policy_violation or {}).get("blocked_tool_call_count") or 0)
                            next_action_hints = [
                                str(item).strip()
                                for item in list(terminal_outcome.get("next_action_hints") or [])
                                if str(item or "").strip()
                            ]
                            node_states[node_id].update(
                                {
                                    "status": node_status,
                                    "outcome": outcome,
                                    "updated_at": finished_at,
                                    "elapsed_ms": elapsed_ms,
                                    "provider_call_count": attempt_count,
                                    "tool_call_count": tool_call_count,
                                    "execution_policy": effective_policy_violation,
                                    "usage_signal": usage_signal,
                                    "token_budget": token_budget or None,
                                    "provider_id": attempt_provider_id or None,
                                    "model_id": attempt_model or None,
                                }
                            )
                            completion_operation_id = str(execution.get("attempt_operation_id") or node_states.get(node_id, {}).get("attempt_operation_id") or "").strip()
                            current_durable_run = durable_store.load_run(run_id, include_events=False)
                            cancellation_requested = self._graph_live_cancellation_requested(current_durable_run)
                            late_result_suppressed = False
                            if cancellation_requested:
                                late_result_suppressed = str(thread_status or "").strip().lower() != "cancelled"
                                node_status = "cancelled"
                                outcome = "cancelled"
                                summary = (
                                    f"{self._tasks._graph_node_label(graph, node_id)} completed after cancellation was requested; the late provider result was suppressed."
                                    if late_result_suppressed
                                    else f"{self._tasks._graph_node_label(graph, node_id)} was cancelled before completion."
                                )
                                output_human_summary = ""
                                machine_result = {
                                    "status": "cancelled",
                                    "late_result_suppressed": late_result_suppressed,
                                }
                                next_action_hints = []
                                node_states[node_id].update(
                                    {
                                        "status": "cancelled",
                                        "outcome": "cancelled",
                                        "updated_at": finished_at,
                                        "cancellation_resolution": "late_result_suppressed" if late_result_suppressed else "provider_turn_cancelled",
                                    }
                                )
                            raw_failure_text = " ".join(
                                part
                                for part in (summary, str(machine_result.get("response_text") or ""), final_text)
                                if str(part or "").strip()
                            )
                            failure_notice: dict[str, Any] | None = None
                            retryable = False
                            if node_status == "completed":
                                self._graph_dispatch_control.record_success(
                                    execution.get("dispatch_request")
                                    or self._graph_run_dispatch.build_dispatch_request(
                                        run_id=run_id,
                                        node_id=node_id,
                                        provider_id=attempt_provider_id,
                                        model_id=attempt_model,
                                    )
                                )
                            if node_status == "failed":
                                failure_notice = self._graph_live_failure_notice(
                                    raw_failure_text,
                                    provider_id=attempt_provider_id,
                                    model_id=attempt_model,
                                )
                                self._graph_dispatch_control.record_failure(
                                    execution.get("dispatch_request")
                                    or self._graph_run_dispatch.build_dispatch_request(
                                        run_id=run_id,
                                        node_id=node_id,
                                        provider_id=attempt_provider_id,
                                        model_id=attempt_model,
                                    ),
                                    category=str(failure_notice.get("category") or "unknown"),
                                    message=str(failure_notice.get("message") or raw_failure_text),
                                    limits=dispatch_limits,
                                )
                            if (
                                failure_notice is not None
                                and attempt_count < max(1, int(retry_policy.get("max_attempts") or 1))
                                and not cancellation_requested
                                and not bool(dict(graph_node.get("execution_policy") or {}).get("allow_code_changes"))
                                and not bool(dict(graph_node.get("execution_policy") or {}).get("allow_install"))
                                and tool_call_count == 0
                                and outcome not in {"invalid_output", "policy_violated", "needs_review", "schema_violation", "handoff_contract_violation"}
                            ):
                                retryable = bool(failure_notice.get("retryable"))
                                if retryable:
                                    retryable, _retry_budget = self._graph_dispatch_control.consume_retry_budget(
                                        execution.get("dispatch_request")
                                        or self._graph_run_dispatch.build_dispatch_request(
                                            run_id=run_id,
                                            node_id=node_id,
                                            provider_id=attempt_provider_id,
                                            model_id=attempt_model,
                                        ),
                                        limits=dispatch_limits,
                                    )
                                    if not retryable:
                                        next_action_hints.append(
                                            f"Retry budget exhausted for {attempt_provider_id or 'provider'} / {attempt_model or 'model'}."
                                        )
                            if retryable:
                                next_attempt_count = attempt_count + 1
                                next_attempt_model = self._graph_live_next_attempt_model(
                                    current_model=attempt_model,
                                    retry_policy=retry_policy,
                                    failure_notice=failure_notice or {},
                                )
                                delay_seconds = self._graph_live_retry_delay_seconds(
                                    run_id=run_id,
                                    node_id=node_id,
                                    attempt_count=attempt_count,
                                    retry_policy=retry_policy,
                                    failure_notice=failure_notice or {},
                                    raw_message=raw_failure_text,
                                )
                                if completion_operation_id:
                                    durable_store.record_external_operation(
                                        completion_operation_id,
                                        run_id,
                                        kind="provider_turn_start",
                                        classification="non_idempotent_write",
                                        status="failed",
                                        external_handle=f"{str(execution.get('execution_thread_id') or '')}:{str(execution.get('turn_id') or '')}",
                                        payload={
                                            "node_id": node_id,
                                            "attempt_count": attempt_count,
                                            "node_status": node_status,
                                            "outcome": outcome,
                                            "failure_notice": failure_notice,
                                        },
                                    )
                                    durable_store.update_outbox_status(
                                        completion_operation_id,
                                        status="failed",
                                        payload={
                                            "node_id": node_id,
                                            "attempt_count": attempt_count,
                                            "node_status": node_status,
                                            "outcome": outcome,
                                            "failure_notice": failure_notice,
                                        },
                                    )
                                retry_event_id = f"{run_id}-{node_id}-retry-{next_attempt_count}"
                                event_refs.append(
                                    {
                                        "event_id": retry_event_id,
                                        "run_id": run_id,
                                        "task_id": graph["task_id"],
                                        "trace_id": f"trace-{run_id}",
                                        "event_type": "node_progress",
                                        "created_at": finished_at,
                                        "summary": (
                                            f"{self._tasks._graph_node_label(graph, node_id)} scheduled retry attempt {next_attempt_count} "
                                            f"after {int(delay_seconds * 1000)} ms"
                                            + (f" using fallback model {next_attempt_model}." if next_attempt_model != attempt_model else ".")
                                        ),
                                        "node_id": node_id,
                                        "parallel_group_id": group_id,
                                    }
                                )
                                for handoff_item in list(execution.get("incoming_handoffs") or []):
                                    envelope = dict(dict(handoff_item).get("agent_envelope") or {})
                                    metadata = dict(envelope.get("metadata") or {})
                                    delivery = dict(envelope.get("delivery") or {})
                                    envelope_id = str(envelope.get("envelope_id") or "").strip()
                                    if not envelope_id:
                                        continue
                                    self._graph_live_append_unique_event(
                                        event_refs,
                                        {
                                            "event_id": f"{run_id}-{envelope_id}-retry-{next_attempt_count}",
                                            "run_id": run_id,
                                            "task_id": graph["task_id"],
                                            "trace_id": f"trace-{run_id}",
                                            "event_type": "handoff_retry_scheduled",
                                            "created_at": finished_at,
                                            "summary": f"Structured handoff for {self._tasks._graph_node_label(graph, node_id)} scheduled retry attempt {next_attempt_count}.",
                                            "node_id": node_id,
                                            "parallel_group_id": group_id,
                                            "payload": {
                                                "envelope_id": envelope_id,
                                                "message_id": str(envelope.get("message_id") or "").strip() or None,
                                                "delivery_idempotency_key": str(delivery.get("idempotency_key") or "").strip() or None,
                                                "correlation_id": str(metadata.get("correlation_id") or "").strip() or None,
                                                "causation_id": str(metadata.get("causation_id") or "").strip() or None,
                                                "source_node_id": str(metadata.get("source_node_id") or "").strip() or None,
                                                "target_node_id": str(metadata.get("target_node_id") or "").strip() or None,
                                                "retry_attempt": next_attempt_count,
                                            },
                                        },
                                    )
                                node_states[node_id].update(
                                    {
                                        "status": "queued",
                                        "outcome": "pending",
                                        "updated_at": finished_at,
                                        "attempt_count": next_attempt_count,
                                        "provider_id": attempt_provider_id or None,
                                        "model_id": next_attempt_model or None,
                                    }
                                )
                                retry_next_attempt = {
                                    "attempt_count": next_attempt_count,
                                    "attempt_model": next_attempt_model,
                                    "attempt_provider_id": attempt_provider_id,
                                    "delay_seconds": delay_seconds,
                                    "finished_at": finished_at,
                                    "failure_notice": deepcopy(failure_notice or {}),
                                }
                            else:
                                completion_status = (
                                    "cancelled"
                                    if node_status == "cancelled" or outcome == "cancelled"
                                    else ("needs_review" if node_status == "needs_review" or outcome == "needs_review" else ("failed" if node_status == "failed" else "completed"))
                                )
                                if completion_operation_id:
                                    durable_store.record_external_operation(
                                        completion_operation_id,
                                        run_id,
                                        kind="provider_turn_start",
                                        classification="non_idempotent_write",
                                        status=completion_status,
                                        external_handle=f"{str(execution.get('execution_thread_id') or '')}:{str(execution.get('turn_id') or '')}",
                                        payload={
                                            "node_id": node_id,
                                            "attempt_count": attempt_count,
                                            "node_status": node_status,
                                            "outcome": outcome,
                                            "failure_notice": failure_notice,
                                        },
                                    )
                                    durable_store.update_outbox_status(
                                        completion_operation_id,
                                        status=completion_status,
                                        payload={
                                            "node_id": node_id,
                                            "attempt_count": attempt_count,
                                            "node_status": node_status,
                                            "outcome": outcome,
                                            "failure_notice": failure_notice,
                                        },
                                    )
                                if node_status == "cancelled":
                                    worker_output = {"worker_binding": {}, "run_ref": self._tasks.graph_run_ref(run_id)}
                                else:
                                    worker_output_payload = {
                                        "graph_id": graph_id,
                                        "run_id": run_id,
                                        "node_id": node_id,
                                        "worker_thread_id": str(worker.get("thread_id") or ""),
                                        "parent_thread_id": str(worker.get("parent_thread_id") or ""),
                                        "spawn_mode": str(worker.get("spawn_mode") or ""),
                                        "worker_origin": str(worker.get("worker_origin") or ""),
                                        "agent_role": str(worker.get("agent_role") or ""),
                                        "agent_nickname": str(worker.get("agent_nickname") or ""),
                                        "execution_backend": str(dict(worker.get("settings") or {}).get("execution_backend") or "app_server"),
                                        "human_summary": output_human_summary,
                                        "machine_result": machine_result,
                                        "next_action_hints": next_action_hints,
                                        "status": node_status,
                                        "provider_id": attempt_provider_id or None,
                                        "model": attempt_model or None,
                                        "provider_call_count": attempt_count,
                                        "tool_call_count": tool_call_count,
                                        "execution_policy": effective_policy_violation,
                                        "usage_signal": usage_signal,
                                        "elapsed_ms": elapsed_ms,
                                        "attempt_count": attempt_count,
                                    }
                                    try:
                                        worker_output = self._tasks.record_graph_worker_output(
                                            worker_output_payload,
                                            graph_definition=graph,
                                        )
                                    except GraphContractValidationError as exc:
                                        node_status = "failed"
                                        outcome = "handoff_contract_violation"
                                        summary = (
                                            f"{self._tasks._graph_node_label(graph, node_id)} produced output that violated the live handoff contract."
                                        )
                                        output_human_summary = ""
                                        machine_result = {
                                            "status": "handoff_contract_violation",
                                            "error": str(exc),
                                        }
                                        next_action_hints = [
                                            "Fix the source node output or edge port bindings before rerunning this graph."
                                        ]
                                        node_states[node_id].update(
                                            {
                                                "status": node_status,
                                                "outcome": outcome,
                                                "updated_at": finished_at,
                                            }
                                        )
                                        if completion_operation_id:
                                            durable_store.record_external_operation(
                                                completion_operation_id,
                                                run_id,
                                                kind="provider_turn_start",
                                                classification="non_idempotent_write",
                                                status="failed",
                                                external_handle=f"{str(execution.get('execution_thread_id') or '')}:{str(execution.get('turn_id') or '')}",
                                                payload={
                                                    "node_id": node_id,
                                                    "attempt_count": attempt_count,
                                                    "node_status": node_status,
                                                    "outcome": outcome,
                                                    "failure_notice": {"message": str(exc)},
                                                },
                                            )
                                            durable_store.update_outbox_status(
                                                completion_operation_id,
                                                status="failed",
                                                payload={
                                                    "node_id": node_id,
                                                    "attempt_count": attempt_count,
                                                    "node_status": node_status,
                                                    "outcome": outcome,
                                                    "failure_notice": {"message": str(exc)},
                                                },
                                            )
                                        worker_output_payload.update(
                                            {
                                                "human_summary": output_human_summary,
                                                "machine_result": machine_result,
                                                "next_action_hints": next_action_hints,
                                                "status": node_status,
                                            }
                                        )
                                        worker_output = self._tasks.record_graph_worker_output(
                                            worker_output_payload,
                                            graph_definition=graph,
                                        )
                                if node_status == "failed":
                                    for handoff_item in list(execution.get("incoming_handoffs") or []):
                                        envelope = dict(dict(handoff_item).get("agent_envelope") or {})
                                        metadata = dict(envelope.get("metadata") or {})
                                        delivery = dict(envelope.get("delivery") or {})
                                        envelope_id = str(envelope.get("envelope_id") or "").strip()
                                        if not envelope_id:
                                            continue
                                        self._graph_live_append_unique_event(
                                            event_refs,
                                            {
                                                "event_id": f"{run_id}-{envelope_id}-delivery-failed-{attempt_count}",
                                                "run_id": run_id,
                                                "task_id": graph["task_id"],
                                                "trace_id": f"trace-{run_id}",
                                                "event_type": "handoff_delivery_failed",
                                                "created_at": finished_at,
                                                "summary": f"Structured handoff for {self._tasks._graph_node_label(graph, node_id)} ended in delivery failure.",
                                                "node_id": node_id,
                                                "parallel_group_id": group_id,
                                                "payload": {
                                                    "envelope_id": envelope_id,
                                                    "message_id": str(envelope.get("message_id") or "").strip() or None,
                                                    "delivery_idempotency_key": str(delivery.get("idempotency_key") or "").strip() or None,
                                                    "correlation_id": str(metadata.get("correlation_id") or "").strip() or None,
                                                    "causation_id": str(metadata.get("causation_id") or "").strip() or None,
                                                    "source_node_id": str(metadata.get("source_node_id") or "").strip() or None,
                                                    "target_node_id": str(metadata.get("target_node_id") or "").strip() or None,
                                                    "node_outcome": outcome,
                                                },
                                            },
                                        )
                        finally:
                            self._graph_dispatch_control.release(str(execution.get("dispatch_token") or "").strip())
                            if heartbeat_stop is not None:
                                heartbeat_stop.set()
                            if heartbeat_thread is not None:
                                heartbeat_thread.join(timeout=2.0)
                            if lease_id:
                                try:
                                    durable_store.release_lease(
                                        lease_id,
                                        owner_boot_id=self._graph_scheduler.owner_id,
                                    )
                                except Exception:
                                    pass
                        if retry_next_attempt is None:
                            break
                        live_run_ref = self._graph_live_run_snapshot(
                            run_ref=live_run_ref,
                            node_states=node_states,
                            event_refs=event_refs,
                            artifact_refs=run_artifact_refs,
                            policy_snapshot=run_manifest["run_policy_snapshot"],
                            status="running",
                        )
                        self._write_graph_live_run_manifest_snapshot(
                            run_manifest_path=run_manifest_path,
                            run_manifest=run_manifest,
                            node_states=node_states,
                            artifact_refs=run_artifact_refs,
                            event_refs=event_refs,
                            status="running",
                            updated_at=str(live_run_ref.get("updated_at") or ""),
                        )
                        delay_seconds = float(retry_next_attempt.get("delay_seconds") or 0.0)
                        if delay_seconds > 0:
                            time.sleep(delay_seconds)
                        current_durable_run = durable_store.load_run(run_id, include_events=False)
                        if self._graph_live_cancellation_requested(current_durable_run):
                            break
                        next_attempt_count = int(retry_next_attempt["attempt_count"])
                        next_attempt_model = str(retry_next_attempt["attempt_model"] or "").strip()
                        next_dispatch_request = self._graph_run_dispatch.build_dispatch_request(
                            run_id=run_id,
                            node_id=node_id,
                            provider_id=str(retry_next_attempt.get("attempt_provider_id") or attempt_provider_id or "").strip(),
                            model_id=next_attempt_model,
                        )
                        next_dispatch_token, next_dispatch_admission = self._graph_dispatch_control.try_acquire(
                            next_dispatch_request,
                            limits=dispatch_limits,
                        )
                        if next_dispatch_token is None:
                            self._graph_live_fail_before_dispatch(
                                graph=graph,
                                run_id=run_id,
                                node_id=node_id,
                                group_id=group_id,
                                node_states=node_states,
                                event_refs=event_refs,
                                reason=str(next_dispatch_admission.get("reason") or "provider_dispatch_denied"),
                                detail=str(next_dispatch_admission.get("last_failure_category") or "").strip() or None,
                            )
                            break
                        next_started_at = now_iso()
                        next_operation_id = self._graph_live_operation_id(
                            run_id=run_id,
                            node_id=node_id,
                            attempt=next_attempt_count,
                            kind="provider_turn_start",
                        )
                        next_lease = durable_store.acquire_lease(
                            run_id,
                            node_id,
                            next_attempt_count,
                            owner_boot_id=self._graph_scheduler.owner_id,
                            ttl_seconds=self._graph_live_lease_ttl_seconds(payload),
                        )
                        durable_store.record_node_attempt(
                            run_id,
                            node_id,
                            next_attempt_count,
                            status="queued",
                            started_at=next_started_at,
                            updated_at=next_started_at,
                            payload={
                                "node_id": node_id,
                                "run_id": run_id,
                                "attempt_count": next_attempt_count,
                                "status": "queued",
                                "outcome": "pending",
                                "started_at": next_started_at,
                                "updated_at": next_started_at,
                                "worker_origin": str(worker.get("worker_origin") or "").strip() or "provider_lane",
                                "provider_id": attempt_provider_id or None,
                                "model_id": next_attempt_model or None,
                                "retry_policy": retry_policy,
                                "lease_id": str(next_lease.get("lease_id") or "").strip() or None,
                                "attempt_operation_id": next_operation_id,
                            },
                        )
                        durable_store.enqueue_outbox(
                            next_operation_id,
                            run_id,
                            kind="provider_turn_start",
                            node_id=node_id,
                            payload={
                                "node_id": node_id,
                                "attempt_count": next_attempt_count,
                                "classification": "non_idempotent_write",
                            },
                        )
                        retry_turn_result = self.start_turn(
                            profile,
                            thread_id=str(worker.get("thread_id") or ""),
                            text=str(execution.get("prompt_text") or ""),
                            attachments=[deepcopy(item) for item in list(execution.get("attachments") or []) if isinstance(item, dict)],
                            model=next_attempt_model or None,
                            effort=str(graph_node.get("reasoning_effort") or "").strip() or None,
                            permission_mode=str(graph_node.get("permission_mode") or "auto").strip() or "auto",
                            collaboration_mode=self._normalize_graph_worker_collaboration_mode(graph_node),
                            context_mode="no_context",
                            execution_policy=str(
                                node_states.get(node_id, {}).get("turn_execution_policy")
                                or self._graph_worker_turn_execution_policy(
                                    self._graph_worker_tool_policy(
                                        dict(graph_node.get("tools") or {}),
                                        node=graph_node,
                                        graph_policy=dict(graph.get("graph_policy") or {}),
                                        node_id=node_id,
                                        mcp_tool_policy_snapshot=deepcopy(
                                            dict(
                                                dict(dict(run_manifest.get("run_policy_snapshot") or {}).get("node_mcp_tool_policies") or {}).get(node_id)
                                                or {}
                                            )
                                        ),
                                    )
                                )
                            ),
                            token_budget=int(execution.get("token_budget") or 0) or None,
                            token_budget_objective=(
                                f"{str(graph.get('title') or graph_id).strip()} / "
                                f"{self._tasks._graph_node_label(graph, node_id)}"
                            ),
                            mcp_tool_policy_snapshot=deepcopy(
                                dict(
                                    dict(dict(run_manifest.get("run_policy_snapshot") or {}).get("node_mcp_tool_policies") or {}).get(node_id)
                                    or {}
                                )
                            ),
                            mcp_tool_policy_context={
                                "graph_id": graph_id,
                                "run_id": run_id,
                                "node_id": node_id,
                                "attempt_count": next_attempt_count,
                                "worker_thread_id": str(worker.get("thread_id") or "").strip() or None,
                            },
                            transition_context={
                                "trigger": "graph_retry",
                                "failure_notice": deepcopy(dict(retry_next_attempt.get("failure_notice") or {})),
                                "graph_run_id": run_id,
                                "graph_node_id": node_id,
                                "attempt_count": next_attempt_count,
                                "retry_delay_seconds": float(retry_next_attempt.get("delay_seconds") or 0.0),
                                "retry_policy": "graph_live_retry",
                            },
                        )
                        retry_execution_thread_id = str(retry_turn_result.get("thread_id") or worker.get("thread_id") or "").strip()
                        retry_turn_id = str(dict(retry_turn_result.get("turn") or {}).get("id") or "").strip()
                        if not retry_execution_thread_id or not retry_turn_id:
                            raise RuntimeError("Task-graph retry turn start did not return an execution thread and turn id.")
                        durable_store.record_external_operation(
                            next_operation_id,
                            run_id,
                            kind="provider_turn_start",
                            classification="non_idempotent_write",
                            status="accepted",
                            external_handle=f"{retry_execution_thread_id}:{retry_turn_id}",
                            payload={
                                "node_id": node_id,
                                "attempt_count": next_attempt_count,
                                "worker_thread_id": str(worker.get("thread_id") or "") or None,
                                "execution_thread_id": retry_execution_thread_id,
                                "turn_id": retry_turn_id,
                            },
                        )
                        durable_store.update_outbox_status(
                            next_operation_id,
                            status="accepted",
                            payload={
                                "node_id": node_id,
                                "attempt_count": next_attempt_count,
                                "worker_thread_id": str(worker.get("thread_id") or "") or None,
                                "execution_thread_id": retry_execution_thread_id,
                                "turn_id": retry_turn_id,
                            },
                        )
                        node_states[node_id].update(
                            {
                                "status": "running",
                                "outcome": "pending",
                                "attempt_count": next_attempt_count,
                                "started_at": next_started_at,
                                "updated_at": next_started_at,
                                "provider_id": attempt_provider_id or None,
                                "model_id": next_attempt_model or None,
                                "execution_thread_id": retry_execution_thread_id,
                                "turn_id": retry_turn_id,
                                "attempt_operation_id": next_operation_id,
                                "lease_id": str(next_lease.get("lease_id") or "").strip() or None,
                            }
                        )
                        event_refs.append(
                            {
                                "event_id": f"{run_id}-{node_id}-attempt-{next_attempt_count}-started",
                                "run_id": run_id,
                                "task_id": graph["task_id"],
                                "trace_id": f"trace-{run_id}",
                                "event_type": "node_started",
                                "created_at": next_started_at,
                                "summary": (
                                    f"{self._tasks._graph_node_label(graph, node_id)} retry attempt {next_attempt_count} started"
                                    + (f" with fallback model {next_attempt_model}." if next_attempt_model != attempt_model else ".")
                                ),
                                "node_id": node_id,
                                "parallel_group_id": group_id,
                                "worker_thread_id": str(worker.get("thread_id") or "") or None,
                                "execution_thread_id": retry_execution_thread_id,
                            }
                        )
                        execution.update(
                            {
                                "dispatch_request": next_dispatch_request,
                                "dispatch_token": next_dispatch_token,
                                "execution_thread_id": retry_execution_thread_id,
                                "turn_id": retry_turn_id,
                                "started_monotonic": time.monotonic(),
                                "attempt_count": next_attempt_count,
                                "lease_id": str(next_lease.get("lease_id") or "").strip() or None,
                                "attempt_operation_id": next_operation_id,
                                "attempt_provider_id": attempt_provider_id or None,
                                "attempt_model": next_attempt_model or None,
                            }
                        )
                        live_run_ref = self._graph_live_run_snapshot(
                            run_ref=live_run_ref,
                            node_states=node_states,
                            event_refs=event_refs,
                            artifact_refs=run_artifact_refs,
                            policy_snapshot=run_manifest["run_policy_snapshot"],
                            status="running",
                        )
                        self._write_graph_live_run_manifest_snapshot(
                            run_manifest_path=run_manifest_path,
                            run_manifest=run_manifest,
                            node_states=node_states,
                            artifact_refs=run_artifact_refs,
                            event_refs=event_refs,
                            status="running",
                            updated_at=str(live_run_ref.get("updated_at") or ""),
                        )
                    if worker_output is None:
                        active_node_id = None
                        continue
                    binding = dict(worker_output.get("worker_binding") or {})
                    for handoff in list(binding.get("downstream_handoffs") or []):
                        if not isinstance(handoff, dict):
                            continue
                        target_node_id = str(handoff.get("to_node_id") or "").strip()
                        if not target_node_id:
                            continue
                        envelope = dict(handoff.get("agent_envelope") or {})
                        metadata = dict(envelope.get("metadata") or {})
                        delivery = dict(envelope.get("delivery") or {})
                        envelope_id = str(envelope.get("envelope_id") or "").strip() or f"{node_id}-{target_node_id}"
                        self._graph_live_append_unique_event(
                            event_refs,
                            {
                                "event_id": f"{run_id}-{envelope_id}-created",
                                "run_id": run_id,
                                "task_id": graph["task_id"],
                                "trace_id": f"trace-{run_id}",
                                "event_type": "handoff_created",
                                "created_at": finished_at,
                                "summary": f"Structured handoff from {self._tasks._graph_node_label(graph, node_id)} to {self._tasks._graph_node_label(graph, target_node_id)} was persisted.",
                                "node_id": node_id,
                                "parallel_group_id": group_id,
                                "payload": {
                                    "envelope_id": envelope_id,
                                    "message_id": str(envelope.get("message_id") or "").strip() or None,
                                    "delivery_idempotency_key": str(delivery.get("idempotency_key") or "").strip() or None,
                                    "correlation_id": str(metadata.get("correlation_id") or "").strip() or None,
                                    "causation_id": str(metadata.get("causation_id") or "").strip() or None,
                                    "source_node_id": str(metadata.get("source_node_id") or "").strip() or node_id,
                                    "target_node_id": str(metadata.get("target_node_id") or "").strip() or target_node_id,
                                },
                            },
                        )
                        incoming_handoffs.setdefault(target_node_id, []).append(
                            {
                                "source_node_id": node_id,
                                "source_label": self._tasks._graph_node_label(graph, node_id),
                                "output_summary": dict(binding.get("output_summary") or {}),
                                "handoff": deepcopy(handoff),
                            }
                        )
                    run_artifact_refs = self._tasks._merge_graph_worker_artifact_refs(
                        run_artifact_refs,
                        [dict(item) for item in list(binding.get("artifact_refs") or []) if isinstance(item, dict)],
                    )
                    event_refs.append(
                        {
                            "event_id": f"{run_id}-{node_id}-{node_status}",
                            "run_id": run_id,
                            "task_id": graph["task_id"],
                            "trace_id": f"trace-{run_id}",
                            "event_type": (
                                "node_completed"
                                if node_status == "completed"
                                else (
                                    "node_cancelled"
                                    if node_status == "cancelled"
                                    else ("node_blocked" if node_status == "needs_review" or outcome == "needs_review" else "node_failed")
                                )
                            ),
                            "created_at": finished_at,
                            "summary": summary,
                            "node_id": node_id,
                            "parallel_group_id": group_id,
                        }
                    )
                    current_live_ref = dict(worker_output.get("run_ref") or self._tasks.graph_run_ref(run_id) or live_run_ref)
                    live_run_ref = self._graph_live_run_snapshot(
                        run_ref=current_live_ref,
                        node_states=node_states,
                        event_refs=event_refs,
                        artifact_refs=run_artifact_refs,
                        policy_snapshot=run_manifest["run_policy_snapshot"],
                        status="running",
                        approval_state=approval_state,
                    )
                    self._write_graph_live_run_manifest_snapshot(
                        run_manifest_path=run_manifest_path,
                        run_manifest=run_manifest,
                        node_states=node_states,
                        artifact_refs=run_artifact_refs,
                        event_refs=event_refs,
                        status="running",
                        updated_at=str(live_run_ref.get("updated_at") or ""),
                        approval_state=approval_state,
                    )
                    active_node_id = None

            approval_pending = str(approval_state.get("status") or "").strip() == "pending"
            unresolved_nodes = [
                node_id
                for node_id in compiled_nodes
                if str(dict(node_states.get(node_id) or {}).get("status") or "").strip()
                not in {"completed", "failed", "cancelled", "needs_review", "waiting_on_approval"}
            ]
            current_durable_run = durable_store.load_run(run_id, include_events=False)
            cancellation_requested = self._graph_live_cancellation_requested(current_durable_run)
            if not approval_pending:
                for node_id in unresolved_nodes:
                    unresolved_status = "cancelled" if cancellation_requested else "blocked"
                    unresolved_summary = (
                        f"{self._tasks._graph_node_label(graph, node_id)} was cancelled before a later provider dispatch."
                        if cancellation_requested
                        else f"{self._tasks._graph_node_label(graph, node_id)} remained blocked because upstream dependencies did not produce a runnable handoff."
                    )
                    node_states[node_id].update(
                        {
                            "status": unresolved_status,
                            "outcome": unresolved_status,
                            "updated_at": now_iso(),
                        }
                    )
                    event_refs.append(
                        {
                            "event_id": f"{run_id}-{node_id}-{unresolved_status}-unstarted",
                            "run_id": run_id,
                            "task_id": graph["task_id"],
                            "trace_id": f"trace-{run_id}",
                            "event_type": "node_cancelled" if unresolved_status == "cancelled" else "node_blocked",
                            "created_at": str(node_states[node_id].get("updated_at") or now_iso()),
                            "summary": unresolved_summary,
                            "node_id": node_id,
                        }
                    )

            final_status = self._tasks._compiled_fixture_run_status(
                node_states=node_states,
                approval_state=approval_state,
            )
            final_updated_at = max(
                [created_at, *[str(dict(state).get("updated_at") or created_at) for state in node_states.values() if isinstance(state, dict)]]
            )
            if cancellation_requested:
                existing_cancellation = dict(self._graph_live_cancellation_record(current_durable_run) or {})
                live_run_ref = {
                    **dict(live_run_ref or {}),
                    "cancellation": {
                        **existing_cancellation,
                        "status": "completed",
                        "resolved_at": final_updated_at,
                        "final_run_status": final_status,
                        "resolution": (
                            "run_cancelled"
                            if final_status == "cancelled"
                            else ("late_result_suppressed" if final_status == "completed" else f"run_{final_status}")
                        ),
                    },
                }
            summary_payload = {
                "schema_version": "astrabridge-task-graph-live-run-summary-v1",
                "run_id": run_id,
                "graph_id": graph["graph_id"],
                "task_id": graph["task_id"],
                "created_at": created_at,
                "updated_at": final_updated_at,
                "run_status": final_status,
                "node_results": [
                    {
                        "node_id": node_id,
                        "label": self._tasks._graph_node_label(graph, node_id),
                        "status": str(state.get("status") or ""),
                        "outcome": str(state.get("outcome") or ""),
                    }
                    for node_id, state in node_states.items()
                ],
                "artifact_paths": {
                    "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                    "report_md": report_md_path.relative_to(workspace_root).as_posix(),
                    "compiled_plan_json": compiled_plan_path.relative_to(workspace_root).as_posix(),
                    "run_manifest_json": run_manifest_path.relative_to(workspace_root).as_posix(),
                },
            }
            write_json(summary_json_path, summary_payload)
            report_md_path.write_text(self._graph_live_run_report_markdown(summary_payload), encoding="utf-8")
            run_artifact_refs = self._tasks._merge_graph_worker_artifact_refs(
                run_artifact_refs,
                [
                    {
                        "artifact_id": f"{run_id}-summary-json",
                        "artifact_kind": "structured_json",
                        "path": summary_json_path.relative_to(workspace_root).as_posix(),
                        "status": "ready",
                    },
                    {
                        "artifact_id": f"{run_id}-report-md",
                        "artifact_kind": "run_summary",
                        "path": report_md_path.relative_to(workspace_root).as_posix(),
                        "status": "ready",
                    },
                ],
            )
            if final_status != "paused_for_review":
                event_refs.append(
                    {
                        "event_id": f"{run_id}-terminal",
                        "run_id": run_id,
                        "task_id": graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": (
                            "run_completed"
                            if final_status == "completed"
                            else ("run_cancelled" if final_status == "cancelled" else "run_failed")
                        ),
                        "created_at": final_updated_at,
                        "summary": f"{graph['title']} live task-graph run finished with status {final_status}.",
                    }
                )
            self._write_graph_live_run_manifest_snapshot(
                run_manifest_path=run_manifest_path,
                run_manifest=run_manifest,
                node_states=node_states,
                artifact_refs=run_artifact_refs,
                event_refs=event_refs,
                status=final_status,
                updated_at=final_updated_at,
                approval_state=approval_state,
            )
            live_run_ref = self._graph_live_run_snapshot(
                run_ref=live_run_ref,
                node_states=node_states,
                event_refs=event_refs,
                artifact_refs=run_artifact_refs,
                policy_snapshot=run_manifest["run_policy_snapshot"],
                status=final_status,
                approval_state=approval_state,
            )
            return {
                "schema_version": "astrabridge-task-graph-live-run-v1",
                "live_run": {
                    "run_id": run_id,
                    "run_status": final_status,
                    "run_ref": live_run_ref,
                    "artifact_paths": summary_payload["artifact_paths"],
                },
                "graph": graph,
                "task": self._tasks.task_view(self._tasks.current_task(), compact_graph_runs=True),
            }
        except _GraphDurablePause:
            raise
        except Exception as exc:
            reconciliation_records = self._reconcile_graph_live_started_turns(
                graph=graph,
                run_id=run_id,
                started_executions=started_executions,
                settled_execution_keys=settled_execution_keys,
                node_states=node_states,
                event_refs=event_refs,
                artifact_refs=run_artifact_refs,
            )
            failed_run = self._finalize_graph_live_run_failure(
                exc=exc,
                graph=graph,
                run_id=run_id,
                workspace_root=workspace_root,
                artifact_root=artifact_root,
                summary_json_path=summary_json_path,
                report_md_path=report_md_path,
                run_manifest_path=run_manifest_path,
                run_manifest=run_manifest,
                live_run_ref=live_run_ref,
                node_states=node_states,
                event_refs=event_refs,
                artifact_refs=run_artifact_refs,
                active_node_id=active_node_id,
                reconciliation_records=reconciliation_records,
            )
            try:
                setattr(
                    exc,
                    "public_payload",
                    {
                        "live_run": {
                            "run_id": run_id,
                            "run_status": str(
                                dict(failed_run.get("run_ref") or {}).get("status") or "failed"
                            ),
                            "run_ref": dict(failed_run.get("run_ref") or {}),
                            "artifact_paths": dict(failed_run.get("artifact_paths") or {}),
                        },
                        "graph": graph,
                        "task": self._tasks.task_view(
                            self._tasks.current_task(),
                            compact_graph_runs=True,
                        ),
                    },
                )
            except Exception:
                pass
            raise
        finally:
            self._graph_dispatch_control.clear_run(run_id)
            restore_thread_id = original_visible_thread_id or parent_thread_id
            if restore_thread_id:
                try:
                    self._tasks.restore_active_provider_thread(restore_thread_id)
                except Exception:
                    pass

    def _resolve_graph_worker_profile(self, node: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(node.get("provider_id") or "").strip()
        if not provider_id:
            raise ValueError(f"Graph node {str(node.get('node_id') or 'unknown')} is missing a provider.")
        return self._profiles.resolve_runtime_profile(provider_id)

    @staticmethod
    def _graph_live_run_token_limit(run_budget: dict[str, Any]) -> int | None:
        limits = dict(run_budget.get("limits") or {}) if isinstance(run_budget.get("limits"), dict) else {}
        raw_value = limits.get(
            "total_tokens",
            limits.get("max_total_tokens", run_budget.get("max_total_tokens", run_budget.get("total_tokens"))),
        )
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @staticmethod
    def _graph_live_retry_policy(
        *,
        compiled_node: dict[str, Any],
        graph_node: dict[str, Any],
    ) -> dict[str, Any]:
        raw = dict(dict(compiled_node.get("execution") or {}).get("retry_policy") or {})
        graph_raw = dict(dict(graph_node.get("execution_policy") or {}).get("retry_policy") or {})
        if graph_raw:
            raw = {**raw, **graph_raw}

        def _int(value: Any, default: int, *, minimum: int = 0) -> int:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                parsed = default
            return parsed if parsed >= minimum else default

        max_attempts = _int(raw.get("max_attempts"), 1, minimum=1)
        base_delay_value = raw["base_delay_ms"] if "base_delay_ms" in raw else raw.get("backoff_ms")
        base_delay_ms = _int(base_delay_value, 250, minimum=0)
        max_delay_value = raw["max_delay_ms"] if "max_delay_ms" in raw else raw.get("cap_delay_ms")
        max_delay_ms = _int(max_delay_value, max(base_delay_ms, 5000), minimum=base_delay_ms)
        jitter_value = raw["jitter_ms"] if "jitter_ms" in raw else min(250, max_delay_ms)
        jitter_ms = _int(jitter_value, min(250, max_delay_ms), minimum=0)
        return {
            "max_attempts": max_attempts,
            "base_delay_ms": base_delay_ms,
            "max_delay_ms": max_delay_ms,
            "jitter_ms": jitter_ms,
            "allow_model_fallback": bool(raw.get("allow_model_fallback", True)),
            "raw": raw,
        }

    @staticmethod
    def _graph_live_failure_notice(
        raw_message: str,
        *,
        provider_id: str,
        model_id: str,
    ) -> dict[str, Any]:
        return classify_runtime_failure(
            raw_message,
            current_provider=provider_id,
            current_model=model_id,
        ).to_payload()

    @staticmethod
    def _graph_live_retry_delay_seconds(
        *,
        run_id: str,
        node_id: str,
        attempt_count: int,
        retry_policy: dict[str, Any],
        failure_notice: dict[str, Any],
        raw_message: str,
    ) -> float:
        message = " ".join(
            part.strip()
            for part in (
                str(raw_message or ""),
                str(failure_notice.get("message") or ""),
            )
            if str(part or "").strip()
        )
        retry_after_match = re.search(r"retry-after[^0-9]*([0-9]+(?:\.[0-9]+)?)", message, re.IGNORECASE)
        if retry_after_match:
            try:
                return max(0.0, float(retry_after_match.group(1)))
            except (TypeError, ValueError):
                pass
        base_delay_ms = int(retry_policy.get("base_delay_ms") or 0)
        max_delay_ms = max(base_delay_ms, int(retry_policy.get("max_delay_ms") or 0))
        jitter_ms = max(0, int(retry_policy.get("jitter_ms") or 0))
        exponential_ms = base_delay_ms * max(1, 2 ** max(0, attempt_count - 1))
        capped_ms = min(exponential_ms, max_delay_ms or exponential_ms)
        if jitter_ms > 0:
            seed = f"{run_id}:{node_id}:{attempt_count}"
            jitter_seed = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)
            capped_ms += jitter_seed % (jitter_ms + 1)
        return max(0.0, capped_ms / 1000.0)

    @staticmethod
    def _graph_live_next_attempt_model(
        *,
        current_model: str,
        retry_policy: dict[str, Any],
        failure_notice: dict[str, Any],
    ) -> str:
        if not bool(retry_policy.get("allow_model_fallback")):
            return current_model
        fallback_models = [
            str(item).strip()
            for item in list(failure_notice.get("fallback_models") or [])
            if str(item or "").strip()
        ]
        for candidate in fallback_models:
            if candidate != current_model:
                return candidate
        return current_model

    @staticmethod
    def _graph_live_cancellation_record(run: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(run, dict):
            return {}
        value = run.get("cancellation")
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _graph_live_cancellation_requested(run: dict[str, Any] | None) -> bool:
        cancellation = RuntimeService._graph_live_cancellation_record(run)
        if not cancellation:
            return False
        status = str(cancellation.get("status") or "").strip().lower()
        if status in {"completed", "already_terminal", "rejected", "ignored"}:
            return False
        if status in {"requested", "interrupting", "timed_out"}:
            return True
        return bool(cancellation.get("requested_at")) and not bool(cancellation.get("resolved_at"))

    def _prepare_graph_live_run_nodes(
        self,
        *,
        task: dict[str, Any],
        graph: dict[str, Any],
        compiled_nodes: dict[str, dict[str, Any]],
        node_map: dict[str, dict[str, Any]],
        run_token_limit: int,
    ) -> dict[str, dict[str, Any]]:
        del task
        ordered_node_ids = sorted(compiled_nodes)
        if not ordered_node_ids:
            raise ValueError("Task graph live run has no executable nodes.")
        if run_token_limit < len(ordered_node_ids):
            raise ValueError(
                "Task graph token budget must allocate at least one token to every executable node."
            )
        base_allocation, remainder = divmod(run_token_limit, len(ordered_node_ids))
        prepared: dict[str, dict[str, Any]] = {}
        for index, node_id in enumerate(ordered_node_ids):
            graph_node = dict(node_map.get(node_id) or {})
            if not graph_node:
                raise ValueError(f"Compiled graph node {node_id} is missing from the graph definition.")
            compiled_node = dict(compiled_nodes.get(node_id) or {})
            compiler_executor_id = str(
                compiled_node.get("compiler_executor_id")
                or graph_node.get("compiler_executor_id")
                or ""
            ).strip() or "agent_lane"
            provider_id = str(graph_node.get("provider_id") or "").strip()
            model_id = str(graph_node.get("model_id") or "").strip()
            prompt_template = str(graph_node.get("human_summary_template") or "").strip()
            execution_policy = dict(graph_node.get("execution_policy") or {})
            timeout_ms = execution_policy.get("timeout_ms")
            try:
                timeout_seconds = max(5.0, int(timeout_ms) / 1000.0) if timeout_ms is not None else 210.0
            except (TypeError, ValueError):
                timeout_seconds = 210.0
            if compiler_executor_id == "agent_lane":
                if not provider_id:
                    raise ValueError(f"Graph node {node_id} is missing an explicit provider.")
                if not model_id:
                    raise ValueError(f"Graph node {node_id} is missing an explicit model.")
                if not prompt_template:
                    raise ValueError(f"Graph node {node_id} is missing an explicit live-run prompt.")
                if not bool(execution_policy.get("allow_provider_calls")):
                    raise ValueError(f"Graph node {node_id} does not allow provider calls.")
                profile = self._resolve_graph_worker_profile(graph_node)
            else:
                profile = {
                    "provider_id": provider_id or "local_only",
                    "model": model_id or compiler_executor_id,
                }
            prepared[node_id] = {
                "node_id": node_id,
                "graph_node": graph_node,
                "profile": profile,
                "token_budget": base_allocation + (1 if index < remainder else 0),
                "timeout_seconds": timeout_seconds,
                "retry_policy": self._graph_live_retry_policy(compiled_node=compiled_node, graph_node=graph_node),
            }
        allocated = sum(int(item["token_budget"]) for item in prepared.values())
        if allocated != run_token_limit:
            raise RuntimeError("Task graph token-budget allocation did not reconcile to the run limit.")
        return prepared

    def _graph_live_local_worker_stub(
        self,
        *,
        graph: dict[str, Any],
        run_id: str,
        node_id: str,
        graph_node: dict[str, Any],
        parent_thread_id: str,
        existing_state: dict[str, Any],
    ) -> dict[str, Any]:
        del graph
        existing_thread_id = str(
            existing_state.get("worker_thread_id")
            or existing_state.get("execution_thread_id")
            or ""
        ).strip()
        worker_thread_id = existing_thread_id or (
            "local-"
            + hashlib.sha256(f"{run_id}:{node_id}".encode("utf-8")).hexdigest()[:24]
        )
        execution_policy = dict(graph_node.get("execution_policy") or {})
        return {
            "thread_id": worker_thread_id,
            "parent_thread_id": str(existing_state.get("parent_thread_id") or parent_thread_id or "").strip() or None,
            "spawn_mode": str(existing_state.get("spawn_mode") or execution_policy.get("spawn_mode") or "inline_lane").strip() or "inline_lane",
            "worker_origin": str(existing_state.get("worker_origin") or "deterministic_local").strip() or "deterministic_local",
            "agent_role": str(existing_state.get("agent_role") or graph_node.get("kind") or "custom").strip() or "custom",
            "agent_nickname": str(existing_state.get("agent_nickname") or graph_node.get("label") or node_id).strip() or node_id,
            "settings": {
                "execution_backend": str(existing_state.get("execution_backend") or graph_node.get("execution_backend") or "local_only").strip() or "local_only",
            },
        }

    @staticmethod
    def _graph_live_node_type_config(node: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(dict(dict(node.get("ui_hints") or {}).get("node_type_config") or {}))

    def _graph_live_collect_typed_inputs(
        self,
        incoming_handoffs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        typed_inputs: dict[str, Any] = {}
        for item in incoming_handoffs:
            envelope = dict(dict(item).get("agent_envelope") or {})
            metadata = dict(envelope.get("metadata") or {})
            projection = dict(metadata.get("typed_handoff") or {})
            for port_id, value in dict(projection.get("inputs") or {}).items():
                clean_port_id = str(port_id or "").strip()
                if not clean_port_id:
                    continue
                if clean_port_id not in typed_inputs:
                    typed_inputs[clean_port_id] = deepcopy(value)
                elif typed_inputs[clean_port_id] != value:
                    raise GraphContractValidationError(
                        f"Incoming handoffs disagreed on target input port {clean_port_id}; local execution is blocked until the graph is corrected."
                    )
        return typed_inputs

    def _graph_live_first_port_id(
        self,
        node: dict[str, Any],
        *,
        direction: str,
        preferred: str,
    ) -> str:
        port_map = self._tasks._graph_node_port_map(node, direction=direction)
        if preferred in port_map:
            return preferred
        for port_id in port_map:
            clean_port_id = str(port_id or "").strip()
            if clean_port_id:
                return clean_port_id
        return preferred

    def _graph_live_resolve_workspace_artifact_uri(
        self,
        uri: str,
        *,
        node_id: str,
    ) -> tuple[Path, str]:
        clean_uri = str(uri or "").strip()
        if clean_uri.startswith("workspace://"):
            relative_path = clean_uri.removeprefix("workspace://").lstrip("/")
        elif clean_uri.startswith(("PRIVATE/", ".astrabridge/")):
            relative_path = clean_uri
        else:
            raise GraphContractValidationError(
                f"{node_id} references unsupported artifact URI `{clean_uri}`. Only workspace:// and workspace-relative paths are allowed."
            )
        resolved = resolve_under(self._projects.require_workspace_root(), relative_path)
        if resolved is None or not resolved.exists() or not resolved.is_file():
            raise GraphContractValidationError(
                f"{node_id} references missing workspace artifact `{clean_uri}`."
            )
        return resolved, relative_path.replace("\\", "/")

    @staticmethod
    def _graph_live_file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _graph_live_protocol_artifact_ref(
        self,
        *,
        run_id: str,
        graph: dict[str, Any],
        node_id: str,
        artifact_id: str,
        relative_path: str,
        media_type: str,
        digest_sha256: str,
    ) -> dict[str, Any]:
        payload = {
            "artifact_id": artifact_id,
            "artifact_uri": f"workspace://{relative_path}",
            "media_type": media_type,
            "status": "ready",
            "lineage": {
                "task_id": str(graph.get("task_id") or "").strip(),
                "run_id": str(run_id or "").strip(),
                "source_node_id": str(node_id or "").strip(),
            },
            "metadata": {
                "relative_path": relative_path,
                "digest_sha256": digest_sha256,
            },
        }
        validate_protocol_payload("ArtifactRef", payload)
        return payload

    def _graph_live_load_structured_artifact_ref(
        self,
        artifact_ref: dict[str, Any],
        *,
        node_id: str,
    ) -> dict[str, Any]:
        normalized_ref = dict(artifact_ref or {})
        try:
            validate_protocol_payload("ArtifactRef", normalized_ref)
        except Exception as exc:
            uri = str(normalized_ref.get("artifact_uri") or "").strip()
            if not uri.startswith("workspace://"):
                raise GraphContractValidationError(
                    f"{node_id} received an invalid ArtifactRef payload: {exc}"
                ) from exc
            relative_path = uri.removeprefix("workspace://").lstrip("/")
            normalized_ref = {
                "artifact_id": str(normalized_ref.get("artifact_id") or f"{node_id}-workspace-artifact").strip() or f"{node_id}-workspace-artifact",
                "artifact_uri": uri,
                "media_type": str(normalized_ref.get("media_type") or "application/json").strip() or "application/json",
                "status": str(normalized_ref.get("status") or "ready").strip() or "ready",
                "lineage": {
                    "task_id": str((self._tasks.current_task() or {}).get("task_id") or "task-runtime").strip() or "task-runtime",
                    "run_id": str(dict(normalized_ref.get("lineage") or {}).get("run_id") or f"runtime-{node_id}").strip() or f"runtime-{node_id}",
                    "source_node_id": str(dict(normalized_ref.get("lineage") or {}).get("source_node_id") or node_id).strip() or node_id,
                },
                "metadata": {
                    **deepcopy(dict(normalized_ref.get("metadata") or {})),
                    "relative_path": relative_path,
                    **(
                        {"digest_sha256": str(normalized_ref.get("digest_sha256") or "").strip()}
                        if str(normalized_ref.get("digest_sha256") or "").strip()
                        else {}
                    ),
                },
            }
            validate_protocol_payload("ArtifactRef", normalized_ref)
        metadata = dict(normalized_ref.get("metadata") or {})
        relative_path = str(metadata.get("relative_path") or "").strip()
        if not relative_path:
            uri = str(normalized_ref.get("artifact_uri") or "").strip()
            if uri.startswith("workspace://"):
                relative_path = uri.removeprefix("workspace://").lstrip("/")
        resolved = resolve_under(self._projects.require_workspace_root(), relative_path)
        if resolved is None or not resolved.exists() or not resolved.is_file():
            raise GraphContractValidationError(
                f"{node_id} references missing artifact payload `{relative_path or normalized_ref.get('artifact_uri')}`."
            )
        expected_digest = str(metadata.get("digest_sha256") or "").strip()
        actual_digest = self._graph_live_file_sha256(resolved)
        if expected_digest and expected_digest != actual_digest:
            raise GraphContractValidationError(
                f"{node_id} rejected artifact `{relative_path}` because digest verification failed."
            )
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except Exception as exc:
            raise GraphContractValidationError(
                f"{node_id} could not decode structured artifact `{relative_path}` as JSON."
            ) from exc
        return {
            "payload": payload,
            "relative_path": relative_path,
            "resolved_path": resolved,
            "digest_sha256": actual_digest,
        }

    def _graph_live_execute_local_executor(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        graph: dict[str, Any],
        graph_id: str,
        run_id: str,
        group_id: str,
        execution: dict[str, Any],
        compiler_executor_id: str,
        run_manifest: dict[str, Any],
        run_manifest_path: Path,
        live_run_ref: dict[str, Any],
        run_artifact_refs: list[dict[str, Any]],
        incoming_handoffs: dict[str, list[dict[str, Any]]],
        node_states: dict[str, dict[str, Any]],
        event_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        del task
        durable_store = self._tasks.durable_run_store()
        node_id = str(execution.get("node_id") or "").strip()
        graph_node = dict(execution.get("graph_node") or {})
        worker = dict(execution.get("worker") or {})
        compiled_node = dict(execution.get("compiled_node") or {})
        existing_state = dict(execution.get("existing_node_state") or {})
        attempt_count = max(1, int(execution.get("attempt_count") or existing_state.get("attempt_count") or 1))
        started_at = now_iso()
        finished_at = started_at
        started_monotonic = time.monotonic()
        label = self._tasks._graph_node_label(graph, node_id)
        worker_thread_id = str(worker.get("thread_id") or "").strip()
        node_mcp_tool_policy_snapshot = deepcopy(
            dict(
                dict(dict(run_manifest.get("run_policy_snapshot") or {}).get("node_mcp_tool_policies") or {}).get(node_id)
                or dict(dict(compiled_node.get("tool_policy") or {}).get("mcp_tool_policy") or {})
            )
        )
        typed_inputs = self._graph_live_collect_typed_inputs(
            list(execution.get("incoming_handoffs") or [])
        )
        node_type_config = self._graph_live_node_type_config(graph_node)
        output_port_id = self._graph_live_first_port_id(
            graph_node,
            direction="outputs",
            preferred=(
                "tool_result"
                if compiler_executor_id == "mcp_tool"
                else (
                    "resource_payload"
                    if compiler_executor_id == "mcp_resource"
                    else (
                        "route_decision"
                        if compiler_executor_id == "router_condition"
                        else (
                            "artifact_output"
                            if compiler_executor_id == "artifact_source"
                            else (
                                "artifact_record"
                                if compiler_executor_id == "artifact_sink"
                                else (
                                    "loop_result"
                                    if compiler_executor_id == "loop"
                                    else ("subgraph_result" if compiler_executor_id == "subgraph" else "machine_result")
                                )
                            )
                        )
                    )
                )
            ),
        )
        worker_artifact_root = (
            self._projects.require_workspace_root()
            / "PRIVATE"
            / "task-graph"
            / "workers"
            / run_id
            / node_id
        )
        worker_artifact_root.mkdir(parents=True, exist_ok=True)
        node_states[node_id].update(
            {
                "status": "running",
                "outcome": "pending",
                "attempt_count": attempt_count,
                "started_at": started_at,
                "updated_at": started_at,
                "worker_thread_id": worker_thread_id or None,
                "parent_thread_id": str(worker.get("parent_thread_id") or "").strip() or None,
                "spawn_mode": str(worker.get("spawn_mode") or "").strip() or None,
                "worker_origin": str(worker.get("worker_origin") or "").strip() or "deterministic_local",
                "agent_role": str(worker.get("agent_role") or graph_node.get("kind") or "").strip() or None,
                "agent_nickname": str(worker.get("agent_nickname") or graph_node.get("label") or "").strip() or None,
                "execution_backend": str(dict(worker.get("settings") or {}).get("execution_backend") or "local_only").strip() or "local_only",
            }
        )
        self._tasks.record_graph_worker(
            {
                "graph_id": graph_id,
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "parent_thread_id": str(worker.get("parent_thread_id") or "").strip(),
                "spawn_mode": str(worker.get("spawn_mode") or "").strip(),
                "worker_origin": str(worker.get("worker_origin") or "deterministic_local").strip() or "deterministic_local",
                "agent_role": str(worker.get("agent_role") or graph_node.get("kind") or "").strip() or "custom",
                "agent_nickname": str(worker.get("agent_nickname") or graph_node.get("label") or node_id).strip() or node_id,
                "status": "ready",
                "execution_backend": str(dict(worker.get("settings") or {}).get("execution_backend") or "local_only").strip() or "local_only",
                "runtime_contract": {
                    "execution_backend": str(dict(worker.get("settings") or {}).get("execution_backend") or "local_only").strip() or "local_only",
                    "spawn_mode": str(worker.get("spawn_mode") or "").strip() or "inline_lane",
                    "tool_policy": {
                        "approval_mode": "allow",
                        "allowed_tool_classes": [],
                        "supports_mcp": bool(node_mcp_tool_policy_snapshot),
                        "mcp_tool_policy": deepcopy(node_mcp_tool_policy_snapshot),
                    },
                },
                "created_at": started_at,
                "updated_at": started_at,
            },
            graph_definition=graph,
        )
        self._graph_live_append_unique_event(
            event_refs,
            {
                "event_id": f"{run_id}-{node_id}-attempt-{attempt_count}-started",
                "run_id": run_id,
                "task_id": graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": "node_started",
                "created_at": started_at,
                "summary": f"{label} local executor attempt {attempt_count} started.",
                "node_id": node_id,
                "parallel_group_id": group_id,
                "worker_thread_id": worker_thread_id or None,
            },
        )

        input_digest = self._stable_json_digest(typed_inputs)
        human_summary = ""
        machine_result: dict[str, Any] = {}
        typed_output_values: dict[str, Any] = {}
        next_action_hints: list[str] = []
        generated_artifact_refs: list[dict[str, Any]] = []
        selected_edge_ids: list[str] = []
        approval_state: dict[str, Any] | None = None
        node_status = "completed"
        outcome = "passed"
        tool_call_count = 0

        try:
            if compiler_executor_id == "mcp_tool":
                if not node_mcp_tool_policy_snapshot:
                    raise GraphContractValidationError(
                        f"{label} is missing a compiled MCP policy snapshot."
                    )
                server = str(node_type_config.get("server") or "").strip()
                tool_name = str(node_type_config.get("tool") or "").strip()
                if not server or not tool_name:
                    raise GraphContractValidationError(
                        f"{label} is missing node_type_config.server/tool."
                    )
                task_context = ""
                for value in typed_inputs.values():
                    if isinstance(value, str) and str(value).strip():
                        task_context = str(value).strip()
                        break
                    if isinstance(value, (dict, list)) and value:
                        task_context = json.dumps(value, ensure_ascii=False)
                        break
                if not task_context:
                    raise GraphContractValidationError(
                        f"{label} requires a non-empty text task_context input."
                    )
                broker_result = self._mcp_broker.invoke_tool(
                    server,
                    tool_name,
                    {
                        **deepcopy(dict(node_type_config.get("arguments") or {})),
                        "task_context": task_context,
                    },
                    caller="task_graph_live_executor",
                    operation_id=self._graph_live_operation_id(
                        run_id=run_id,
                        node_id=node_id,
                        attempt=attempt_count,
                        kind="mcp_tool_call",
                    ),
                    internal_meta={
                        "astrabridge_mcp_tool_policy": deepcopy(node_mcp_tool_policy_snapshot),
                        "astrabridge_mcp_policy_context": {
                            "graph_id": graph_id,
                            "run_id": run_id,
                            "node_id": node_id,
                            "attempt_count": attempt_count,
                            "worker_thread_id": worker_thread_id or None,
                        },
                    },
                )
                tool_call_count = 1
                raw_tool_result = deepcopy(broker_result.get("result"))
                if isinstance(raw_tool_result, (dict, list)):
                    tool_result_value = deepcopy(raw_tool_result)
                else:
                    tool_result_value = {"value": raw_tool_result}
                tool_payload = {
                    "schema_version": "astrabridge-live-mcp-tool-result-v1",
                    "server": server,
                    "tool": tool_name,
                    "result": deepcopy(tool_result_value),
                    "mcp": deepcopy(dict(broker_result.get("mcp") or {})),
                    "input_digest": input_digest,
                }
                tool_payload_path = worker_artifact_root / "mcp-tool-result.json"
                write_json(tool_payload_path, tool_payload)
                tool_payload_rel = tool_payload_path.relative_to(self._projects.require_workspace_root()).as_posix()
                tool_digest = self._graph_live_file_sha256(tool_payload_path)
                protocol_ref = self._graph_live_protocol_artifact_ref(
                    run_id=run_id,
                    graph=graph,
                    node_id=node_id,
                    artifact_id=output_port_id,
                    relative_path=tool_payload_rel,
                    media_type="application/json",
                    digest_sha256=tool_digest,
                )
                typed_output_values[output_port_id] = deepcopy(tool_result_value)
                generated_artifact_refs.append(
                    {
                        "artifact_id": output_port_id,
                        "artifact_kind": "tool_result",
                        "path": tool_payload_rel,
                        "status": "ready",
                        "metadata": {"digest_sha256": tool_digest},
                    }
                )
                human_summary = f"MCP tool {tool_name} completed through {server}."
                machine_result = {
                    "status": "completed",
                    "executor": "mcp_tool",
                    "server": server,
                    "tool": tool_name,
                    "result": deepcopy(tool_result_value),
                    "artifact_uri": protocol_ref["artifact_uri"],
                    "input_digest": input_digest,
                    "output_digest": tool_digest,
                }
            elif compiler_executor_id == "mcp_resource":
                if not node_mcp_tool_policy_snapshot:
                    raise GraphContractValidationError(
                        f"{label} is missing a compiled MCP policy snapshot."
                    )
                server = str(node_type_config.get("server") or "").strip()
                resource_uri = str(node_type_config.get("resource") or "").strip()
                if not server or not resource_uri:
                    raise GraphContractValidationError(
                        f"{label} is missing node_type_config.server/resource."
                    )
                broker_result = self._mcp_broker.read_resource(
                    server,
                    resource_uri,
                    caller="task_graph_live_executor",
                    operation_id=self._graph_live_operation_id(
                        run_id=run_id,
                        node_id=node_id,
                        attempt=attempt_count,
                        kind="mcp_resource_read",
                    ),
                    internal_meta={
                        "astrabridge_mcp_tool_policy": deepcopy(node_mcp_tool_policy_snapshot),
                        "astrabridge_mcp_policy_context": {
                            "graph_id": graph_id,
                            "run_id": run_id,
                            "node_id": node_id,
                            "attempt_count": attempt_count,
                            "worker_thread_id": worker_thread_id or None,
                        },
                    },
                )
                tool_call_count = 1
                resource_payload = {
                    "server": server,
                    "resource": resource_uri,
                    "result": deepcopy(dict(broker_result.get("result") or {})),
                    "input_digest": input_digest,
                }
                resource_payload_path = worker_artifact_root / "mcp-resource-result.json"
                write_json(resource_payload_path, resource_payload)
                resource_payload_rel = resource_payload_path.relative_to(self._projects.require_workspace_root()).as_posix()
                generated_artifact_refs.append(
                    {
                        "artifact_id": "resource_payload",
                        "artifact_kind": "structured_json",
                        "path": resource_payload_rel,
                        "status": "ready",
                        "metadata": {"digest_sha256": self._graph_live_file_sha256(resource_payload_path)},
                    }
                )
                typed_output_values[output_port_id] = deepcopy(resource_payload)
                human_summary = f"MCP resource {resource_uri} loaded through {server}."
                machine_result = deepcopy(resource_payload)
            elif compiler_executor_id == "transform":
                transform_id = str(node_type_config.get("transform_id") or "identity").strip() or "identity"
                input_value = next(iter(typed_inputs.values()), {})
                if isinstance(input_value, dict) and str(input_value.get("artifact_uri") or "").strip():
                    loaded = self._graph_live_load_structured_artifact_ref(input_value, node_id=node_id)
                    input_payload = loaded["payload"]
                else:
                    input_payload = deepcopy(input_value)
                if transform_id in {"identity", "pass_through"}:
                    transformed = input_payload if isinstance(input_payload, (dict, list)) else {"value": input_payload}
                elif transform_id in {"tool_result_to_structured_json", "extract_tool_result", "unwrap_result"}:
                    if isinstance(input_payload, dict) and isinstance(input_payload.get("result"), (dict, list)):
                        transformed = deepcopy(input_payload.get("result"))
                    else:
                        transformed = input_payload if isinstance(input_payload, (dict, list)) else {"value": input_payload}
                else:
                    raise GraphContractValidationError(
                        f"{label} references unsupported transform_id `{transform_id}`."
                    )
                typed_output_values[output_port_id] = deepcopy(transformed)
                human_summary = f"Deterministic transform {transform_id} completed."
                machine_result = {
                    "status": "completed",
                    "executor": "transform",
                    "transform_id": transform_id,
                    "input_digest": input_digest,
                    "output_digest": self._stable_json_digest(transformed),
                    "result": deepcopy(transformed),
                }
            elif compiler_executor_id == "router_condition":
                condition = dict(node_type_config.get("condition") or {})
                input_payload = deepcopy(next(iter(typed_inputs.values()), {}))
                if not isinstance(input_payload, dict):
                    input_payload = {"value": input_payload}
                field = str(condition.get("field") or "").strip()
                actual_value: Any = deepcopy(input_payload)
                if field:
                    actual_value = deepcopy(input_payload)
                    for part in [segment for segment in field.split(".") if segment]:
                        if isinstance(actual_value, dict) and part in actual_value:
                            actual_value = deepcopy(actual_value[part])
                        else:
                            actual_value = None
                            break
                routes = dict(condition.get("routes") or {})
                if routes:
                    route_key = str(actual_value)
                    raw_selected = routes.get(route_key, routes.get("*"))
                    if isinstance(raw_selected, str):
                        selected_edge_ids = [raw_selected]
                    else:
                        selected_edge_ids = [
                            str(item).strip()
                            for item in list(raw_selected or [])
                            if str(item or "").strip()
                        ]
                else:
                    expected_value = condition.get("equals", condition.get("value"))
                    matched = actual_value == expected_value if ("equals" in condition or "value" in condition) else bool(actual_value)
                    raw_selected = (
                        condition.get("true_edge_ids")
                        if matched
                        else condition.get("false_edge_ids", condition.get("default_edge_ids"))
                    )
                    selected_edge_ids = [
                        str(item).strip()
                        for item in list(raw_selected or [])
                        if str(item or "").strip()
                    ]
                outgoing_edge_ids = {
                    str(item.get("edge_id") or "").strip()
                    for item in list(graph.get("edges") or [])
                    if isinstance(item, dict) and str(item.get("from_node_id") or "").strip() == node_id
                }
                invalid_edge_ids = sorted(set(selected_edge_ids).difference(outgoing_edge_ids))
                if invalid_edge_ids:
                    raise GraphContractValidationError(
                        f"{label} selected unknown outgoing edges: {', '.join(invalid_edge_ids)}."
                    )
                if not selected_edge_ids:
                    raise GraphContractValidationError(
                        f"{label} did not select any downstream edges."
                    )
                route_decision = {
                    "selected_edge_ids": list(selected_edge_ids),
                    "field": field or None,
                    "value": deepcopy(actual_value),
                    "input_digest": input_digest,
                }
                typed_output_values[output_port_id] = deepcopy(route_decision)
                human_summary = f"Router selected {len(selected_edge_ids)} downstream edge(s)."
                machine_result = deepcopy(route_decision)
            elif compiler_executor_id == "artifact_source":
                artifact_uri = str(node_type_config.get("artifact_uri") or "").strip()
                artifact_kind = str(node_type_config.get("artifact_kind") or "structured_json").strip() or "structured_json"
                if not artifact_uri:
                    raise GraphContractValidationError(
                        f"{label} is missing node_type_config.artifact_uri."
                    )
                resolved_path, relative_path = self._graph_live_resolve_workspace_artifact_uri(
                    artifact_uri,
                    node_id=node_id,
                )
                actual_digest = self._graph_live_file_sha256(resolved_path)
                expected_digest = str(node_type_config.get("digest_sha256") or node_type_config.get("expected_digest_sha256") or "").strip()
                if expected_digest and expected_digest != actual_digest:
                    raise GraphContractValidationError(
                        f"{label} rejected source artifact `{artifact_uri}` because the digest does not match the declared value."
                    )
                media_type = mimetypes.guess_type(resolved_path.name)[0] or "application/octet-stream"
                artifact_payload = {
                    "artifact_kind": artifact_kind,
                    "artifact_uri": f"workspace://{relative_path}",
                    "relative_path": relative_path,
                    "media_type": media_type,
                    "digest_sha256": actual_digest,
                    "size_bytes": int(resolved_path.stat().st_size),
                }
                typed_output_values[output_port_id] = deepcopy(artifact_payload)
                generated_artifact_refs.append(
                    {
                        "artifact_id": "artifact_source",
                        "artifact_kind": artifact_kind,
                        "path": relative_path,
                        "status": "ready",
                        "metadata": {"digest_sha256": actual_digest},
                    }
                )
                human_summary = f"Artifact source loaded {relative_path}."
                machine_result = deepcopy(artifact_payload)
            elif compiler_executor_id == "artifact_sink":
                sink_input = deepcopy(next(iter(typed_inputs.values()), {}))
                if not isinstance(sink_input, dict):
                    raise GraphContractValidationError(
                        f"{label} requires a structured_json artifact input."
                    )
                source_digest = None
                artifact_uri = str(sink_input.get("artifact_uri") or "").strip()
                if artifact_uri:
                    resolved_path, relative_path = self._graph_live_resolve_workspace_artifact_uri(
                        artifact_uri,
                        node_id=node_id,
                    )
                    actual_digest = self._graph_live_file_sha256(resolved_path)
                    expected_digest = str(sink_input.get("digest_sha256") or "").strip()
                    if expected_digest and expected_digest != actual_digest:
                        raise GraphContractValidationError(
                            f"{label} rejected upstream artifact `{relative_path}` because digest verification failed."
                        )
                    source_digest = actual_digest
                target_kind = str(node_type_config.get("target_kind") or "structured_json").strip() or "structured_json"
                sink_payload_path = worker_artifact_root / f"artifact-sink-{target_kind}.json"
                sink_record = {
                    "target_kind": target_kind,
                    "stored_path": sink_payload_path.relative_to(self._projects.require_workspace_root()).as_posix(),
                    "source_artifact_uri": artifact_uri or None,
                    "source_digest_sha256": source_digest,
                    "input_digest": input_digest,
                    "status": "ready",
                }
                write_json(
                    sink_payload_path,
                    {
                        "schema_version": "astrabridge-live-artifact-sink-v1",
                        "record": sink_record,
                        "source_payload": deepcopy(sink_input),
                    },
                )
                sink_payload_rel = sink_payload_path.relative_to(self._projects.require_workspace_root()).as_posix()
                sink_digest = self._graph_live_file_sha256(sink_payload_path)
                generated_artifact_refs.append(
                    {
                        "artifact_id": "artifact_record",
                        "artifact_kind": target_kind,
                        "path": sink_payload_rel,
                        "status": "ready",
                        "metadata": {"digest_sha256": sink_digest},
                    }
                )
                typed_output_values[output_port_id] = deepcopy(sink_record)
                human_summary = f"Artifact sink persisted {target_kind} output."
                machine_result = deepcopy(sink_record)
            elif compiler_executor_id == "loop":
                input_payload = deepcopy(next(iter(typed_inputs.values()), {}))
                if isinstance(input_payload, dict) and str(input_payload.get("artifact_uri") or "").strip():
                    loaded = self._graph_live_load_structured_artifact_ref(input_payload, node_id=node_id)
                    input_payload = loaded["payload"]
                if not isinstance(input_payload, dict):
                    raise GraphContractValidationError(
                        f"{label} requires a structured_json payload with an `items` array."
                    )
                raw_items = input_payload.get("items")
                if not isinstance(raw_items, list):
                    raise GraphContractValidationError(
                        f"{label} requires input.items to be an array for bounded live loop execution."
                    )
                max_iterations = max(1, int(node_type_config.get("max_iterations") or 1))
                timeout_ms = self._graph_live_effective_timeout_ms(graph_node=graph_node, compiled_node=compiled_node)
                processed_items: list[Any] = []
                stopped_reason = "input_exhausted"
                elapsed_timeout = False
                cancelled_during_loop = False
                for index, item in enumerate(raw_items):
                    if index >= max_iterations:
                        stopped_reason = "max_iterations_reached"
                        break
                    current_run = durable_store.load_run(run_id, include_events=False)
                    if self._graph_live_cancellation_requested(current_run):
                        cancelled_during_loop = True
                        stopped_reason = "cancel_requested"
                        break
                    if timeout_ms is not None:
                        elapsed_ms = int((time.monotonic() - started_monotonic) * 1000)
                        if elapsed_ms >= timeout_ms:
                            elapsed_timeout = True
                            stopped_reason = "timeout_reached"
                            break
                    processed_items.append(deepcopy(item))
                    if isinstance(item, dict) and bool(item.get("stop")):
                        stopped_reason = "stop_requested"
                        break
                checkpoint = {
                    "status": "cancelled" if cancelled_during_loop else ("timed_out" if elapsed_timeout else "completed"),
                    "iteration_count": len(processed_items),
                    "max_iterations": max_iterations,
                    "input_item_count": len(raw_items),
                    "remaining_item_count": max(0, len(raw_items) - len(processed_items)),
                    "stopped_reason": stopped_reason,
                    "timeout_ms": timeout_ms,
                }
                typed_output_values[output_port_id] = {
                    "items": deepcopy(processed_items),
                    "iteration_count": len(processed_items),
                    "max_iterations": max_iterations,
                    "remaining_item_count": max(0, len(raw_items) - len(processed_items)),
                    "stopped_reason": stopped_reason,
                    "checkpoint": deepcopy(checkpoint),
                }
                node_states[node_id]["loop_state"] = deepcopy(checkpoint)
                if cancelled_during_loop:
                    node_status = "cancelled"
                    outcome = "cancelled"
                    human_summary = ""
                    machine_result = {
                        "status": "cancelled",
                        "executor": "loop",
                        "checkpoint": deepcopy(checkpoint),
                    }
                elif elapsed_timeout:
                    node_status = "failed"
                    outcome = "timeout"
                    human_summary = ""
                    machine_result = {
                        "status": "timeout",
                        "executor": "loop",
                        "checkpoint": deepcopy(checkpoint),
                    }
                else:
                    loop_result = deepcopy(dict(typed_output_values.get(output_port_id) or {}))
                    human_summary = (
                        f"Loop completed {len(processed_items)} iteration(s) with stop reason {stopped_reason}."
                    )
                    machine_result = {
                        **loop_result,
                        "status": "completed",
                    }
            elif compiler_executor_id == "subgraph":
                graph_ref = str(node_type_config.get("graph_ref") or "").strip()
                child_graph = self._graph_live_resolve_subgraph_definition(
                    graph_ref=graph_ref,
                    current_graph_id=graph_id,
                    parent_context=self._graph_live_parent_context(payload),
                )
                child_orchestration_graph = (
                    child_graph
                    if child_graph.get("schema_registry") is not None
                    else self._tasks._orchestration_graph_for_task_graph(child_graph)
                )
                child_entry_node_ids = [
                    str(item).strip()
                    for item in list(dict(child_graph.get("graph_policy") or {}).get("entry_node_ids") or [])
                    if str(item or "").strip()
                ]
                if len(child_entry_node_ids) != 1:
                    raise GraphContractValidationError(
                        f"{label} currently requires exactly one child entry node for live subgraph execution."
                    )
                child_node_map = {
                    str(item.get("node_id") or "").strip(): dict(item)
                    for item in list(child_orchestration_graph.get("nodes") or [])
                    if isinstance(item, dict) and str(item.get("node_id") or "").strip()
                }
                child_entry_node = dict(child_node_map.get(child_entry_node_ids[0]) or {})
                if not child_entry_node:
                    raise GraphContractValidationError(
                        f"{label} references a child graph whose entry node could not be resolved."
                    )
                child_seed_input = deepcopy(next(iter(typed_inputs.values()), {}))
                if isinstance(child_seed_input, dict) and str(child_seed_input.get("artifact_uri") or "").strip():
                    child_seed_loaded = self._graph_live_load_structured_artifact_ref(
                        child_seed_input,
                        node_id=node_id,
                    )
                    child_seed_input = deepcopy(child_seed_loaded.get("payload"))
                subgraph_seed = self._graph_live_build_seed_subgraph_handoff(
                    parent_graph=graph,
                    parent_graph_id=graph_id,
                    parent_run_id=run_id,
                    parent_node_id=node_id,
                    worker_thread_id=worker_thread_id or f"local-{node_id}",
                    child_graph=child_orchestration_graph,
                    child_entry_node=child_entry_node,
                    typed_input_value=child_seed_input,
                    artifact_root=worker_artifact_root,
                )
                child_context = self._graph_live_parent_context(payload)
                ancestor_graph_ids = {
                    str(item).strip()
                    for item in list(child_context.get("ancestor_graph_ids") or [])
                    if str(item or "").strip()
                }
                ancestor_graph_ids.update(
                    {
                        str(graph_id or "").strip(),
                        str(child_context.get("current_graph_id") or "").strip(),
                    }
                )
                ancestor_graph_ids.discard("")
                node_states[node_id]["subgraph_state"] = {
                    "status": "child_run_started",
                    "graph_ref": graph_ref,
                    "child_graph_id": str(child_graph.get("graph_id") or "").strip(),
                    "seed_agent_envelope_path": str(subgraph_seed.get("agent_envelope_path") or "").strip() or None,
                }
                self._graph_live_append_unique_event(
                    event_refs,
                    {
                        "event_id": f"{run_id}-{node_id}-subgraph-started",
                        "run_id": run_id,
                        "task_id": graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_progress",
                        "created_at": started_at,
                        "summary": f"{label} pinned subgraph {str(child_graph.get('graph_id') or graph_ref).strip()} before child execution.",
                        "node_id": node_id,
                        "parallel_group_id": group_id,
                    },
                )
                current_live_ref = self._graph_live_run_snapshot(
                    run_ref=live_run_ref,
                    node_states=node_states,
                    event_refs=event_refs,
                    artifact_refs=run_artifact_refs,
                    policy_snapshot=run_manifest["run_policy_snapshot"],
                    status="running",
                    approval_state=approval_state or dict(run_manifest.get("approval_state") or {"status": "not_required"}),
                )
                self._write_graph_live_run_manifest_snapshot(
                    run_manifest_path=run_manifest_path,
                    run_manifest=run_manifest,
                    node_states=node_states,
                    artifact_refs=run_artifact_refs,
                    event_refs=event_refs,
                    status="running",
                    updated_at=str(current_live_ref.get("updated_at") or ""),
                    approval_state=approval_state or dict(run_manifest.get("approval_state") or {"status": "not_required"}),
                )
                child_result = self.execute_task_graph_run(
                    {
                        "graph_id": str(child_graph.get("graph_id") or "").strip(),
                        "budget": deepcopy(dict(payload.get("budget") or {})),
                        "_seed_incoming_handoffs": {
                            str(child_entry_node.get("node_id") or "").strip(): [deepcopy(dict(subgraph_seed or {}))]
                        },
                        "_parent_run_context": {
                            "kind": "subgraph",
                            "parent_graph_id": graph_id,
                            "parent_run_id": run_id,
                            "parent_node_id": node_id,
                            "current_graph_id": str(child_graph.get("graph_id") or "").strip(),
                            "ancestor_graph_ids": sorted(ancestor_graph_ids),
                        },
                    }
                )
                child_live_run = dict(child_result.get("live_run") or {})
                child_run_ref = dict(child_live_run.get("run_ref") or {})
                child_status = str(child_live_run.get("run_status") or child_run_ref.get("status") or "").strip()
                child_run_id = str(child_live_run.get("run_id") or child_run_ref.get("run_id") or "").strip()
                if child_status != "completed":
                    node_status = "needs_review"
                    outcome = "needs_review"
                    human_summary = ""
                    machine_result = {
                        "status": "needs_review",
                        "executor": "subgraph",
                        "graph_ref": graph_ref,
                        "child_graph_id": str(child_graph.get("graph_id") or "").strip(),
                        "child_run_id": child_run_id or None,
                        "child_status": child_status or None,
                    }
                    next_action_hints = [
                        "Inspect the child subgraph run before replaying the parent graph.",
                    ]
                else:
                    subgraph_result = self._graph_live_project_subgraph_result(
                        child_graph=child_graph,
                        child_run_id=child_run_id,
                        child_run_ref=child_run_ref,
                    )
                    node_states[node_id]["subgraph_state"] = {
                        "status": "completed",
                        "graph_ref": graph_ref,
                        "child_graph_id": str(child_graph.get("graph_id") or "").strip(),
                        "child_run_id": child_run_id,
                        "child_status": child_status,
                        "child_trace_id": str(subgraph_result.get("child_trace_id") or "").strip() or None,
                    }
                    typed_output_values[output_port_id] = deepcopy(subgraph_result)
                    human_summary = (
                        f"Subgraph {str(child_graph.get('graph_id') or graph_ref).strip()} completed as an isolated child run."
                    )
                    machine_result = {
                        **deepcopy(subgraph_result),
                        "status": "completed",
                    }
            elif compiler_executor_id == "human_approval":
                approval_gate = dict(graph_node.get("approval_gate") or {})
                review_kind = (
                    str(node_type_config.get("review_kind") or "").strip()
                    or str(approval_gate.get("review_kind") or approval_gate.get("approval_kind") or "").strip()
                    or "human_gate"
                )
                reason = (
                    str(node_type_config.get("reason") or "").strip()
                    or str(approval_gate.get("reason") or approval_gate.get("description") or "").strip()
                    or f"{label} requires human approval before continuing."
                )
                approval_state = {
                    "status": "pending",
                    "review_kind": review_kind,
                    "node_id": node_id,
                    "reason": reason,
                    "requested_at": started_at,
                    "worker_thread_id": worker_thread_id,
                    "allowed_actions": [
                        str(item).strip()
                        for item in list(approval_gate.get("allowed_actions") or [])
                        if str(item or "").strip()
                    ]
                    or ["provider_call"],
                    "blocked_actions": [
                        str(item).strip()
                        for item in list(approval_gate.get("blocked_actions") or [])
                        if str(item or "").strip()
                    ]
                    or ["silent_high_risk_execution"],
                }
                node_status = "waiting_on_approval"
                outcome = "pending"
                human_summary = ""
                machine_result = {
                    "status": "approval_pending",
                    "review_kind": review_kind,
                    "reason": reason,
                }
                next_action_hints = [
                    "Resolve the pending human approval before continuing this graph.",
                ]
                typed_output_values = {}
                generated_artifact_refs = []
                selected_edge_ids = []
            else:
                raise GraphContractValidationError(
                    f"{label} references unsupported live executor `{compiler_executor_id}`."
                )
        except McpToolPolicyDenied as exc:
            node_status = "failed"
            outcome = "mcp_policy_denied"
            human_summary = ""
            machine_result = {
                "status": "mcp_policy_denied",
                "error": str(exc),
                "decision": deepcopy(getattr(exc, "decision", {})),
            }
            next_action_hints = [
                "Update the node MCP policy snapshot or resource allowlist before rerunning this graph."
            ]
            typed_output_values = {}
            generated_artifact_refs = []
            selected_edge_ids = []
        except GraphContractValidationError as exc:
            node_status = "failed"
            outcome = "handoff_contract_violation"
            human_summary = ""
            machine_result = {
                "status": "executor_validation_failed",
                "error": str(exc),
            }
            next_action_hints = [
                "Fix the node configuration or typed-port contract before rerunning this graph."
            ]
            typed_output_values = {}
            generated_artifact_refs = []
            selected_edge_ids = []
        except Exception as exc:  # noqa: BLE001
            node_status = "failed"
            outcome = "executor_failed"
            human_summary = ""
            machine_result = {
                "status": "executor_failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            next_action_hints = [
                "Inspect the local executor configuration and preserved worker artifacts before retrying."
            ]
            typed_output_values = {}
            generated_artifact_refs = []
            selected_edge_ids = []

        finished_at = now_iso()
        summary = human_summary or f"{label} local executor {node_status}."
        worker_output_payload = {
            "graph_id": graph_id,
            "run_id": run_id,
            "node_id": node_id,
            "worker_thread_id": worker_thread_id,
            "parent_thread_id": str(worker.get("parent_thread_id") or "").strip(),
            "spawn_mode": str(worker.get("spawn_mode") or "").strip(),
            "worker_origin": str(worker.get("worker_origin") or "").strip(),
            "agent_role": str(worker.get("agent_role") or "").strip(),
            "agent_nickname": str(worker.get("agent_nickname") or "").strip(),
            "execution_backend": str(dict(worker.get("settings") or {}).get("execution_backend") or "local_only"),
            "human_summary": human_summary,
            "machine_result": machine_result,
            "typed_output_values": typed_output_values,
            "generated_artifact_refs": generated_artifact_refs,
            "selected_edge_ids": list(selected_edge_ids),
            "next_action_hints": next_action_hints,
            "status": node_status,
            "provider_call_count": 0,
            "tool_call_count": tool_call_count,
            "attempt_count": attempt_count,
            "elapsed_ms": max(1, int((time.time() - datetime.fromisoformat(started_at).timestamp()) * 1000))
            if "T" in started_at
            else 1,
        }
        try:
            worker_output = self._tasks.record_graph_worker_output(
                worker_output_payload,
                graph_definition=graph,
            )
        except GraphContractValidationError as exc:
            node_status = "failed"
            outcome = "handoff_contract_violation"
            exc_detail = " ".join(str(exc).split())[:240]
            summary = (
                f"{label} produced output that violated the live handoff contract: "
                f"{exc_detail}"
            )
            worker_output_payload.update(
                {
                    "human_summary": "",
                    "machine_result": {
                        "status": "handoff_contract_violation",
                        "error": str(exc),
                    },
                    "typed_output_values": {},
                    "generated_artifact_refs": [],
                    "selected_edge_ids": [],
                    "status": "failed",
                    "next_action_hints": [
                        "Fix the source node output or edge port bindings before rerunning this graph."
                    ],
                }
            )
            worker_output = self._tasks.record_graph_worker_output(
                worker_output_payload,
                graph_definition=graph,
            )
        node_states[node_id].update(
            {
                "status": node_status,
                "outcome": outcome,
                "updated_at": finished_at,
                "summary": summary,
                "worker_thread_id": worker_thread_id or None,
            }
        )
        binding = dict(worker_output.get("worker_binding") or {})
        for handoff in list(binding.get("downstream_handoffs") or []):
            if not isinstance(handoff, dict):
                continue
            target_node_id = str(handoff.get("to_node_id") or "").strip()
            if not target_node_id:
                continue
            envelope = dict(handoff.get("agent_envelope") or {})
            metadata = dict(envelope.get("metadata") or {})
            delivery = dict(envelope.get("delivery") or {})
            envelope_id = str(envelope.get("envelope_id") or "").strip() or f"{node_id}-{target_node_id}"
            self._graph_live_append_unique_event(
                event_refs,
                {
                    "event_id": f"{run_id}-{envelope_id}-created",
                    "run_id": run_id,
                    "task_id": graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "handoff_created",
                    "created_at": finished_at,
                    "summary": f"Structured handoff from {label} to {self._tasks._graph_node_label(graph, target_node_id)} was persisted.",
                    "node_id": node_id,
                    "parallel_group_id": group_id,
                    "payload": {
                        "envelope_id": envelope_id,
                        "message_id": str(envelope.get("message_id") or "").strip() or None,
                        "delivery_idempotency_key": str(delivery.get("idempotency_key") or "").strip() or None,
                        "correlation_id": str(metadata.get("correlation_id") or "").strip() or None,
                        "causation_id": str(metadata.get("causation_id") or "").strip() or None,
                        "source_node_id": str(metadata.get("source_node_id") or "").strip() or node_id,
                        "target_node_id": str(metadata.get("target_node_id") or "").strip() or target_node_id,
                    },
                },
            )
            incoming_handoffs.setdefault(target_node_id, []).append(
                {
                    "source_node_id": node_id,
                    "source_label": label,
                    "output_summary": dict(binding.get("output_summary") or {}),
                    "handoff": deepcopy(handoff),
                }
            )
        if compiler_executor_id == "router_condition":
            selected_edge_id_set = {
                str(item).strip()
                for item in list(selected_edge_ids or [])
                if str(item or "").strip()
            }
            for edge in list(graph.get("edges") or []):
                if not isinstance(edge, dict):
                    continue
                if str(edge.get("from_node_id") or "").strip() != node_id:
                    continue
                edge_id = str(edge.get("edge_id") or "").strip()
                if not edge_id or edge_id in selected_edge_id_set:
                    continue
                target_node_id = str(edge.get("to_node_id") or "").strip()
                if not target_node_id:
                    continue
                other_inbound_edges = [
                    dict(item)
                    for item in list(graph.get("edges") or [])
                    if isinstance(item, dict)
                    and str(item.get("to_node_id") or "").strip() == target_node_id
                    and str(item.get("from_node_id") or "").strip() != node_id
                ]
                if other_inbound_edges:
                    continue
                existing_target_state = dict(node_states.get(target_node_id) or {})
                if str(existing_target_state.get("status") or "").strip() in {
                    "completed",
                    "failed",
                    "cancelled",
                    "needs_review",
                    "blocked",
                }:
                    continue
                node_states[target_node_id].update(
                    {
                        "status": "completed",
                        "outcome": "not_selected",
                        "updated_at": finished_at,
                        "summary": f"{self._tasks._graph_node_label(graph, target_node_id)} was skipped because router edge {edge_id} was not selected.",
                    }
                )
                self._graph_live_append_unique_event(
                    event_refs,
                    {
                        "event_id": f"{run_id}-{target_node_id}-not-selected",
                        "run_id": run_id,
                        "task_id": graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_completed",
                        "created_at": finished_at,
                        "summary": f"{self._tasks._graph_node_label(graph, target_node_id)} was skipped because router edge {edge_id} was not selected.",
                        "node_id": target_node_id,
                        "parallel_group_id": group_id,
                    },
                )
        merged_artifact_refs = self._tasks._merge_graph_worker_artifact_refs(
            run_artifact_refs,
            [
                dict(item)
                for item in list(binding.get("artifact_refs") or [])
                if isinstance(item, dict)
            ],
        )
        self._graph_live_append_unique_event(
            event_refs,
            {
                "event_id": f"{run_id}-{node_id}-{node_status}",
                "run_id": run_id,
                "task_id": graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": (
                    "approval_requested"
                    if node_status == "waiting_on_approval"
                    else (
                        "node_completed"
                        if node_status == "completed"
                        else ("node_cancelled" if node_status == "cancelled" else ("node_blocked" if node_status == "needs_review" else "node_failed"))
                    )
                ),
                "created_at": finished_at,
                "summary": summary,
                "node_id": node_id,
                "parallel_group_id": group_id,
            },
        )
        current_live_ref = dict(worker_output.get("run_ref") or self._tasks.graph_run_ref(run_id) or live_run_ref)
        updated_live_ref = self._graph_live_run_snapshot(
            run_ref=current_live_ref,
            node_states=node_states,
            event_refs=event_refs,
            artifact_refs=merged_artifact_refs,
            policy_snapshot=run_manifest["run_policy_snapshot"],
            status="running",
            approval_state=approval_state or dict(run_manifest.get("approval_state") or {"status": "not_required"}),
        )
        self._write_graph_live_run_manifest_snapshot(
            run_manifest_path=run_manifest_path,
            run_manifest=run_manifest,
            node_states=node_states,
            artifact_refs=merged_artifact_refs,
            event_refs=event_refs,
            status="running",
            updated_at=str(updated_live_ref.get("updated_at") or ""),
            approval_state=approval_state or dict(run_manifest.get("approval_state") or {"status": "not_required"}),
        )
        return {
            "live_run_ref": updated_live_ref,
            "artifact_refs": merged_artifact_refs,
            "approval_state": deepcopy(approval_state) if isinstance(approval_state, dict) else None,
        }

    def _graph_live_turn_usage_signal(
        self,
        *,
        thread_id: str,
        turn_id: str,
        provider_id: str | None,
        model: str | None,
    ) -> dict[str, Any]:
        token_usage = self._latest_context_token_usage(thread_id)
        if not token_usage:
            return usage_not_available(
                source="task_graph_live_run",
                reason="token_usage_notification_missing",
                provider_id=provider_id,
                model=model,
                request_kind="task_graph_live_run",
            )
        observed_turn_id = str(token_usage.get("turn_id") or "").strip()
        if (
            turn_id
            and observed_turn_id
            and observed_turn_id != turn_id
            and self._observed_turn_alias_target(
                thread_id=thread_id,
                observed_turn_id=observed_turn_id,
            ) != turn_id
        ):
            return usage_not_available(
                source="task_graph_live_run",
                reason="latest_token_usage_belongs_to_another_turn",
                provider_id=provider_id,
                model=model,
                request_kind="task_graph_live_run",
            )
        total = dict(token_usage.get("total") or {})
        if not total:
            return usage_not_available(
                source="task_graph_live_run",
                reason="token_usage_total_missing",
                provider_id=provider_id,
                model=model,
                request_kind="task_graph_live_run",
            )
        return normalize_usage_signal(
            source="task_graph_live_run",
            provider_id=provider_id,
            model=model,
            usage={
                "input_tokens": total.get("inputTokens"),
                "output_tokens": total.get("outputTokens"),
                "reasoning_tokens": total.get("reasoningOutputTokens"),
                "cached_input_tokens": total.get("cachedInputTokens"),
                "total_tokens": total.get("totalTokens"),
            },
            request_kind="task_graph_live_run",
        )

    def _graph_live_run_prompt(
        self,
        *,
        task: dict[str, Any],
        graph: dict[str, Any],
        node: dict[str, Any],
        incoming_handoffs: list[dict[str, Any]],
        neutral_context: dict[str, Any] | None = None,
    ) -> str:
        goal = task.get("goal")
        if isinstance(goal, str):
            task_goal = goal.strip()
        elif goal is None:
            task_goal = ""
        else:
            task_goal = json.dumps(goal, ensure_ascii=False)
        prompt_template = str(node.get("human_summary_template") or "").strip() or (
            f"Complete the {str(node.get('label') or node.get('node_id') or 'current')} task."
        )
        sections = [
            f"Task graph: {str(graph.get('title') or '').strip()}",
            f"Current node: {str(node.get('label') or node.get('node_id') or '').strip()}",
            f"Node role: {str(node.get('kind') or '').strip() or 'worker'}",
            "Objective:",
            prompt_template,
        ]
        if task_goal:
            sections.extend(["Task context:", task_goal[:4000]])
        if incoming_handoffs:
            handoff_lines: list[str] = []
            for index, item in enumerate(incoming_handoffs, start=1):
                output_summary = dict(item.get("output_summary") or {})
                handoff = dict(item.get("handoff") or {})
                downstream_input = dict(handoff.get("downstream_input") or {})
                envelope = dict(item.get("agent_envelope") or {})
                metadata = dict(envelope.get("metadata") or {})
                typed_handoff = dict(metadata.get("typed_handoff") or {})
                typed_inputs = dict(typed_handoff.get("inputs") or {})
                content_parts = [
                    dict(part)
                    for part in list(envelope.get("content") or [])
                    if isinstance(part, dict)
                ]
                artifact_uris = [
                    str(dict(part.get("artifact") or {}).get("artifact_uri") or "").strip()
                    for part in content_parts
                    if isinstance(part.get("artifact"), dict)
                    and str(dict(part.get("artifact") or {}).get("artifact_uri") or "").strip()
                ]
                artifact_paths = [
                    str(path).strip()
                    for path in list(downstream_input.get("artifact_paths") or [])
                    if str(path or "").strip()
                ]
                artifact_summary = ", ".join(artifact_uris or artifact_paths) if (artifact_uris or artifact_paths) else "none"
                text_parts = [
                    str(part.get("text") or "").strip()
                    for part in content_parts
                    if str(part.get("kind") or "").strip() == "text" and str(part.get("text") or "").strip()
                ]
                json_previews = [
                    json.dumps(part.get("data") or {}, ensure_ascii=False)[:320]
                    for part in content_parts
                    if str(part.get("kind") or "").strip() == "json" and isinstance(part.get("data"), dict)
                ]
                part_kinds = [
                    str(part.get("kind") or "").strip()
                    for part in content_parts
                    if str(part.get("kind") or "").strip()
                ]
                typed_inputs_preview = json.dumps(typed_inputs, ensure_ascii=False)[:600] if typed_inputs else "none"
                handoff_lines.append(
                    (
                        f"{index}. From {str(item.get('source_label') or item.get('source_node_id') or 'upstream').strip()}: "
                        f"typed_inputs={typed_inputs_preview}; "
                        f"parts={', '.join(part_kinds) if part_kinds else 'none'}; "
                        f"text={'; '.join(text_parts)[:320] or str(output_summary.get('human_summary') or '').strip()[:320] or 'none'}; "
                        f"json={'; '.join(json_previews)[:320] or str(output_summary.get('machine_result_preview') or '').strip()[:320] or 'none'}; "
                        f"artifacts={artifact_summary}"
                    )
                )
            sections.extend(["Upstream handoffs:", *handoff_lines])
        if isinstance(neutral_context, dict) and neutral_context:
            typed_input_port_ids = [
                str(item).strip()
                for item in list(neutral_context.get("typed_input_port_ids") or [])
                if str(item or "").strip()
            ]
            provider_pairs = [
                f"{str(dict(item).get('source_provider') or '').strip()}->{str(dict(item).get('target_provider') or '').strip()}"
                for item in list(neutral_context.get("provider_pairs") or [])
                if isinstance(item, dict)
            ]
            sections.extend(
                [
                    "Neutral handoff context:",
                    f"Attached neutral context bundle: {str(neutral_context.get('bundle_path') or '').strip() or 'attached'}",
                    f"Typed input ports: {', '.join(typed_input_port_ids) if typed_input_port_ids else 'none'}",
                    f"Provider projection pairs: {', '.join(provider_pairs) if provider_pairs else 'none'}",
                    f"Projection warnings: {int(neutral_context.get('projection_warning_count') or 0)}",
                    f"Tool-pair repairs: {int(neutral_context.get('total_repaired_tool_pairs') or 0)}",
                    (
                        "Use the attached neutral context bundle and attached artifacts as the authoritative upstream state. "
                        "Do not rely on provider-native transcript fields, hidden reasoning, or preview-only summaries."
                    ),
                ]
            )
        schema_hint = node.get("machine_result_schema")
        if not isinstance(schema_hint, dict) or not schema_hint:
            schema_hint = dict(node.get("output_contract") or {}).get("machine_result_schema")
        if isinstance(schema_hint, dict) and schema_hint:
            sections.extend(["Machine-result JSON schema hint:", json.dumps(schema_hint, ensure_ascii=False, indent=2)[:3000]])
        sections.extend(
            [
                "Response contract:",
                "This is one bounded task-graph node. Finish in a single reply and stop.",
                "Return a single JSON object with keys `human_summary` and `machine_result`.",
                "`human_summary` must be plain text. `machine_result` must be an object.",
                "When typed upstream inputs are present, treat them as authoritative; previews and summaries are advisory only.",
                "Do not open an extended planning loop, do not inspect the repository, and do not call tools unless the prompt explicitly requires them.",
                "Do not include markdown fences, preambles, or trailing commentary outside the JSON object.",
            ]
        )
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _graph_live_append_unique_event(
        event_refs: list[dict[str, Any]],
        event: dict[str, Any],
    ) -> None:
        event_id = str(dict(event).get("event_id") or "").strip()
        if event_id and any(str(item.get("event_id") or "").strip() == event_id for item in event_refs):
            return
        event_refs.append(dict(event))

    def _graph_live_prepare_incoming_handoffs(
        self,
        *,
        graph: dict[str, Any],
        node_id: str,
        incoming_handoffs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        orchestration_graph = (
            graph
            if graph.get("schema_registry") is not None
            else self._tasks._orchestration_graph_for_task_graph(graph)
        )
        prepared: list[dict[str, Any]] = []
        seen_delivery_keys: set[str] = set()
        target_provider_id = ""
        for graph_node in list(orchestration_graph.get("nodes") or []):
            if not isinstance(graph_node, dict):
                continue
            if str(graph_node.get("node_id") or "").strip() != node_id:
                continue
            target_provider_id = str(graph_node.get("provider_id") or "").strip()
            break
        durable_store = self._tasks.durable_run_store()
        for item in incoming_handoffs:
            if not isinstance(item, dict):
                continue
            handoff = dict(item.get("handoff") or {})
            envelope = self._tasks._load_graph_handoff_agent_envelope(
                handoff,
                expected_target_node_id=node_id,
                graph_definition=orchestration_graph,
            )
            delivery_key = str(dict(envelope.get("delivery") or {}).get("idempotency_key") or "").strip()
            if delivery_key and delivery_key in seen_delivery_keys:
                continue
            admission = durable_store.admit_agent_envelope_processing(
                envelope,
                target_node_id=node_id,
                target_provider_id=target_provider_id or None,
            )
            if str(admission.get("status") or "").strip() != "accepted":
                continue
            if delivery_key:
                seen_delivery_keys.add(delivery_key)
            prepared.append({**dict(item), "agent_envelope": dict(admission.get("envelope") or envelope), "delivery_processing": admission})
        return prepared

    def _graph_live_validate_machine_result_contract(
        self,
        *,
        graph: dict[str, Any],
        node_id: str,
        node_label: str,
        machine_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        verdict = self._tasks.validate_graph_node_machine_result_contract(
            graph,
            node_id=node_id,
            machine_result=machine_result,
        )
        if verdict is None:
            return None
        errors = [
            str(item).strip()
            for item in list(dict(verdict).get("errors") or [])
            if str(item or "").strip()
        ]
        schema_ref = str(dict(verdict).get("schema_ref") or "").strip() or f"schema.{node_id}.machine_result"
        clean_label = str(node_label or node_id).strip() or node_id
        first_error = errors[0] if errors else "machine_result violated the declared schema."
        return {
            "node_status": "failed",
            "outcome": "schema_violation",
            "summary": f"{clean_label} returned a machine_result that violated {schema_ref}.",
            "output_human_summary": "",
            "machine_result": {
                "status": "schema_violation",
                "schema_ref": schema_ref,
                "errors": errors,
                "received_machine_result": deepcopy(machine_result),
            },
            "next_action_hints": [
                f"Fix the node output so machine_result satisfies {schema_ref}.",
                first_error,
            ],
        }

    @staticmethod
    def _graph_live_artifact_attachment_key(artifact_ref: dict[str, Any]) -> str:
        metadata = dict(artifact_ref.get("metadata") or {})
        return (
            str(metadata.get("relative_path") or "").strip()
            or str(artifact_ref.get("artifact_uri") or "").strip()
            or str(artifact_ref.get("artifact_id") or "").strip()
        )

    def _graph_live_attachment_from_artifact_ref(self, artifact_ref: dict[str, Any]) -> dict[str, Any] | None:
        metadata = dict(artifact_ref.get("metadata") or {})
        relative_path = str(metadata.get("relative_path") or artifact_ref.get("path") or "").strip()
        if not relative_path:
            return None
        resolved = resolve_under(self._projects.require_workspace_root(), relative_path)
        if resolved is None or not resolved.exists() or not resolved.is_file():
            return None
        media_type = str(artifact_ref.get("media_type") or artifact_ref.get("mime_type") or "").strip() or (
            mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        )
        return {
            "path": resolved.as_posix(),
            "name": resolved.name,
            "mime_type": media_type,
            "kind": "image" if media_type.startswith("image/") else "file",
            "source": "graph_handoff_artifact",
        }

    def _graph_live_trim_projection_detail(self, detail: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        trimmed = deepcopy(detail)
        warnings = [
            str(item).strip()
            for item in list(trimmed.get("warnings") or [])
            if str(item or "").strip()
        ]
        truncation = {
            "applied": False,
            "message_limit": GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_HISTORY_MESSAGES,
            "replayable_artifact_limit": GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_REPLAYABLE_ARTIFACTS,
            "json_byte_limit": GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_JSON_BYTES,
            "reasons": [],
        }
        messages = [deepcopy(item) for item in list(trimmed.get("messages") or []) if isinstance(item, dict)]
        original_message_count = len(messages)
        if original_message_count > GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_HISTORY_MESSAGES:
            messages = messages[-GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_HISTORY_MESSAGES :]
            reason = (
                f"Projected history messages were truncated deterministically from {original_message_count} "
                f"to {len(messages)} by keeping the newest messages."
            )
            warnings.append(reason)
            truncation["applied"] = True
            truncation["reasons"].append(reason)
        trimmed["messages"] = messages
        trimmed["projected_message_count"] = len(messages)
        replayable_artifacts = [
            deepcopy(item)
            for item in list(trimmed.get("replayable_artifacts") or [])
            if isinstance(item, dict)
        ]
        original_artifact_count = len(replayable_artifacts)
        if original_artifact_count > GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_REPLAYABLE_ARTIFACTS:
            replayable_artifacts = replayable_artifacts[:GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_REPLAYABLE_ARTIFACTS]
            reason = (
                f"Replayable projected artifacts were truncated deterministically from {original_artifact_count} "
                f"to {len(replayable_artifacts)} by keeping the earliest replayable artifacts."
            )
            warnings.append(reason)
            truncation["applied"] = True
            truncation["reasons"].append(reason)
        trimmed["replayable_artifacts"] = replayable_artifacts
        trimmed["replayable_artifact_count"] = len(replayable_artifacts)
        trimmed["warnings"] = warnings
        return trimmed, truncation

    def _graph_live_prepare_neutral_context_bundle(
        self,
        *,
        graph: dict[str, Any],
        node: dict[str, Any],
        run_id: str,
        incoming_handoffs: list[dict[str, Any]],
        artifact_root: Path,
        attempt_count: int,
        target_provider_id: str,
    ) -> dict[str, Any] | None:
        if not incoming_handoffs:
            return None
        node_id = str(node.get("node_id") or "").strip()
        if not node_id:
            return None
        workspace_root = self._projects.require_workspace_root()
        bundle_root = artifact_root / node_id
        bundle_root.mkdir(parents=True, exist_ok=True)
        bundle_path = bundle_root / f"neutral-context-attempt-{max(1, int(attempt_count or 1))}.json"
        merged_typed_inputs: dict[str, Any] = {}
        projection_warnings: list[str] = []
        attachments: list[dict[str, Any]] = []
        seen_attachment_keys: set[str] = set()
        incoming_entries: list[dict[str, Any]] = []
        provider_pairs: list[dict[str, Any]] = []
        total_repaired_tool_pairs = 0
        stripped_private_state = False
        for index, item in enumerate(incoming_handoffs, start=1):
            handoff = dict(item.get("handoff") or {})
            envelope = dict(item.get("agent_envelope") or {})
            metadata = dict(envelope.get("metadata") or {})
            delivery = dict(envelope.get("delivery") or {})
            sender = dict(envelope.get("sender") or {})
            typed_handoff = dict(metadata.get("typed_handoff") or {})
            typed_inputs = deepcopy(dict(typed_handoff.get("inputs") or {}))
            for port_id, value in typed_inputs.items():
                clean_port_id = str(port_id or "").strip()
                if not clean_port_id:
                    continue
                if clean_port_id not in merged_typed_inputs:
                    merged_typed_inputs[clean_port_id] = deepcopy(value)
                elif merged_typed_inputs[clean_port_id] != value:
                    warning = (
                        f"Incoming handoffs disagreed on target input port {clean_port_id}; preserved the first validated payload."
                    )
                    if warning not in projection_warnings:
                        projection_warnings.append(warning)
            source_thread_id = str(dict(metadata.get("provenance") or {}).get("source_worker_thread_id") or dict(sender).get("lane_id") or "").strip()
            projection_detail = self._handoff_projection_detail(
                source_thread_id=source_thread_id,
                target_provider_id=target_provider_id,
            )
            projection_truncation = None
            if projection_detail:
                projection_detail, projection_truncation = self._graph_live_trim_projection_detail(projection_detail)
                total_repaired_tool_pairs += int(projection_detail.get("repaired_tool_pairs") or 0)
                for warning in list(projection_detail.get("warnings") or []):
                    clean_warning = str(warning or "").strip()
                    if clean_warning:
                        projection_warnings.append(clean_warning)
                        if "provider-private" in clean_warning.lower():
                            stripped_private_state = True
            artifact_refs: list[dict[str, Any]] = []
            downstream_input = dict(handoff.get("downstream_input") or {})
            for artifact in list(downstream_input.get("artifact_refs") or []):
                if isinstance(artifact, dict):
                    artifact_refs.append(deepcopy(artifact))
            for part in list(envelope.get("content") or []):
                if not isinstance(part, dict):
                    continue
                artifact = dict(part.get("artifact") or {})
                if artifact:
                    artifact_refs.append(deepcopy(artifact))
            deduped_artifact_refs: list[dict[str, Any]] = []
            seen_artifact_keys: set[str] = set()
            for artifact_ref in artifact_refs:
                key = self._graph_live_artifact_attachment_key(artifact_ref)
                if not key or key in seen_artifact_keys:
                    continue
                seen_artifact_keys.add(key)
                deduped_artifact_refs.append(artifact_ref)
                attachment = self._graph_live_attachment_from_artifact_ref(artifact_ref)
                if attachment:
                    attachment_key = str(attachment.get("path") or "").strip()
                    if attachment_key and attachment_key not in seen_attachment_keys:
                        attachments.append(attachment)
                        seen_attachment_keys.add(attachment_key)
            source_provider = str(sender.get("provider_id") or "").strip() or None
            if projection_detail and str(projection_detail.get("source_provider") or "").strip():
                source_provider = str(projection_detail.get("source_provider") or "").strip()
            if source_provider:
                pair = {"source_provider": source_provider, "target_provider": target_provider_id}
                if pair not in provider_pairs:
                    provider_pairs.append(pair)
            incoming_entries.append(
                {
                    "index": index,
                    "source_node_id": str(metadata.get("source_node_id") or item.get("source_node_id") or "").strip() or None,
                    "source_label": str(item.get("source_label") or metadata.get("source_node_id") or "").strip() or None,
                    "target_node_id": str(metadata.get("target_node_id") or node_id).strip() or node_id,
                    "edge_id": str(metadata.get("edge_id") or "").strip() or None,
                    "envelope_id": str(envelope.get("envelope_id") or "").strip() or None,
                    "message_id": str(envelope.get("message_id") or "").strip() or None,
                    "source_provider_id": source_provider,
                    "target_provider_id": target_provider_id,
                    "trace_id": str(delivery.get("trace_id") or "").strip() or None,
                    "correlation_id": str(metadata.get("correlation_id") or "").strip() or None,
                    "causation_id": str(metadata.get("causation_id") or "").strip() or None,
                    "schema_refs": [str(ref).strip() for ref in list(metadata.get("schema_refs") or []) if str(ref or "").strip()],
                    "typed_inputs": typed_inputs,
                    "artifact_refs": deduped_artifact_refs,
                    "resource_refs": [str(ref).strip() for ref in list(downstream_input.get("resource_refs") or []) if str(ref or "").strip()],
                    "context_policy": deepcopy(dict(metadata.get("context_policy_snapshot") or {})),
                    "provenance": deepcopy(dict(metadata.get("provenance") or {})),
                    "projected_history": projection_detail,
                    "projection_truncation": projection_truncation,
                }
            )
        deduped_projection_warnings: list[str] = []
        for warning in projection_warnings:
            clean_warning = str(warning or "").strip()
            if clean_warning and clean_warning not in deduped_projection_warnings:
                deduped_projection_warnings.append(clean_warning)
        lineage = {
            "task_id": str(graph.get("task_id") or "").strip() or None,
            "graph_id": str(graph.get("graph_id") or "").strip() or None,
            "run_id": str(run_id or "").strip() or None,
            "target_node_id": node_id,
            "target_provider_id": str(target_provider_id or "").strip() or None,
            "source_node_ids": sorted(
                {
                    str(item.get("source_node_id") or "").strip()
                    for item in incoming_entries
                    if str(item.get("source_node_id") or "").strip()
                }
            ),
            "source_thread_ids": sorted(
                {
                    str(dict(item.get("provenance") or {}).get("source_worker_thread_id") or "").strip()
                    for item in incoming_entries
                    if str(dict(item.get("provenance") or {}).get("source_worker_thread_id") or "").strip()
                }
            ),
            "envelope_ids": sorted(
                {
                    str(item.get("envelope_id") or "").strip()
                    for item in incoming_entries
                    if str(item.get("envelope_id") or "").strip()
                }
            ),
            "correlation_ids": sorted(
                {
                    str(item.get("correlation_id") or "").strip()
                    for item in incoming_entries
                    if str(item.get("correlation_id") or "").strip()
                }
            ),
            "causation_ids": sorted(
                {
                    str(item.get("causation_id") or "").strip()
                    for item in incoming_entries
                    if str(item.get("causation_id") or "").strip()
                }
            ),
        }
        projection_payload = {
            "typed_inputs": deepcopy(merged_typed_inputs),
            "incoming_handoffs": deepcopy(incoming_entries),
            "provider_pairs": deepcopy(provider_pairs),
            "projection_warnings": list(deduped_projection_warnings),
            "provider_private_state_removed": bool(stripped_private_state),
            "total_repaired_tool_pairs": int(total_repaired_tool_pairs or 0),
        }
        bundle = {
            "schema_version": "astrabridge-graph-neutral-context-v1",
            "graph_id": str(graph.get("graph_id") or "").strip(),
            "run_id": run_id,
            "task_id": str(graph.get("task_id") or "").strip(),
            "target_node_id": node_id,
            "target_provider_id": target_provider_id,
            "target_model_id": str(node.get("model_id") or "").strip() or None,
            "created_at": now_iso(),
            "typed_inputs": merged_typed_inputs,
            "incoming_handoffs": incoming_entries,
            "provider_pairs": provider_pairs,
            "projection_warnings": deduped_projection_warnings,
            "provider_private_state_removed": stripped_private_state,
            "total_repaired_tool_pairs": total_repaired_tool_pairs,
            "lineage": lineage,
            "projection_digest": self._stable_json_digest(projection_payload),
            "lineage_digest": self._stable_json_digest(lineage),
            "budget": {
                "history_message_limit": GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_HISTORY_MESSAGES,
                "replayable_artifact_limit": GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_REPLAYABLE_ARTIFACTS,
                "json_byte_limit": GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_JSON_BYTES,
            },
            "estimated_json_bytes": 0,
            "truncation": {
                "applied": any(bool(dict(entry.get("projection_truncation") or {}).get("applied")) for entry in incoming_entries),
                "reasons": [
                    reason
                    for entry in incoming_entries
                    for reason in list(dict(entry.get("projection_truncation") or {}).get("reasons") or [])
                    if str(reason or "").strip()
                ],
            },
        }
        bundle["bundle_digest"] = self._stable_json_digest(bundle)
        encoded = json.dumps(bundle, ensure_ascii=False, indent=2)
        bundle["estimated_json_bytes"] = len(encoded.encode("utf-8"))
        if bundle["estimated_json_bytes"] > GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_JSON_BYTES:
            warning = (
                f"Neutral context bundle estimated size {bundle['estimated_json_bytes']} bytes exceeds the configured budget "
                f"{GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_JSON_BYTES} bytes; deterministic per-handoff truncation was applied first."
            )
            if warning not in bundle["projection_warnings"]:
                bundle["projection_warnings"].append(warning)
            bundle["truncation"]["applied"] = True
            bundle["truncation"]["reasons"].append(warning)
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        context_attachment = {
            "path": bundle_path.as_posix(),
            "name": f"{node_id}-neutral-context.json",
            "mime_type": "application/json",
            "kind": "file",
            "source": "graph_neutral_context_bundle",
        }
        bundle_artifact_ref = {
            "artifact_id": f"{run_id}-{node_id}-neutral-context-json-{max(1, int(attempt_count or 1))}",
            "artifact_kind": "structured_json",
            "task_id": str(graph.get("task_id") or "").strip(),
            "run_id": run_id,
            "source_node_id": node_id,
            "path": bundle_path.relative_to(Path(workspace_root)).as_posix(),
            "media_type": "application/json",
            "status": "ready",
            "created_at": str(bundle.get("created_at") or now_iso()),
        }
        return {
            "bundle_path": bundle_path.relative_to(Path(workspace_root)).as_posix(),
            "bundle": bundle,
            "attachments": [context_attachment, *attachments],
            "artifact_refs": [bundle_artifact_ref],
            "summary": {
                "bundle_path": bundle_path.relative_to(Path(workspace_root)).as_posix(),
                "incoming_handoff_count": len(incoming_entries),
                "typed_input_port_ids": sorted(merged_typed_inputs),
                "provider_pairs": provider_pairs,
                "projection_digest": str(bundle.get("projection_digest") or ""),
                "lineage_digest": str(bundle.get("lineage_digest") or ""),
                "bundle_digest": str(bundle.get("bundle_digest") or ""),
                "projection_warning_count": len(bundle["projection_warnings"]),
                "total_repaired_tool_pairs": total_repaired_tool_pairs,
                "provider_private_state_removed": stripped_private_state,
                "truncation_applied": bool(bundle["truncation"]["applied"]),
            },
        }

    def _normalize_graph_worker_collaboration_mode(
        self,
        node: dict[str, Any],
        *,
        collaboration_mode: str | None = None,
    ) -> str | None:
        requested = str(collaboration_mode if collaboration_mode is not None else node.get("collaboration_mode") or "").strip().lower()
        if not requested:
            return None
        if requested == "plan":
            return "default"
        return requested

    @staticmethod
    def _graph_live_run_parse_response(final_text: str) -> dict[str, Any]:
        text = str(final_text or "").strip()
        parsed = RuntimeService._graph_live_run_extract_json(text)
        if isinstance(parsed, dict):
            human_summary = str(parsed.get("human_summary") or "").strip()
            machine_result = parsed.get("machine_result")
            if isinstance(machine_result, dict):
                return {
                    "human_summary": human_summary,
                    "machine_result": machine_result,
                }
            if human_summary:
                remainder = {key: value for key, value in parsed.items() if key != "human_summary"}
                return {
                    "human_summary": human_summary,
                    "machine_result": remainder or {"raw_json": parsed},
                }
            return {"human_summary": "", "machine_result": parsed}
        return {
            "human_summary": text[:1200],
            "machine_result": {"raw_text": text[:4000]} if text else {},
        }

    @staticmethod
    def _graph_live_run_terminal_outcome(
        *,
        node_label: str,
        thread_status: str,
        final_text: str,
        reasoning_text: str,
        parsed_output: dict[str, Any],
        policy_violation: dict[str, Any] | None,
        budget_exceeded: bool,
        observed_tokens: Any,
        token_budget: int,
    ) -> dict[str, Any]:
        clean_label = str(node_label or "").strip() or "Node"
        clean_status = str(thread_status or "").strip().lower()
        clean_text = str(final_text or "").strip()
        clean_reasoning = str(reasoning_text or "").strip()
        human_summary = str(parsed_output.get("human_summary") or "").strip()
        parsed_machine_result = parsed_output.get("machine_result")
        violation_detail = dict(policy_violation or {}) if isinstance(policy_violation, dict) else None
        parsed_json = RuntimeService._graph_live_run_extract_json(clean_text)

        if violation_detail is not None:
            if clean_status == "completed" and isinstance(parsed_json, dict) and isinstance(parsed_machine_result, dict) and parsed_machine_result:
                violation_detail["compliant_success"] = True
                violation_detail["recovery"] = "structured_response_salvaged_after_blocked_tools"
                return {
                    "node_status": "completed",
                    "outcome": "partial",
                    "summary": human_summary
                    or f"{clean_label} returned a bounded result after blocked tool requests were ignored.",
                    "output_human_summary": human_summary,
                    "machine_result": parsed_machine_result,
                    "policy_violation": violation_detail,
                    "next_action_hints": [
                        "Review the blocked tool requests; this node completed via structured-response fallback.",
                    ],
                }
            return {
                "node_status": "failed",
                "outcome": "policy_violated",
                "summary": f"{clean_label} requested tools outside its no-tools contract.",
                "machine_result": {
                    "status": "policy_violated",
                    "execution_policy": violation_detail,
                    "response_text": clean_text[:4000],
                },
                "policy_violation": violation_detail,
                "next_action_hints": [
                    "Tighten the node prompt or tool policy before rerunning this graph.",
                ],
            }
        if budget_exceeded:
            return {
                "node_status": "failed",
                "outcome": "budget_exceeded",
                "summary": (
                    f"{clean_label} exceeded its enforced token allocation "
                    f"({observed_tokens} / {token_budget})."
                ),
                "output_human_summary": f"{clean_label} exceeded its enforced token allocation ({observed_tokens} / {token_budget}).",
                "machine_result": {
                    "status": "budget_exceeded",
                    "observed_total_tokens": observed_tokens,
                    "token_budget": token_budget,
                    "response_text": clean_text[:4000],
                },
                "policy_violation": None,
                "next_action_hints": [
                    "Increase the node budget or reduce its prompt/context scope before retrying.",
                ],
            }
        if clean_status == "completed":
            if not isinstance(parsed_json, dict):
                return {
                    "node_status": "failed",
                    "outcome": "invalid_output",
                    "summary": f"{clean_label} completed without returning the required JSON envelope.",
                    "output_human_summary": "",
                    "machine_result": {
                        "status": "invalid_output",
                        "response_text": clean_text[:4000],
                    },
                    "policy_violation": None,
                    "next_action_hints": [
                        "Fix the node prompt or output contract so the worker returns `human_summary` plus an object `machine_result`.",
                    ],
                }
            machine_result = parsed_machine_result
            if not isinstance(machine_result, dict) or not machine_result:
                return {
                    "node_status": "failed",
                    "outcome": "invalid_output",
                    "summary": f"{clean_label} completed without a valid object `machine_result` payload.",
                    "output_human_summary": "",
                    "machine_result": {
                        "status": "invalid_output",
                        "response_text": clean_text[:4000],
                        "reasoning_excerpt": clean_reasoning[:800] if clean_reasoning else None,
                    },
                    "policy_violation": None,
                    "next_action_hints": [
                        "Fix the node output schema or response template before retrying.",
                    ],
                }
            return {
                "node_status": "completed",
                "outcome": "passed",
                "summary": human_summary or (clean_text[:400] if clean_text else f"{clean_label} completed."),
                "output_human_summary": human_summary,
                "machine_result": machine_result,
                "policy_violation": None,
                "next_action_hints": [],
            }
        if clean_status == "cancelled":
            return {
                "node_status": "cancelled",
                "outcome": "cancelled",
                "summary": f"{clean_label} was cancelled before completion.",
                "output_human_summary": f"{clean_label} was cancelled before completion.",
                "machine_result": {"status": "cancelled", "response_text": clean_text[:4000]},
                "policy_violation": None,
                "next_action_hints": [],
            }
        return {
            "node_status": "failed",
            "outcome": "failed",
            "summary": f"{clean_label} finished with status {clean_status or 'failed'}.",
            "output_human_summary": f"{clean_label} finished with status {clean_status or 'failed'}.",
            "machine_result": {"status": clean_status or "failed", "response_text": clean_text[:4000]},
            "policy_violation": None,
            "next_action_hints": [],
        }

    @staticmethod
    def _graph_live_run_extract_json(text: str) -> dict[str, Any] | None:
        if not text:
            return None
        candidates = [text]
        fenced = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
        candidates.extend(fenced)
        brace_match = re.search(r"(\{[\s\S]*\})", text)
        if brace_match:
            candidates.append(brace_match.group(1))
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _reconcile_graph_live_started_turns(
        self,
        *,
        graph: dict[str, Any],
        run_id: str,
        started_executions: list[dict[str, Any]],
        settled_execution_keys: set[tuple[str, str]],
        node_states: dict[str, dict[str, Any]],
        event_refs: list[dict[str, Any]],
        artifact_refs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for execution in started_executions:
            thread_id = str(execution.get("execution_thread_id") or "").strip()
            turn_id = str(execution.get("turn_id") or "").strip()
            node_id = str(execution.get("node_id") or "").strip()
            execution_key = (thread_id, turn_id)
            if not thread_id or not turn_id or execution_key in settled_execution_keys:
                continue
            record: dict[str, Any] = {
                "node_id": node_id or None,
                "thread_id": thread_id,
                "turn_id": turn_id,
                "action": "inspect_then_interrupt",
                "status": "pending",
            }
            try:
                notification = self._terminal_turn_notification(thread_id=thread_id, turn_id=turn_id)
                notification_status = str(dict(notification or {}).get("status") or "").strip().lower()
                profile = dict(execution.get("profile") or {})
                runtime_status = self._prepare_runtime(profile, require_secret=False)
                client = self._ensure_client(runtime_status)
                if notification_status in TERMINAL_TURN_STATUSES:
                    terminal_thread = self._wait_for_probe_turn_terminal(
                        client,
                        thread_id=thread_id,
                        turn_id=turn_id,
                        timeout_seconds=5.0,
                        operation_label=f"task graph reconciliation for {node_id or turn_id}",
                    )
                    terminal_status, _final_text, _reasoning = self._probe_turn_result(
                        terminal_thread,
                        turn_id=turn_id,
                    )
                    record.update({"status": "terminal_observed", "terminal_status": terminal_status or notification_status})
                else:
                    self.interrupt_turn(profile, thread_id, turn_id)
                    terminal_thread = self._wait_for_probe_turn_terminal(
                        client,
                        thread_id=thread_id,
                        turn_id=turn_id,
                        timeout_seconds=5.0,
                        operation_label=f"task graph cancellation for {node_id or turn_id}",
                    )
                    terminal_status, _final_text, _reasoning = self._probe_turn_result(
                        terminal_thread,
                        turn_id=turn_id,
                    )
                    record.update({"status": "interrupted", "terminal_status": terminal_status or "unknown"})
                committed_status = self._commit_graph_live_reconciled_execution_result(
                    graph=graph,
                    run_id=run_id,
                    execution=execution,
                    terminal_thread=terminal_thread,
                    node_states=node_states,
                    event_refs=event_refs,
                    artifact_refs=artifact_refs,
                )
                settled_execution_keys.add(execution_key)
                if committed_status:
                    record.update(
                        {
                            "status": "terminal_result_committed",
                            "terminal_status": committed_status,
                            "committed_output": True,
                        }
                    )
                elif node_id and node_id in node_states:
                    observed = str(record.get("terminal_status") or "").lower()
                    node_states[node_id].update(
                        {
                            "status": "cancelled" if observed == "cancelled" else "failed",
                            "outcome": "cancelled" if observed == "cancelled" else "failed",
                            "updated_at": now_iso(),
                            "turn_reconciliation": dict(record),
                        }
                    )
                if node_id and node_id in node_states and committed_status:
                    node_states[node_id]["turn_reconciliation"] = dict(record)
            except Exception as reconcile_exc:
                reconcile_error_type = type(reconcile_exc).__name__
                reconcile_error_message = str(redact_sensitive(str(reconcile_exc))).strip()[:400]
                recovered_commit_status: str | None = None
                try:
                    profile = dict(execution.get("profile") or {})
                    runtime_status = self._prepare_runtime(profile, require_secret=False)
                    client = self._ensure_client(runtime_status)
                    terminal_thread = self._wait_for_probe_turn_terminal(
                        client,
                        thread_id=thread_id,
                        turn_id=turn_id,
                        timeout_seconds=5.0,
                        operation_label=f"task graph recovery for {node_id or turn_id}",
                    )
                    recovered_commit_status = self._commit_graph_live_reconciled_execution_result(
                        graph=graph,
                        run_id=run_id,
                        execution=execution,
                        terminal_thread=terminal_thread,
                        node_states=node_states,
                        event_refs=event_refs,
                        artifact_refs=artifact_refs,
                    )
                except Exception:
                    recovered_commit_status = None
                if recovered_commit_status:
                    settled_execution_keys.add(execution_key)
                    record.update(
                        {
                            "status": "terminal_result_committed_after_reconcile_error",
                            "terminal_status": recovered_commit_status,
                            "committed_output": True,
                            "recovery_error_type": reconcile_error_type,
                            "recovery_error_message": reconcile_error_message,
                        }
                    )
                    if node_id and node_id in node_states:
                        node_states[node_id]["turn_reconciliation"] = dict(record)
                else:
                    record.update(
                        {
                            "status": "interrupt_failed",
                            "error_type": reconcile_error_type,
                            "message": reconcile_error_message,
                        }
                    )
                    if node_id and node_id in node_states:
                        node_states[node_id].update(
                            {
                                "status": "failed",
                                "outcome": "failed",
                                "updated_at": now_iso(),
                                "turn_reconciliation": dict(record),
                            }
                        )
            records.append(record)
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id or turn_id}-turn-reconciled",
                    "run_id": run_id,
                    "task_id": graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_progress",
                    "created_at": now_iso(),
                    "summary": (
                        f"{self._tasks._graph_node_label(graph, node_id) if node_id else turn_id} "
                        f"provider turn reconciliation finished as {record['status']}."
                    ),
                    "node_id": node_id or None,
                    "reconciliation_status": record["status"],
                }
            )
            reconciled_node_status = str(dict(node_states.get(node_id) or {}).get("status") or "").strip()
            if node_id and reconciled_node_status in {"cancelled", "failed"}:
                event_refs.append(
                    {
                        "event_id": f"{run_id}-{node_id}-reconciled-{reconciled_node_status}",
                        "run_id": run_id,
                        "task_id": graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_cancelled" if reconciled_node_status == "cancelled" else "node_failed",
                        "created_at": now_iso(),
                        "summary": (
                            f"{self._tasks._graph_node_label(graph, node_id)} finished failure reconciliation "
                            f"as {reconciled_node_status}."
                        ),
                        "node_id": node_id,
                    }
                )
            self._record_event(
                {
                    "type": "task_graph_turn_reconciled",
                    "graph_id": graph.get("graph_id"),
                    "run_id": run_id,
                    "node_id": node_id or None,
                    "thread_id": thread_id,
                    "turn_id": turn_id,
                    "status": record["status"],
                    "terminal_status": record.get("terminal_status"),
                }
            )
        return records

    def _commit_graph_live_reconciled_execution_result(
        self,
        *,
        graph: dict[str, Any],
        run_id: str,
        execution: dict[str, Any],
        terminal_thread: dict[str, Any],
        node_states: dict[str, dict[str, Any]],
        event_refs: list[dict[str, Any]],
        artifact_refs: list[dict[str, Any]],
    ) -> str | None:
        node_id = str(execution.get("node_id") or "").strip()
        if not node_id or node_id not in node_states:
            return None
        graph_id = str(graph.get("graph_id") or "").strip()
        graph_node = dict(execution.get("graph_node") or {})
        profile = dict(execution.get("profile") or {})
        worker = dict(execution.get("worker") or {})
        turn_id = str(execution.get("turn_id") or "").strip()
        thread_status, final_text, reasoning_text = self._probe_turn_result(terminal_thread, turn_id=turn_id)
        thread_status = str(thread_status or "").strip().lower()
        if thread_status not in TERMINAL_TURN_STATUSES:
            return None
        finished_at = now_iso()
        attempt_count = max(1, int(execution.get("attempt_count") or 1))
        execution_thread_id = str(execution.get("execution_thread_id") or "").strip()
        attempt_operation_id = str(execution.get("attempt_operation_id") or "").strip()
        if execution_thread_id and turn_id:
            completion_inbox_key = self._graph_live_completion_inbox_key(
                run_id=run_id,
                node_id=node_id,
                attempt=attempt_count,
                execution_thread_id=execution_thread_id,
                turn_id=turn_id,
            )
            self._tasks.durable_run_store().record_inbox(
                completion_inbox_key,
                run_id=run_id,
                event_id=f"{run_id}-{node_id}-terminal-{attempt_count}",
                payload={"node_id": node_id, "attempt_count": attempt_count},
            )
        if attempt_operation_id:
            self._tasks.durable_run_store().record_external_operation(
                attempt_operation_id,
                run_id,
                kind="provider_turn_start",
                classification="non_idempotent_write",
                status="completed",
                external_handle=f"{execution_thread_id}:{turn_id}" if execution_thread_id and turn_id else None,
                payload={"node_id": node_id, "attempt_count": attempt_count},
            )
            self._tasks.durable_run_store().update_outbox_status(
                attempt_operation_id,
                status="completed",
                payload={"node_id": node_id, "attempt_count": attempt_count},
            )
        elapsed_ms = max(
            0,
            int((time.monotonic() - float(execution.get("started_monotonic") or time.monotonic())) * 1000),
        )
        usage_signal = self._graph_live_turn_usage_signal(
            thread_id=str(execution.get("execution_thread_id") or ""),
            turn_id=turn_id,
            provider_id=str(profile.get("provider_id") or "").strip() or None,
            model=str(graph_node.get("model_id") or profile.get("model") or "").strip() or None,
        )
        policy_violation = self._turn_execution_policy_violation(
            thread_id=str(execution.get("execution_thread_id") or ""),
            turn_id=turn_id,
        )
        token_budget = int(execution.get("token_budget") or 0)
        observed_tokens = dict(usage_signal.get("tokens") or {}).get("total_tokens")
        budget_exceeded = (
            token_budget > 0
            and isinstance(observed_tokens, int)
            and observed_tokens > token_budget
        )
        parsed_output = self._graph_live_run_parse_response(final_text)
        terminal_outcome = self._graph_live_run_terminal_outcome(
            node_label=self._tasks._graph_node_label(graph, node_id),
            thread_status=thread_status,
            final_text=final_text,
            reasoning_text=reasoning_text,
            parsed_output=parsed_output,
            policy_violation=policy_violation,
            budget_exceeded=budget_exceeded,
            observed_tokens=observed_tokens,
            token_budget=token_budget,
        )
        node_status = str(terminal_outcome.get("node_status") or "failed")
        outcome = str(terminal_outcome.get("outcome") or "failed")
        summary = str(terminal_outcome.get("summary") or "").strip() or (
            f"{self._tasks._graph_node_label(graph, node_id)} finished with status {thread_status or 'failed'}."
        )
        output_human_summary = str(terminal_outcome.get("output_human_summary") or "").strip()
        machine_result = dict(terminal_outcome.get("machine_result") or {})
        contract_failure = None
        if node_status == "completed":
            contract_failure = self._graph_live_validate_machine_result_contract(
                graph=graph,
                node_id=node_id,
                node_label=self._tasks._graph_node_label(graph, node_id),
                machine_result=machine_result,
            )
        if isinstance(contract_failure, dict):
            node_status = str(contract_failure.get("node_status") or "failed")
            outcome = str(contract_failure.get("outcome") or "schema_violation")
            summary = str(contract_failure.get("summary") or "").strip() or summary
            output_human_summary = str(contract_failure.get("output_human_summary") or "").strip()
            machine_result = dict(contract_failure.get("machine_result") or {})
            terminal_outcome["next_action_hints"] = list(contract_failure.get("next_action_hints") or [])
        effective_policy_violation = dict(terminal_outcome.get("policy_violation") or {}) or None
        next_action_hints = [
            str(item).strip()
            for item in list(terminal_outcome.get("next_action_hints") or [])
            if str(item or "").strip()
        ]
        node_states[node_id].update(
            {
                "status": node_status,
                "outcome": outcome,
                "updated_at": finished_at,
                "elapsed_ms": elapsed_ms,
                "provider_call_count": 1,
                "tool_call_count": int(dict(effective_policy_violation or {}).get("blocked_tool_call_count") or 0),
                "execution_policy": effective_policy_violation,
                "usage_signal": usage_signal,
                "token_budget": token_budget or None,
            }
        )
        worker_output_payload = {
            "graph_id": graph_id,
            "run_id": run_id,
            "node_id": node_id,
            "worker_thread_id": str(worker.get("thread_id") or ""),
            "human_summary": output_human_summary,
            "machine_result": machine_result,
            "next_action_hints": next_action_hints,
            "status": node_status,
            "provider_id": str(profile.get("provider_id") or "").strip() or None,
            "model": str(graph_node.get("model_id") or profile.get("model") or "").strip() or None,
            "provider_call_count": 1,
            "tool_call_count": int(dict(effective_policy_violation or {}).get("blocked_tool_call_count") or 0),
            "execution_policy": effective_policy_violation,
            "usage_signal": usage_signal,
            "elapsed_ms": elapsed_ms,
            "attempt_count": 1,
            "updated_at": finished_at,
        }
        try:
            worker_output = self._tasks.record_graph_worker_output(
                worker_output_payload,
                graph_definition=graph,
            )
        except GraphContractValidationError as exc:
            node_status = "failed"
            outcome = "handoff_contract_violation"
            summary = f"{self._tasks._graph_node_label(graph, node_id)} produced output that violated the live handoff contract."
            machine_result = {
                "status": "handoff_contract_violation",
                "error": str(exc),
            }
            next_action_hints = [
                "Fix the source node output or edge port bindings before rerunning this graph."
            ]
            node_states[node_id].update(
                {
                    "status": node_status,
                    "outcome": outcome,
                    "updated_at": finished_at,
                }
            )
            worker_output_payload.update(
                {
                    "human_summary": "",
                    "machine_result": machine_result,
                    "next_action_hints": next_action_hints,
                    "status": node_status,
                }
            )
            worker_output = self._tasks.record_graph_worker_output(
                worker_output_payload,
                graph_definition=graph,
            )
        binding = dict(worker_output.get("worker_binding") or {})
        merged_artifact_refs = self._tasks._merge_graph_worker_artifact_refs(
            artifact_refs,
            [dict(item) for item in list(binding.get("artifact_refs") or []) if isinstance(item, dict)],
        )
        artifact_refs[:] = merged_artifact_refs
        event_refs.append(
            {
                "event_id": f"{run_id}-{node_id}-recovered-{node_status}",
                "run_id": run_id,
                "task_id": graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": (
                    "node_completed" if node_status == "completed" else ("node_cancelled" if node_status == "cancelled" else "node_failed")
                ),
                "created_at": finished_at,
                "summary": summary,
                "node_id": node_id,
            }
        )
        return node_status

    def _finalize_graph_live_run_failure(
        self,
        *,
        exc: Exception,
        graph: dict[str, Any],
        run_id: str,
        workspace_root: Path,
        artifact_root: Path,
        summary_json_path: Path,
        report_md_path: Path,
        run_manifest_path: Path,
        run_manifest: dict[str, Any],
        live_run_ref: dict[str, Any],
        node_states: dict[str, dict[str, Any]],
        event_refs: list[dict[str, Any]],
        artifact_refs: list[dict[str, Any]],
        active_node_id: str | None,
        reconciliation_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        persisted_ref = dict(self._tasks.graph_run_ref(run_id) or live_run_ref or {})
        persisted_status = str(persisted_ref.get("status") or "").strip().lower()
        if persisted_status in {"cancelled", "completed", "failed"}:
            self._record_event(
                {
                    "type": "task_graph_live_run_failure_finalization_skipped",
                    "run_id": run_id,
                    "persisted_status": persisted_status,
                    "error_type": type(exc).__name__,
                }
            )
            return {
                "run_ref": persisted_ref,
                "artifact_paths": {},
                "failure_kind": "already_terminal",
            }

        failed_at = now_iso()
        failure_kind = "terminal_collection_timeout" if isinstance(exc, TimeoutError) else "runtime_error"
        failure_message = str(redact_sensitive(str(exc))).strip()[:600] or type(exc).__name__
        active_node = str(active_node_id or "").strip()
        for node_id, state in node_states.items():
            current_status = str(state.get("status") or "").strip().lower()
            if current_status in {"completed", "failed", "cancelled", "blocked"}:
                continue
            if node_id == active_node or current_status == "running":
                state.update({"status": "failed", "outcome": "failed", "updated_at": failed_at})
                event_refs.append(
                    {
                        "event_id": f"{run_id}-{node_id}-runtime-failed",
                        "run_id": run_id,
                        "task_id": graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_failed",
                        "created_at": failed_at,
                        "summary": f"{self._tasks._graph_node_label(graph, node_id)} stopped because live runtime collection failed.",
                        "node_id": node_id,
                    }
                )
                continue
            state.update({"status": "blocked", "outcome": "blocked", "updated_at": failed_at})
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-runtime-blocked",
                    "run_id": run_id,
                    "task_id": graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_blocked",
                    "created_at": failed_at,
                    "summary": f"{self._tasks._graph_node_label(graph, node_id)} did not run after an upstream runtime failure.",
                    "node_id": node_id,
                }
            )

        event_refs.append(
            {
                "event_id": f"{run_id}-runtime-failed",
                "run_id": run_id,
                "task_id": graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": "run_failed",
                "created_at": failed_at,
                "summary": f"{graph['title']} live task-graph run failed during runtime result collection.",
            }
        )
        failure_path = artifact_root / "failure.json"
        failure_payload = {
            "schema_version": "astrabridge-task-graph-live-run-failure-v1",
            "run_id": run_id,
            "graph_id": graph["graph_id"],
            "task_id": graph["task_id"],
            "failed_at": failed_at,
            "failure_kind": failure_kind,
            "error_type": type(exc).__name__,
            "message": failure_message,
            "active_node_id": active_node or None,
            "turn_reconciliation": deepcopy(reconciliation_records),
            "recovery": {
                "action": "inspect_and_rerun",
                "safe_to_resume": False,
                "reason": "The terminal worker result was not committed to the graph run.",
            },
        }
        write_json(failure_path, failure_payload)
        summary_payload = {
            "schema_version": "astrabridge-task-graph-live-run-summary-v1",
            "run_id": run_id,
            "graph_id": graph["graph_id"],
            "task_id": graph["task_id"],
            "created_at": str(run_manifest.get("created_at") or failed_at),
            "updated_at": failed_at,
            "run_status": "failed",
            "failure": failure_payload,
            "node_results": [
                {
                    "node_id": node_id,
                    "label": self._tasks._graph_node_label(graph, node_id),
                    "status": str(state.get("status") or ""),
                    "outcome": str(state.get("outcome") or ""),
                }
                for node_id, state in node_states.items()
            ],
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
                "run_manifest_json": run_manifest_path.relative_to(workspace_root).as_posix(),
                "failure_json": failure_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, summary_payload)
        report_md_path.write_text(self._graph_live_run_report_markdown(summary_payload), encoding="utf-8")
        source_node_id = active_node or str((run_manifest.get("entry_node_ids") or [""])[0] or "")
        next_artifact_refs = self._tasks._merge_graph_worker_artifact_refs(
            artifact_refs,
            [
                {
                    "artifact_id": f"{run_id}-failure-json",
                    "artifact_kind": "diagnostic_bundle",
                    "task_id": graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": source_node_id,
                    "path": failure_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": failed_at,
                },
                {
                    "artifact_id": f"{run_id}-failure-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": source_node_id,
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": failed_at,
                },
                {
                    "artifact_id": f"{run_id}-failure-report-md",
                    "artifact_kind": "validation_report",
                    "task_id": graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": source_node_id,
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": failed_at,
                },
            ],
        )
        run_manifest.update(
            {
                "status": "failed",
                "updated_at": failed_at,
                "node_run_states": [deepcopy(item) for item in node_states.values()],
                "artifact_refs": deepcopy(next_artifact_refs),
                "event_refs": deepcopy(event_refs),
                "failure": failure_payload,
            }
        )
        write_json(run_manifest_path, run_manifest)
        failed_ref = self._graph_live_run_snapshot(
            run_ref=persisted_ref,
            node_states=node_states,
            event_refs=event_refs,
            artifact_refs=next_artifact_refs,
            policy_snapshot=dict(run_manifest.get("run_policy_snapshot") or {}),
            status="failed",
        )
        self._record_event(
            {
                "type": "task_graph_live_run_failed",
                "run_id": run_id,
                "graph_id": graph["graph_id"],
                "task_id": graph["task_id"],
                "failure_kind": failure_kind,
                "error_type": type(exc).__name__,
                "active_node_id": active_node or None,
            }
        )
        return {
            "run_ref": failed_ref,
            "artifact_paths": dict(summary_payload.get("artifact_paths") or {}),
            "failure_kind": failure_kind,
        }

    def _graph_live_run_snapshot(
        self,
        *,
        run_ref: dict[str, Any],
        node_states: dict[str, dict[str, Any]],
        event_refs: list[dict[str, Any]],
        artifact_refs: list[dict[str, Any]],
        policy_snapshot: dict[str, Any],
        status: str,
        approval_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = str(dict(run_ref or {}).get("run_id") or "").strip()
        persisted_run_ref = self._tasks.graph_run_ref(run_id) if run_id else None
        next_run_ref = {
            **dict(run_ref or {}),
            **dict(persisted_run_ref or {}),
        }
        next_run_ref["status"] = status
        next_run_ref["node_status_counts"] = {
            key: sum(1 for item in node_states.values() if str(item.get("status") or "").strip() == key)
            for key in sorted({str(item.get("status") or "").strip() for item in node_states.values() if str(item.get("status") or "").strip()})
        }
        next_run_ref["node_outcome_counts"] = {
            key: sum(1 for item in node_states.values() if str(item.get("outcome") or "").strip() == key)
            for key in sorted({str(item.get("outcome") or "").strip() for item in node_states.values() if str(item.get("outcome") or "").strip()})
        }
        next_run_ref["event_count"] = len(event_refs)
        next_run_ref["artifact_refs"] = self._tasks._merge_graph_worker_artifact_refs(
            list(next_run_ref.get("artifact_refs") or []),
            [dict(item) for item in artifact_refs if isinstance(item, dict)],
        )
        next_run_ref["artifact_count"] = len(list(next_run_ref.get("artifact_refs") or []))
        next_run_ref["diagnostic_refs"] = self._tasks._extract_graph_run_diagnostic_refs(
            {"artifact_refs": list(next_run_ref.get("artifact_refs") or [])}
        )
        next_run_ref["node_run_states"] = [deepcopy(item) for item in node_states.values()]
        next_run_ref["event_refs"] = [deepcopy(item) for item in event_refs]
        next_run_ref["timeline_events"] = self._tasks._compact_graph_run_timeline_events(event_refs)
        next_run_ref["latest_event_type"] = str(dict(event_refs[-1]).get("event_type") or "").strip() if event_refs else None
        next_run_ref["latest_event_at"] = str(dict(event_refs[-1]).get("created_at") or "").strip() if event_refs else None
        next_run_ref["updated_at"] = str(next_run_ref.get("latest_event_at") or now_iso())
        next_run_ref["policy_snapshot"] = redact_sensitive(dict(policy_snapshot or {}))
        next_run_ref["approval_state"] = str(dict(approval_state or {}).get("status") or "not_required").strip() or "not_required"
        next_run_ref["approval_details"] = self._tasks._compact_graph_run_approval_state(approval_state or {"status": "not_required"})
        return dict(self._tasks.persist_graph_run_ref(next_run_ref).get("run_ref") or next_run_ref)

    def _write_graph_live_run_manifest_snapshot(
        self,
        *,
        run_manifest_path: Path,
        run_manifest: dict[str, Any],
        node_states: dict[str, dict[str, Any]],
        artifact_refs: list[dict[str, Any]],
        event_refs: list[dict[str, Any]],
        status: str,
        updated_at: str | None = None,
        approval_state: dict[str, Any] | None = None,
    ) -> None:
        manifest_updated_at = (
            str(updated_at or "").strip()
            or str(dict(event_refs[-1]).get("created_at") or "").strip()
            or now_iso()
        )
        run_manifest["status"] = status
        run_manifest["updated_at"] = manifest_updated_at
        run_manifest["node_run_states"] = [deepcopy(item) for item in node_states.values()]
        run_manifest["artifact_refs"] = deepcopy(artifact_refs)
        run_manifest["event_refs"] = deepcopy(event_refs)
        run_manifest["approval_state"] = deepcopy(dict(approval_state or run_manifest.get("approval_state") or {"status": "not_required"}))
        run_id = str(run_manifest.get("run_id") or "").strip()
        latest_run_ref = self._tasks.graph_run_ref(run_id) if self._tasks is not None and run_id else None
        if isinstance(latest_run_ref, dict) and latest_run_ref.get("worker_bindings"):
            run_manifest["worker_bindings"] = [
                deepcopy(dict(item))
                for item in list(latest_run_ref.get("worker_bindings") or [])
                if isinstance(item, dict)
            ]
        write_json(run_manifest_path, run_manifest)

    @staticmethod
    def _graph_live_run_report_markdown(summary_payload: dict[str, Any]) -> str:
        lines = [
            f"# {str(summary_payload.get('graph_id') or '').strip()}",
            "",
            f"- Run ID: {str(summary_payload.get('run_id') or '').strip()}",
            f"- Status: {str(summary_payload.get('run_status') or '').strip()}",
            "",
            "## Nodes",
            "",
        ]
        for item in list(summary_payload.get("node_results") or []):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {str(item.get('label') or item.get('node_id') or '').strip()}: "
                f"{str(item.get('status') or '').strip()} / {str(item.get('outcome') or '').strip()}"
            )
        failure = dict(summary_payload.get("failure") or {})
        if failure:
            lines.extend(
                [
                    "",
                    "## Failure",
                    "",
                    f"- Kind: {str(failure.get('failure_kind') or 'runtime_error').strip()}",
                    f"- Active node: {str(failure.get('active_node_id') or 'unknown').strip()}",
                    f"- Message: {str(failure.get('message') or 'Live runtime collection failed.').strip()}",
                ]
            )
        lines.append("")
        return "\n".join(lines)

    def _graph_worker_timeout_ms(self, value: Any) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return value if value > 0 else 0
        try:
            parsed = int(str(value or "").strip() or "0")
        except Exception:
            return 0
        return parsed if parsed > 0 else 0

    def _normalize_graph_worker_subagent_policy(
        self,
        value: dict[str, Any],
        *,
        node_id: str,
        spawn_mode: str,
    ) -> dict[str, Any]:
        defaults = {
            "isolation_mode": "lane",
            "max_turns": 8,
            "allow_direct_teammate_messages": False,
            "share_worktree": False,
            "allow_nested_subagents": False,
        }
        if spawn_mode != "subagent_worker":
            return defaults
        policy = {
            "isolation_mode": str(value.get("isolation_mode") or defaults["isolation_mode"]).strip().lower() or "lane",
            "max_turns": self._graph_worker_timeout_ms(value.get("max_turns")) or int(defaults["max_turns"]),
            "allow_direct_teammate_messages": bool(value.get("allow_direct_teammate_messages")),
            "share_worktree": bool(value.get("share_worktree")),
            "allow_nested_subagents": bool(value.get("allow_nested_subagents")),
        }
        if policy["max_turns"] <= 0:
            raise ValueError(f"Graph worker {node_id} requires a positive subagent max_turns value.")
        isolation_mode = str(policy.get("isolation_mode") or "lane")
        if isolation_mode not in {"lane", "worktree"}:
            raise ValueError(f"Graph worker {node_id} requested unsupported isolation_mode={isolation_mode}.")
        if bool(policy.get("allow_nested_subagents")):
            raise ValueError(f"Graph worker {node_id} requested nested subagents, which are not supported yet.")
        if bool(policy.get("share_worktree")) or isolation_mode == "worktree":
            raise ValueError(f"Graph worker {node_id} requested worktree isolation, which is not supported yet.")
        return policy

    def _graph_worker_tool_policy(
        self,
        value: dict[str, Any],
        *,
        node: dict[str, Any] | None = None,
        graph_policy: dict[str, Any] | None = None,
        node_id: str | None = None,
        mcp_tool_policy_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        allowed_tool_classes = [
            str(item).strip()
            for item in list(value.get("allowed_tool_classes") or [])
            if str(item or "").strip()
        ]
        mcp_tool_policy = (
            deepcopy(mcp_tool_policy_snapshot)
            if isinstance(mcp_tool_policy_snapshot, dict) and mcp_tool_policy_snapshot
            else resolve_node_mcp_tool_policy(
                tools=value,
                mcp_preset_ids=[
                    str(item).strip()
                    for item in list(dict(node or {}).get("mcp_preset_ids") or [])
                    if str(item or "").strip()
                ],
                graph_policy=graph_policy,
                enabled_servers=self._enabled_mcp_servers_snapshot(),
                node_id=str(node_id or dict(node or {}).get("node_id") or "").strip() or None,
            )
        )
        return {
            "approval_mode": str(value.get("approval_mode") or "").strip().lower() or "ask",
            "allowed_tool_classes": allowed_tool_classes,
            "supports_mcp": bool(value.get("supports_mcp")),
            "mcp_tool_policy": mcp_tool_policy,
        }

    def _enabled_mcp_servers_snapshot(self) -> list[dict[str, Any]]:
        try:
            return [dict(item) for item in self._mcp_config.enabled_servers() if isinstance(item, dict)]
        except Exception:
            return []

    @staticmethod
    def _graph_worker_dynamic_tool_filter(tool_policy: dict[str, Any]) -> tuple[set[str] | None, bool]:
        mcp_tool_policy = dict(tool_policy.get("mcp_tool_policy") or {})
        allowed_mcp_tools = allowed_mcp_dynamic_tool_names(mcp_tool_policy)
        supports_mcp = bool(tool_policy.get("supports_mcp")) or bool(allowed_mcp_tools)
        allow_browser_smoke = "web" in {
            str(item).strip()
            for item in list(tool_policy.get("allowed_tool_classes") or [])
            if str(item or "").strip()
        }
        if not supports_mcp:
            return set(), allow_browser_smoke
        return allowed_mcp_tools, allow_browser_smoke

    def _graph_node_mcp_tool_policy_snapshots(
        self,
        *,
        graph: dict[str, Any],
        compiled_plan: dict[str, Any],
    ) -> dict[str, Any]:
        graph_policy = dict(graph.get("graph_policy") or {})
        compiled_tool_policies = {
            str(item.get("node_id") or "").strip(): deepcopy(dict(dict(item.get("tool_policy") or {}).get("mcp_tool_policy") or {}))
            for item in list(compiled_plan.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        snapshots: dict[str, Any] = {}
        for node in list(graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or "").strip()
            if not node_id:
                continue
            snapshots[node_id] = deepcopy(
                dict(
                    self._graph_worker_tool_policy(
                        dict(node.get("tools") or {}),
                        node=node,
                        graph_policy=graph_policy,
                        node_id=node_id,
                        mcp_tool_policy_snapshot=compiled_tool_policies.get(node_id),
                    ).get("mcp_tool_policy")
                    or {}
                )
            )
        return snapshots

    @staticmethod
    def _graph_worker_turn_execution_policy(tool_policy: dict[str, Any]) -> str:
        allowed_tool_classes = [
            str(item).strip()
            for item in list(tool_policy.get("allowed_tool_classes") or [])
            if str(item or "").strip()
        ]
        has_mcp_tools = bool(tool_policy.get("supports_mcp")) or bool(
            list(dict(tool_policy.get("mcp_tool_policy") or {}).get("exposed_tools") or [])
        )
        if not allowed_tool_classes and not has_mcp_tools:
            return NO_TOOLS_EXECUTION_POLICY
        return "standard"

    def _graph_worker_runtime_contract(
        self,
        *,
        profile: dict[str, Any],
        node: dict[str, Any],
        model: Any,
        effort: Any,
        permission_mode: str,
        collaboration_mode: str | None,
        execution_backend: str | None,
        timeout_ms: int,
        spawn_mode: str,
        subagent_policy: dict[str, Any],
        tool_policy: dict[str, Any],
    ) -> dict[str, Any]:
        mcp_preset_ids = [
            str(item).strip()
            for item in list(node.get("mcp_preset_ids") or [])
            if str(item or "").strip()
        ]
        skill_ids = [
            str(item).strip()
            for item in list(node.get("skill_ids") or node.get("skills") or [])
            if str(item or "").strip()
        ]
        return {
            "profile_id": str(profile.get("profile_id") or "").strip(),
            "provider_id": str(profile.get("provider_id") or "").strip(),
            "model": str(model or "").strip(),
            "reasoning_effort": str(effort or "").strip(),
            "permission_mode": permission_mode,
            "collaboration_mode": collaboration_mode or "default",
            "execution_backend": self._normalize_execution_backend(execution_backend or profile.get("execution_backend")),
            "spawn_mode": spawn_mode,
            "timeout_ms": timeout_ms,
            "tool_policy": tool_policy,
            "turn_execution_policy": self._graph_worker_turn_execution_policy(tool_policy),
            "subagent_policy": subagent_policy,
            "mcp_preset_ids": mcp_preset_ids,
            "skill_ids": skill_ids,
            "prompt_template_mode": str(dict(node.get("prompt") or {}).get("template_mode") or "").strip(),
        }

    def archive_thread(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        client.request("thread/archive", {"threadId": thread_id})
        if (self._projects.current_project or {}).get("current_thread_id") == thread_id:
            self._projects.switch_thread(None)
        self._mark_provider_thread_missing(thread_id, reason="thread_archived")
        self._record_event({"type": "thread_archived", "thread_id": thread_id, "runtime": runtime_status})
        return {"archived": thread_id}

    def update_thread_defaults(
        self,
        *,
        thread_id: str,
        profile_id: str | None,
        model: str | None,
        effort: str | None,
        permission_mode: str | None,
        collaboration_mode: str | None = None,
    ) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        normalized = self._normalize_shell_settings(
            {
                "profile_id": profile_id,
                "model": model,
                "reasoning_effort": effort,
                "permission_mode": permission_mode,
                "collaboration_mode": collaboration_mode,
            },
            current_project=self._projects.current_project or {},
            prefer_project_defaults=False,
        )
        self._cache_thread_entry(
            thread_id,
            {
                "profile_id": normalized.get("profile_id"),
                "model": normalized.get("model"),
                "reasoning_effort": normalized.get("reasoning_effort"),
                "permission_mode": normalized.get("permission_mode"),
                "collaboration_mode": normalized.get("collaboration_mode"),
            },
        )
        if normalized.get("profile_id") or normalized.get("model") or normalized.get("reasoning_effort"):
            self._projects.update_project(
                {
                    **({"default_profile_id": normalized.get("profile_id")} if normalized.get("profile_id") else {}),
                    **({"default_model": normalized.get("model")} if normalized.get("model") else {}),
                    **({"default_effort": normalized.get("reasoning_effort")} if normalized.get("reasoning_effort") else {}),
                }
            )
        return self._thread_settings_for(thread_id)

    def get_goal(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        active_runtime = self._active_runtime_status()
        if active_runtime.get("configured") and self._profile_targets_different_runtime(profile, active_runtime):
            self._record_event(
                {
                    "type": "goal_read_deferred_active_runtime",
                    "thread_id": thread_id,
                    "profile_id": profile.get("profile_id"),
                    "active_provider_id": active_runtime.get("provider_id"),
                }
            )
            return {"goal": None, "warning": "goal_read_deferred_active_runtime"}
        runtime_status = self._runtime_status_for_profile(profile, require_secret=False)
        self._refresh_client_if_runtime_changed(runtime_status)
        client = self._ensure_client(runtime_status)
        try:
            result = client.request("thread/goal/get", {"threadId": thread_id})
        except Exception as exc:
            if self._is_thread_not_found_error(exc):
                self._mark_provider_thread_missing(thread_id, reason="goal_thread_missing")
                self._record_event(
                    {
                        "type": "goal_thread_missing",
                        "thread_id": thread_id,
                        "profile_id": profile.get("profile_id"),
                    }
                )
                fallback_goal = None
                if self._tasks is not None:
                    try:
                        fallback_goal = (self._tasks.current_task() or {}).get("goal")
                    except Exception:
                        fallback_goal = None
                return {"goal": fallback_goal, "status": "thread_missing", "thread_id": thread_id}
            raise
        return {"goal": self._goal_with_local_state(thread_id, result.get("goal"))}

    def _local_goal_state(self, thread_id: str) -> dict[str, Any] | None:
        if self._tasks is None:
            return None
        try:
            task = self._tasks.current_task() or {}
        except Exception:
            return None
        goal = task.get("goal")
        if not isinstance(goal, dict):
            return None
        goal_thread_id = str(goal.get("threadId") or goal.get("thread_id") or task.get("active_provider_thread_id") or "").strip()
        if goal_thread_id and goal_thread_id != thread_id:
            return None
        return goal

    def _goal_with_local_state(self, thread_id: str, goal: Any) -> Any:
        if not isinstance(goal, dict):
            return goal
        local_goal = self._local_goal_state(thread_id)
        if not isinstance(local_goal, dict):
            return goal
        merged = dict(goal)
        for key in ("status", "tokenBudget", "tokensUsed", "timeUsedSeconds", "updatedAt"):
            if key in local_goal and local_goal.get(key) is not None:
                merged[key] = local_goal.get(key)
        merged["threadId"] = thread_id
        return merged

    def set_goal(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        objective: str,
        token_budget: int | None,
        status: str | None = None,
    ) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        payload = {"threadId": thread_id, "objective": objective, "tokenBudget": token_budget}
        if status:
            payload["status"] = status
        client.request(
            "thread/goal/set",
            payload,
        )
        if self._tasks is not None:
            self._tasks.record_goal(
                thread_id,
                {
                    "threadId": thread_id,
                    "objective": objective,
                    "tokenBudget": token_budget,
                    "updatedAt": int(time.time()),
                    **({"status": status} if status else {}),
                },
            )
        self._record_event({"type": "goal_set", "thread_id": thread_id, "token_budget": token_budget, **({"status": status} if status else {})})
        return self.get_goal(profile, thread_id)

    def clear_goal(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        client.request("thread/goal/clear", {"threadId": thread_id})
        if self._tasks is not None:
            self._tasks.record_goal(thread_id, None)
        self._record_event({"type": "goal_cleared", "thread_id": thread_id})
        return {"goal": None}

    def _build_turn_transition_for_start(
        self,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        execution_backend: str | None,
        context_mode: str,
        transition_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the secret-free admission record before a lane can start.

        The local action ledger is intentionally queried by lineage instead of
        by the next provider's tool-call ID: a fallback provider must not be
        able to make an interrupted source action look new merely by assigning
        a different call ID.
        """

        source_settings = self._task_thread_entry(source_thread_id)
        if not source_settings and source_thread_id:
            try:
                source_settings = self._thread_settings_for(source_thread_id)
            except Exception:  # noqa: BLE001 - transition admission stays conservative without cache metadata
                source_settings = {}
        task_id = ""
        if self._tasks is not None:
            try:
                task_id = str((self._tasks.current_task() or {}).get("task_id") or "").strip()
            except Exception:  # noqa: BLE001 - no task ownership means no extra receipt narrowing
                task_id = ""
        target_model = str(model or profile.get("model") or "").strip()
        target_provider = str(profile.get("provider_id") or source_settings.get("provider_id") or "").strip().lower()
        target_backend = self._normalize_execution_backend(execution_backend or profile.get("execution_backend"))
        source = {
            "thread_id": source_thread_id,
            "profile_id": source_settings.get("profile_id") or profile.get("profile_id"),
            "provider_id": source_settings.get("provider_id") or target_provider,
            "model_id": source_settings.get("model") or target_model,
            "reasoning_effort": source_settings.get("reasoning_effort") or effort or profile.get("reasoning_effort"),
            "execution_backend": source_settings.get("execution_backend") or target_backend,
        }
        target = {
            "thread_id": None,
            "profile_id": profile.get("profile_id"),
            "provider_id": target_provider,
            "model_id": target_model,
            "reasoning_effort": effort or profile.get("reasoning_effort"),
            "execution_backend": target_backend,
        }
        receipt_references: list[dict[str, Any]] = []
        receipt_reader = getattr(self._project_tools, "tool_action_receipts_for_lineage", None)
        if callable(receipt_reader):
            try:
                result = receipt_reader(
                    task_id=task_id or None,
                    visible_thread_id=source_thread_id or None,
                    execution_thread_id=source_thread_id or None,
                )
                receipt_references = [dict(item) for item in list(result or []) if isinstance(item, dict)]
            except Exception as exc:  # noqa: BLE001 - unreadable durable receipt state fails closed
                self._record_event(
                    {
                        "type": "turn_transition_receipt_query_failed",
                        "thread_id": source_thread_id,
                        "error_type": type(exc).__name__,
                    }
                )
                receipt_references = [
                    {
                        "receipt_id": "receipt-ledger-unavailable",
                        "idempotency_key": "ledger-unavailable",
                        "action_id": "action-ledger-unavailable",
                        "tool_name": "unknown",
                        "state": "recovery_required",
                        "recovery_required": True,
                        "lineage": {
                            "task_id": task_id or None,
                            "visible_thread_id": source_thread_id or None,
                            "execution_thread_id": source_thread_id or None,
                            "turn_id": None,
                            "tool_call_id": None,
                        },
                    }
                ]
        context = dict(transition_context or {})
        failure_notice = context.get("failure_notice")
        if not isinstance(failure_notice, dict):
            failure_notice = context.get("failure") if isinstance(context.get("failure"), dict) else None
        return build_turn_transition(
            source=source,
            target=target,
            trigger=str(context.get("trigger") or "turn_start"),
            failure_notice=dict(failure_notice or {}),
            receipt_references=receipt_references,
            target_route=self._turn_transition_target_route(
                provider_id=target_provider,
                model_id=target_model,
                execution_backend=target_backend,
            ),
            context_mode=context_mode,
            retry={
                "attempt_count": context.get("attempt_count"),
                "delay_seconds": context.get("retry_delay_seconds"),
                "retry_policy": context.get("retry_policy"),
            },
        )

    def _turn_transition_target_route(
        self,
        *,
        provider_id: str,
        model_id: str,
        execution_backend: str,
    ) -> dict[str, Any]:
        route = {
            "provider_id": provider_id,
            "model_id": model_id,
            "execution_backend": execution_backend,
            "admission": "not_recorded",
            "verification_status": "not_recorded",
            "accepted": True,
            "basis": "runtime_configuration_observed",
        }
        if self._router_config is None or not provider_id or not model_id:
            return route
        try:
            configured = next(
                (
                    dict(item)
                    for item in self._router_config.models()
                    if str(item.get("id") or "").strip() == f"{provider_id}/{model_id}"
                    or (
                        str(item.get("provider") or item.get("provider_id") or "").strip().lower() == provider_id
                        and str(item.get("native_model") or "").strip() == model_id
                    )
                ),
                None,
            )
        except Exception as exc:  # noqa: BLE001 - route metadata remains advisory when unavailable
            self._record_event(
                {
                    "type": "turn_transition_route_lookup_failed",
                    "provider_id": provider_id,
                    "model": model_id,
                    "error_type": type(exc).__name__,
                }
            )
            return route
        if not configured:
            return route
        admission = str(configured.get("execution_route_status") or "not_recorded").strip()
        verification = str(configured.get("execution_route_verification_status") or "not_recorded").strip()
        # Step 8 records configured admission without promoting a review-only
        # route to a stronger claim.  Only an explicit configured block stops a
        # lane here; broader runtime-route enforcement remains its own step.
        explicit_block = admission.lower() in {"blocked", "disabled", "rejected", "unavailable"}
        return {
            **route,
            "admission": admission,
            "verification_status": verification,
            "accepted": not explicit_block,
            "basis": "configured_execution_route",
        }

    def _assert_turn_transition_admitted(
        self,
        transition: dict[str, Any],
        *,
        source_thread_id: str,
        phase: str,
    ) -> None:
        try:
            assert_turn_transition_admitted(transition)
        except RuntimeError:
            self._record_event(
                {
                    "type": "turn_transition_blocked",
                    "thread_id": source_thread_id,
                    "phase": phase,
                    "turn_transition": compact_turn_transition(transition),
                }
            )
            raise
        if bool(transition.get("record_required")):
            self._record_event(
                {
                    "type": "turn_transition_preflight",
                    "thread_id": source_thread_id,
                    "phase": phase,
                    "turn_transition": compact_turn_transition(transition),
                }
            )

    @staticmethod
    def _complete_turn_transition(
        transition: dict[str, Any] | None,
        *,
        target_thread_id: str,
        reused_existing: bool,
        completion_status: str,
    ) -> dict[str, Any] | None:
        if not isinstance(transition, dict):
            return None
        return complete_turn_transition(
            transition,
            target_thread_id=target_thread_id,
            reused_existing=reused_existing,
            completion_status=completion_status,
        )

    def start_turn(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        text: str,
        attachments: list[dict[str, Any]] | None,
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None = None,
        context_mode: str | None = None,
        execution_policy: str | None = None,
        token_budget: int | None = None,
        token_budget_objective: str | None = None,
        mcp_tool_policy_snapshot: dict[str, Any] | None = None,
        mcp_tool_policy_context: dict[str, Any] | None = None,
        transition_context: dict[str, Any] | None = None,
        confirm_route_degradation: bool = False,
    ) -> dict[str, Any]:
        if not getattr(self._runtime_operation_local, "in_start_turn", False):
            with self._runtime_operation_lock:
                self._runtime_start_turn_in_progress = True
                self._runtime_operation_local.in_start_turn = True
                try:
                    return self.start_turn(
                        profile,
                        thread_id=thread_id,
                        text=text,
                        attachments=attachments,
                        model=model,
                        effort=effort,
                        permission_mode=permission_mode,
                        collaboration_mode=collaboration_mode,
                        context_mode=context_mode,
                        execution_policy=execution_policy,
                        token_budget=token_budget,
                        token_budget_objective=token_budget_objective,
                        mcp_tool_policy_snapshot=mcp_tool_policy_snapshot,
                        mcp_tool_policy_context=mcp_tool_policy_context,
                        transition_context=transition_context,
                        confirm_route_degradation=confirm_route_degradation,
                    )
                finally:
                    self._runtime_operation_local.in_start_turn = False
                    self._runtime_start_turn_in_progress = False
        requested_thread_id = self._resolve_requested_thread_id(thread_id.strip() or self._visible_task_thread_id_hint())
        if not requested_thread_id:
            raise ValueError("thread_id is required.")
        normalized_context_mode = self._normalize_context_mode(context_mode)
        normalized_execution_policy = self._normalize_turn_execution_policy(execution_policy)
        profile, route_admission = self._admit_runtime_route(
            profile,
            thread_id=requested_thread_id,
            model=model,
            effort=effort,
            permission_mode=permission_mode,
            execution_policy=normalized_execution_policy,
            context_mode=normalized_context_mode,
            attachments=attachments,
            confirm_degradation=confirm_route_degradation,
        )
        self._assert_runtime_route_admitted(route_admission, operation="turn_start", thread_id=requested_thread_id)
        model = str(profile.get("model") or model or "").strip() or None
        effective_admission = dict(route_admission.get("effective") or {})
        if str(effective_admission.get("reasoning_effort") or "").strip():
            effort = str(effective_admission.get("reasoning_effort") or "").strip()
        normalized_execution_policy = self._normalize_turn_execution_policy(
            str(effective_admission.get("execution_policy") or normalized_execution_policy)
        )
        allowed_mcp_tool_names = None
        allow_browser_smoke = True
        if isinstance(mcp_tool_policy_snapshot, dict) and mcp_tool_policy_snapshot:
            allowed_mcp_tool_names = allowed_mcp_dynamic_tool_names(mcp_tool_policy_snapshot)
            allow_browser_smoke = "web" in {
                str(item).strip()
                for item in list(dict(mcp_tool_policy_snapshot).get("allowed_tool_classes") or [])
                if str(item or "").strip()
            }
        effective_permission_mode = str(
            effective_admission.get("permission_mode")
            or ("ask" if normalized_execution_policy == NO_TOOLS_EXECUTION_POLICY else permission_mode)
            or "ask"
        ).strip()
        execution_backend = self._thread_execution_backend(requested_thread_id, profile)
        if normalized_execution_policy == PATCH_ONLY_EXECUTION_POLICY and not self._supports_patch_only_execution_policy(profile, execution_backend):
            self._record_event(
                {
                    "type": "turn_execution_policy_rejected",
                    "thread_id": requested_thread_id,
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "policy": normalized_execution_policy,
                    "reason": "verified_native_apply_patch_only_enforcement_unavailable",
                }
            )
            raise ValueError(
                "Patch-only execution is unavailable for this runtime. AstraBridge blocked the turn rather than silently allowing shell edits. "
                "Use Standard execution with approvals, or choose a runtime that advertises verified native patch-only enforcement."
            )
        turn_transition = self._build_turn_transition_for_start(
            source_thread_id=requested_thread_id,
            profile=profile,
            model=model,
            effort=effort,
            execution_backend=execution_backend,
            context_mode=normalized_context_mode,
            transition_context=transition_context,
        )
        self._assert_turn_transition_admitted(
            turn_transition,
            source_thread_id=requested_thread_id,
            phase="turn_start_preflight",
        )
        if execution_backend == "native_kernel":
            if token_budget is not None:
                raise ValueError(
                    "Token-budget-enforced task-graph turns require the App Server execution backend."
                )
            native_result = self._start_native_turn(
                profile,
                thread_id=requested_thread_id,
                text=text,
                attachments=attachments or [],
                model=model,
                effort=effort,
                permission_mode=effective_permission_mode,
                collaboration_mode=collaboration_mode,
                context_mode=normalized_context_mode,
                turn_transition=turn_transition,
            )
            return {**native_result, "route_admission": route_admission}
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        self._assert_attachment_route_supported(
            attachments or [],
            runtime_status=runtime_status,
            execution_backend=execution_backend,
            provider_id=str(profile.get("provider_id") or ""),
            model_id=str(model or profile.get("model") or ""),
        )
        client = self._ensure_client(runtime_status)

        def apply_turn_budget(active_client: AppServerClient, target_thread_id: str) -> None:
            if token_budget is None:
                return
            try:
                normalized_budget = int(token_budget)
            except (TypeError, ValueError) as exc:
                raise ValueError("token_budget must be a positive integer.") from exc
            if normalized_budget <= 0:
                raise ValueError("token_budget must be a positive integer.")
            objective = str(token_budget_objective or text).strip()[:500]
            if not objective:
                objective = "Bounded AstraBridge task-graph node execution"
            active_client.request(
                "thread/goal/set",
                {
                    "threadId": target_thread_id,
                    "objective": objective,
                    "tokenBudget": normalized_budget,
                },
            )
            self._record_event(
                {
                    "type": "turn_token_budget_set",
                    "thread_id": target_thread_id,
                    "token_budget": normalized_budget,
                    "objective_present": True,
                }
            )

        def prepare_effective_thread(active_client: AppServerClient) -> tuple[str, dict[str, Any] | None]:
            force_fresh_context_thread = normalized_context_mode in {"minimal_text", "minimal_visual", "no_context"} and self._tasks is not None
            if force_fresh_context_thread:
                desired = self._task_thread_settings(
                    profile,
                    model,
                    effort,
                    effective_permission_mode,
                    collaboration_mode=collaboration_mode,
                )
                reason = f"{normalized_context_mode}_fresh_thread"
                prepared_thread_id, prepared_handoff = self._start_fresh_provider_thread_for_turn(
                    active_client,
                    source_thread_id=requested_thread_id,
                    profile=profile,
                    model=model,
                    effort=effort,
                    permission_mode=effective_permission_mode,
                    desired=desired,
                    reason=reason,
                    include_dynamic_tools=normalized_execution_policy != NO_TOOLS_EXECUTION_POLICY,
                    allowed_mcp_tool_names=allowed_mcp_tool_names,
                    allow_browser_smoke=allow_browser_smoke,
                    turn_transition=turn_transition,
                )
            else:
                prepared_thread_id, prepared_handoff = self._ensure_provider_thread_for_turn(
                    active_client,
                    source_thread_id=requested_thread_id,
                    profile=profile,
                    model=model,
                    effort=effort,
                    permission_mode=effective_permission_mode,
                    collaboration_mode=collaboration_mode,
                    context_mode=normalized_context_mode,
                    include_dynamic_tools=normalized_execution_policy != NO_TOOLS_EXECUTION_POLICY,
                    allowed_mcp_tool_names=allowed_mcp_tool_names,
                    allow_browser_smoke=allow_browser_smoke,
                    turn_transition=turn_transition,
                )
            if normalized_context_mode == "minimal_visual" and self._tasks is not None:
                guard_state = self._context_guard_state(prepared_thread_id)
                if str(guard_state.get("level") or "") == "pause":
                    desired = self._task_thread_settings(
                        profile,
                        model,
                        effort,
                        effective_permission_mode,
                        collaboration_mode=collaboration_mode,
                    )
                    prepared_thread_id, prepared_handoff = self._start_fresh_provider_thread_for_turn(
                        active_client,
                        source_thread_id=prepared_thread_id,
                        profile=profile,
                        model=model,
                        effort=effort,
                        permission_mode=effective_permission_mode,
                        desired=desired,
                        reason="minimal_visual_hot_thread",
                        include_dynamic_tools=normalized_execution_policy != NO_TOOLS_EXECUTION_POLICY,
                        allowed_mcp_tool_names=allowed_mcp_tool_names,
                        allow_browser_smoke=allow_browser_smoke,
                        turn_transition=turn_transition,
                    )
            self._raise_if_context_guard_blocks_turn(active_client, prepared_thread_id)
            return prepared_thread_id, prepared_handoff

        try:
            effective_thread_id, handoff_event = prepare_effective_thread(client)
        except RuntimeError as exc:
            if not self._is_app_server_transport_error(exc):
                raise
            self._record_event(
                {
                    "type": "turn_start_provider_thread_transport_retry",
                    "thread_id": requested_thread_id,
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "error": str(exc),
                }
            )
            self._close_client("turn_start_provider_thread_transport_retry")
            runtime_status = self._prepare_runtime(profile, require_secret=True)
            client = self._ensure_client(runtime_status)
            effective_thread_id, handoff_event = prepare_effective_thread(client)
        try:
            inputs = self._build_user_inputs(
                self._execution_policy_prompt(normalized_execution_policy, text),
                attachments or [],
                thread_id=effective_thread_id,
                context_mode=normalized_context_mode,
                profile_id=str(profile.get("profile_id") or ""),
                provider_id=str(profile.get("provider_id") or ""),
                model_id=str(model or profile.get("model") or ""),
            )
        except Exception as exc:
            attachment_diagnostics = self._attachment_diagnostics(
                attachments or [],
                provider_id=str(profile.get("provider_id") or ""),
                model_id=str(model or profile.get("model") or ""),
                context_mode=normalized_context_mode,
            )
            self._record_event(
                {
                    "type": "attachment_inputs_failed",
                    "thread_id": effective_thread_id,
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "model": model or profile.get("model"),
                    "context_mode": normalized_context_mode,
                    "attachment_diagnostics": attachment_diagnostics,
                    "error": self._attachment_failure_message(exc),
                }
            )
            raise ValueError(f"Attachment preparation failed: {self._attachment_failure_message(exc)}") from exc
        inputs, context_budget_report = self._apply_context_budget_preflight(
            inputs,
            profile=profile,
            runtime_status=runtime_status,
            model=model,
            thread_id=effective_thread_id,
            attachments=attachments or [],
            context_mode=normalized_context_mode,
        )
        attachment_diagnostics = self._attachment_diagnostics(
            attachments or [],
            prepared_inputs=inputs,
            provider_id=str(profile.get("provider_id") or ""),
            model_id=str(model or profile.get("model") or ""),
            context_mode=normalized_context_mode,
        )
        apply_turn_budget(client, effective_thread_id)
        params = {
            "threadId": effective_thread_id,
            "input": inputs,
            "cwd": self._runtime_workspace_root(),
            "approvalsReviewer": "user",
            "model": codex_model_id(profile, model),
            "effort": codex_reasoning_effort(effort or profile.get("reasoning_effort")),
            **self._turn_permission_overrides(effective_permission_mode),
        }
        mode_params = self._collaboration_mode_params(
            profile=profile,
            model=model,
            effort=effort,
            collaboration_mode=collaboration_mode,
        )
        if mode_params:
            params["collaborationMode"] = mode_params
        self._register_active_turn_execution_policy(
            effective_thread_id,
            normalized_execution_policy,
            mcp_tool_policy_snapshot=mcp_tool_policy_snapshot,
            mcp_tool_policy_context=mcp_tool_policy_context,
        )
        try:
            result = client.request("turn/start", params, timeout=TURN_START_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            return self._turn_start_background_pending_response(
                exc,
                effective_thread_id=effective_thread_id,
                handoff_event=handoff_event,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=effective_permission_mode,
                collaboration_mode=collaboration_mode,
                context_mode=normalized_context_mode,
                execution_policy=normalized_execution_policy,
                runtime_status=runtime_status,
                attachments=attachments or [],
                context_budget_report=context_budget_report,
                turn_transition=turn_transition,
                route_admission=route_admission,
            )
        except JsonRpcError as exc:
            if not self._is_thread_not_found_error(exc):
                raise
            self._mark_provider_thread_missing(effective_thread_id, reason="turn_start_thread_missing")
            turn_transition = self._build_turn_transition_for_start(
                source_thread_id=effective_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                execution_backend=execution_backend,
                context_mode=normalized_context_mode,
                transition_context={
                    "trigger": "turn_start_thread_missing",
                    "failure_notice": classify_runtime_failure(
                        "provider thread missing during turn/start",
                        current_provider=str(profile.get("provider_id") or ""),
                        current_model=str(model or profile.get("model") or ""),
                    ).to_payload(),
                },
            )
            self._assert_turn_transition_admitted(
                turn_transition,
                source_thread_id=effective_thread_id,
                phase="turn_start_thread_recovery",
            )
            effective_thread_id, handoff_event = self._recover_missing_provider_thread(
                client,
                missing_thread_id=effective_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=effective_permission_mode,
                collaboration_mode=collaboration_mode,
                reason="turn_start_thread_missing",
                include_dynamic_tools=normalized_execution_policy != NO_TOOLS_EXECUTION_POLICY,
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
                turn_transition=turn_transition,
            )
            try:
                inputs = self._build_user_inputs(
                    self._execution_policy_prompt(normalized_execution_policy, text),
                    attachments or [],
                    thread_id=effective_thread_id,
                    context_mode=normalized_context_mode,
                    profile_id=str(profile.get("profile_id") or ""),
                    provider_id=str(profile.get("provider_id") or ""),
                    model_id=str(model or profile.get("model") or ""),
                )
            except Exception as exc:
                attachment_diagnostics = self._attachment_diagnostics(
                    attachments or [],
                    provider_id=str(profile.get("provider_id") or ""),
                    model_id=str(model or profile.get("model") or ""),
                    context_mode=normalized_context_mode,
                )
                self._record_event(
                    {
                        "type": "attachment_inputs_failed",
                        "thread_id": effective_thread_id,
                        "profile_id": profile.get("profile_id"),
                        "provider_id": profile.get("provider_id"),
                        "model": model or profile.get("model"),
                        "context_mode": normalized_context_mode,
                        "attachment_diagnostics": attachment_diagnostics,
                        "error": self._attachment_failure_message(exc),
                    }
                )
                raise ValueError(f"Attachment preparation failed: {self._attachment_failure_message(exc)}") from exc
            inputs, context_budget_report = self._apply_context_budget_preflight(
                inputs,
                profile=profile,
                runtime_status=runtime_status,
                model=model,
                thread_id=effective_thread_id,
                attachments=attachments or [],
                context_mode=normalized_context_mode,
            )
            attachment_diagnostics = self._attachment_diagnostics(
                attachments or [],
                prepared_inputs=inputs,
                provider_id=str(profile.get("provider_id") or ""),
                model_id=str(model or profile.get("model") or ""),
                context_mode=normalized_context_mode,
            )
            params["threadId"] = effective_thread_id
            params["input"] = inputs
            apply_turn_budget(client, effective_thread_id)
            try:
                result = client.request("turn/start", params, timeout=TURN_START_TIMEOUT_SECONDS)
            except TimeoutError as retry_exc:
                return self._turn_start_background_pending_response(
                    retry_exc,
                    effective_thread_id=effective_thread_id,
                    handoff_event=handoff_event,
                    profile=profile,
                    model=model,
                    effort=effort,
                    permission_mode=effective_permission_mode,
                    collaboration_mode=collaboration_mode,
                    context_mode=normalized_context_mode,
                    execution_policy=normalized_execution_policy,
                    runtime_status=runtime_status,
                    attachments=attachments or [],
                    context_budget_report=context_budget_report,
                    turn_transition=turn_transition,
                    route_admission=route_admission,
                )
        except RuntimeError as exc:
            if not self._is_app_server_transport_error(exc):
                raise
            self._record_event(
                {
                    "type": "turn_start_transport_retry",
                    "thread_id": effective_thread_id,
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "error": str(exc),
                }
            )
            self._close_client("turn_start_transport_retry")
            client = self._runtime_request_client(runtime_status)
            result = client.request("turn/start", params, timeout=TURN_START_TIMEOUT_SECONDS)
        turn = dict(result.get("turn") or {})
        turn_id = str(turn.get("id") or "")
        turn_status = self._normalize_terminal_turn_status(turn.get("status"))
        self._pin_runtime_for_turn(runtime_status, effective_thread_id, turn_id)
        # Some compatible runtimes return a terminal turn directly from
        # turn/start and do not emit a later terminal notification. Do not
        # leave provider switching and thread reads pinned in that case.
        if turn_status in TERMINAL_TURN_STATUSES:
            self._clear_runtime_pin(
                thread_id=effective_thread_id,
                turn_id=turn_id,
                reason="turn_start_terminal_response",
            )
            if normalized_execution_policy != NO_TOOLS_EXECUTION_POLICY:
                self._clear_active_turn_execution_policy(thread_id=effective_thread_id, turn_id=turn_id)
        self._projects.switch_thread(effective_thread_id)
        if self._tasks is not None:
            self._tasks.force_visible_provider_thread(effective_thread_id)
        self._cache_thread_entry(
            effective_thread_id,
            {
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": model or profile.get("model"),
                "reasoning_effort": effort or profile.get("reasoning_effort"),
                "permission_mode": effective_permission_mode,
                "collaboration_mode": collaboration_mode or "default",
                "execution_route_status": route_admission.get("status"),
                "execution_route_driver": dict(route_admission.get("effective") or {}).get("execution_driver"),
            },
        )
        self._update_project_runtime_defaults(profile, model, effort, route_admission=route_admission)
        self._record_event(
            {
                "type": "turn_started_request",
                "thread_id": effective_thread_id,
                "turn_id": turn_id,
                "runtime": runtime_status,
                "attachments": self._attachment_event_items(attachments or []),
                "attachment_diagnostics": attachment_diagnostics,
                "context_budget_report": context_budget_report,
                "collaboration_mode": collaboration_mode or "default",
                "context_mode": normalized_context_mode,
                "turn_transition": compact_turn_transition(turn_transition),
                "route_admission": deepcopy(route_admission),
            }
        )
        self._record_execution_policy_started(
            thread_id=effective_thread_id,
            turn_id=str(turn.get("id") or ""),
            policy=normalized_execution_policy,
        )
        completed_transition = self._complete_turn_transition(
            turn_transition,
            target_thread_id=effective_thread_id,
            reused_existing=bool((handoff_event or {}).get("reused_existing", True)),
            completion_status="turn_start_accepted",
        )
        return {
            "turn": turn,
            "thread_id": effective_thread_id,
            "handoff": handoff_event,
            "attachment_diagnostics": attachment_diagnostics,
            "context_budget_report": context_budget_report,
            "turn_transition": compact_turn_transition(completed_transition),
            "route_admission": route_admission,
        }

    def verify_app_server_image_transport(
        self,
        profile: dict[str, Any],
        *,
        model: str | None,
    ) -> dict[str, Any]:
        provider_id = str(profile.get("provider_id") or "").strip()
        model_id = str(model or profile.get("model") or "").strip()
        if not provider_id or not model_id:
            raise ValueError("provider and model are required for App Server image verification.")
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        if "image" not in {str(item).strip().lower() for item in list(runtime_status.get("input_modalities") or [])}:
            raise ValueError("The selected model does not declare image input.")
        execution_backend = self._normalize_execution_backend(runtime_status.get("execution_backend") or profile.get("execution_backend"))
        if execution_backend != "app_server":
            raise ValueError("App Server image verification only applies to App Server routes.")
        client = self._runtime_request_client(runtime_status)
        probe_path, fixture_digest = self._materialize_app_server_image_probe_fixture()
        transport_contract = self._app_server_image_transport_contract(profile, model=model_id)
        probe_attempts: list[dict[str, Any]] = []
        probe_outcome: dict[str, Any] | None = None
        terminal_thread: dict[str, Any] | None = None
        for index, attempt in enumerate(self._app_server_image_probe_attempt_specs(model_id=model_id), start=1):
            outcome = self._run_app_server_image_probe_attempt(
                client,
                profile=profile,
                model_id=model_id,
                probe_path=probe_path,
                prompt=str(attempt.get("prompt") or ""),
                effort=str(attempt.get("effort") or "high"),
                attempt_index=index,
                variant=str(attempt.get("variant") or f"attempt_{index}"),
            )
            probe_attempts.append(outcome)
            probe_outcome = outcome
            terminal_thread = outcome.get("terminal_thread")
            if bool(outcome.get("grounded")):
                break
        if probe_outcome is None:
            raise RuntimeError("App Server image verification did not produce a probe attempt.")
        probe_thread_id = str(probe_outcome.get("thread_id") or "")
        turn_id = str(probe_outcome.get("turn_id") or "")
        terminal_status = str(probe_outcome.get("thread_status") or "failed")
        final_text = str(probe_outcome.get("final_text") or "")
        reasoning_text = str(probe_outcome.get("reasoning_text") or "")
        grounded = bool(probe_outcome.get("grounded"))
        verification_record = {
            "status": "verified" if grounded else "unverified",
            "verified_at": now_iso() if grounded else None,
            "verification_mode": "bounded_app_server_local_image_probe",
            "fixture": "red_square_png",
            "fixture_sha256": fixture_digest,
            "expected_response": "red",
            "provider_id": provider_id,
            "model_id": model_id,
            "native_model": str(profile.get("model") or model_id).strip(),
            "profile_id": str(profile.get("profile_id") or "").strip(),
            "runtime_backend": execution_backend,
            "transport_adapter": transport_contract["transport_adapter"],
            "transport_signature": transport_contract["transport_signature"],
            "thread_id": probe_thread_id,
            "turn_id": turn_id,
            "response_excerpt": final_text[:120],
            "reasoning_excerpt": reasoning_text[:240],
            "attempt_count": len(probe_attempts),
            "verified_attempt": int(probe_outcome.get("attempt") or 0) if grounded else None,
            "failure_reason": str(probe_outcome.get("failure_reason") or ""),
            "attempts": [
                {
                    "attempt": int(item.get("attempt") or 0),
                    "variant": str(item.get("variant") or ""),
                    "effort": str(item.get("effort") or ""),
                    "thread_status": str(item.get("thread_status") or ""),
                    "grounded": bool(item.get("grounded")),
                    "failure_reason": str(item.get("failure_reason") or ""),
                    "response_excerpt": str(item.get("final_text") or "")[:120],
                    "reasoning_excerpt": str(item.get("reasoning_text") or "")[:240],
                }
                for item in probe_attempts
            ],
            "usage_signal": usage_not_available(
                source="app_server_image_transport_verification",
                reason="app_server_thread_read_has_no_usage_projection",
                provider_id=provider_id,
                model=model_id,
                request_kind="app_server_local_image_probe",
            ),
        }
        if self._router_config is not None:
            self._router_config.record_app_server_image_transport_verification(
                model_id,
                verification_record if grounded else None,
            )
        result = {
            "ok": grounded,
            "provider": provider_id,
            "model": model_id,
            "stream": False,
            "status": 200 if terminal_thread is not None else 500,
            "content_type": "application/json; charset=utf-8",
            "preview": {
                "verification_mode": "bounded_app_server_local_image_probe",
                "execution_backend": execution_backend,
                "fixture": "red_square_png",
                "transport_adapter": transport_contract["transport_adapter"],
                "transport_signature": transport_contract["transport_signature"],
            },
            "response_excerpt": final_text[:120],
            "timestamp": now_iso(),
            "image_probe": {
                "fixture": "red_square_png",
                "expected_response": "red",
                "grounded": grounded,
                "thread_status": terminal_status,
                "attempt_count": len(probe_attempts),
                "failure_reason": str(probe_outcome.get("failure_reason") or ""),
                "attempts": [
                    {
                        "attempt": int(item.get("attempt") or 0),
                        "variant": str(item.get("variant") or ""),
                        "effort": str(item.get("effort") or ""),
                        "thread_status": str(item.get("thread_status") or ""),
                        "grounded": bool(item.get("grounded")),
                        "failure_reason": str(item.get("failure_reason") or ""),
                        "response_excerpt": str(item.get("final_text") or "")[:120],
                    }
                    for item in probe_attempts
                ],
            },
            "route_verification": redact_sensitive(verification_record),
        }
        if self._router_config is not None:
            self._router_config.record_test_result(result)
        self._record_event(
            {
                "type": "app_server_image_transport_verification",
                "provider_id": provider_id,
                "model": model_id,
                "ok": grounded,
                "thread_status": terminal_status,
                "response_excerpt": final_text[:120],
                "reasoning_excerpt": reasoning_text[:240],
                "verification": redact_sensitive(verification_record),
            }
        )
        return result

    def _app_server_image_probe_attempt_specs(self, *, model_id: str | None = None) -> list[dict[str, str]]:
        return [
            {
                "variant": "default_high_effort",
                "effort": "high",
                "prompt": "What is the dominant color of the attached image? Reply with one lowercase English word only.",
            },
            {
                "variant": "strict_final_low_reasoning",
                "effort": self._app_server_image_probe_fallback_effort(model_id=model_id),
                "prompt": (
                    "Identify the dominant color of the attached image. "
                    "Reply with exactly one lowercase English color word and nothing else. "
                    "Valid answer shape examples: red, blue, green, black, white, gray, yellow, orange, purple, brown, pink. "
                    "Do not explain and do not omit the final answer."
                ),
            },
        ][:APP_SERVER_IMAGE_VERIFY_MAX_ATTEMPTS]

    def _app_server_image_probe_fallback_effort(self, *, model_id: str | None = None) -> str:
        model_record: dict[str, Any] | None = None
        if model_id and self._router_config is not None:
            for item in self._router_config.models():
                if str(item.get("id") or "").strip() == str(model_id).strip():
                    model_record = dict(item)
                    break
        supported = {
            str(item).strip().lower()
            for item in list((model_record or {}).get("supported_reasoning_levels") or [])
            if str(item).strip()
        }
        native_supported = {
            str(item).strip().lower()
            for item in list((model_record or {}).get("native_supported_reasoning_levels") or [])
            if str(item).strip()
        }
        if "off" in supported and "off" in native_supported:
            return "off"
        for effort in ("minimal", "low", "medium", "high", "xhigh"):
            if effort in supported or effort in native_supported:
                return effort
        return "off"

    def _run_app_server_image_probe_attempt(
        self,
        client: Any,
        *,
        profile: dict[str, Any],
        model_id: str,
        probe_path: Path,
        prompt: str,
        effort: str,
        attempt_index: int,
        variant: str,
    ) -> dict[str, Any]:
        probe_thread_id = ""
        turn_id = ""
        terminal_thread: dict[str, Any] | None = None
        terminal_status = "failed"
        final_text = ""
        reasoning_text = ""
        try:
            started = client.request(
                "thread/start",
                self._thread_start_params(profile=profile, model=model_id, permission_mode="ask"),
                timeout=THREAD_START_TIMEOUT_SECONDS,
            )
            probe_thread_id = str(dict(started.get("thread") or {}).get("id") or "").strip()
            if not probe_thread_id:
                raise RuntimeError("thread/start did not return a probe thread id.")
            try:
                client.request(
                    "thread/name/set",
                    {"threadId": probe_thread_id, "name": f"AstraBridge image transport probe {attempt_index}"},
                )
            except Exception:
                pass
            started_turn = client.request(
                "turn/start",
                {
                    "threadId": probe_thread_id,
                    "input": self._app_server_image_probe_inputs(probe_path, prompt=prompt),
                    "cwd": self._runtime_workspace_root(),
                    "approvalsReviewer": "user",
                    "model": codex_model_id(profile, model_id),
                    "effort": codex_reasoning_effort(effort),
                    **self._turn_permission_overrides("ask"),
                },
                timeout=TURN_START_TIMEOUT_SECONDS,
            )
            turn_id = str(dict(started_turn.get("turn") or {}).get("id") or "").strip()
            if not turn_id:
                raise RuntimeError("turn/start did not return a probe turn id.")
            terminal_thread = self._wait_for_probe_turn_terminal(
                client,
                thread_id=probe_thread_id,
                turn_id=turn_id,
                timeout_seconds=APP_SERVER_IMAGE_VERIFY_TIMEOUT_SECONDS,
            )
            terminal_status, final_text, reasoning_text = self._probe_turn_result(terminal_thread, turn_id=turn_id)
        finally:
            if probe_thread_id:
                try:
                    client.request("thread/archive", {"threadId": probe_thread_id}, timeout=THREAD_READ_TIMEOUT_SECONDS)
                except Exception:
                    pass
        grounded = terminal_status == "completed" and final_text.strip().lower() == "red"
        return {
            "attempt": attempt_index,
            "variant": variant,
            "effort": codex_reasoning_effort(effort),
            "thread_id": probe_thread_id,
            "turn_id": turn_id,
            "thread_status": terminal_status,
            "final_text": final_text,
            "reasoning_text": reasoning_text,
            "grounded": grounded,
            "failure_reason": self._app_server_image_probe_failure_reason(
                status=terminal_status,
                final_text=final_text,
                reasoning_text=reasoning_text,
            ),
            "terminal_thread": terminal_thread,
        }

    def _app_server_image_probe_failure_reason(self, *, status: str, final_text: str, reasoning_text: str) -> str:
        normalized_status = str(status or "").strip().lower()
        normalized_final = final_text.strip().lower()
        if normalized_status != "completed":
            return f"turn_{normalized_status or 'unknown'}"
        if normalized_final == "red":
            return ""
        if normalized_final:
            return "unexpected_final_text"
        if reasoning_text.strip():
            return "reasoning_only_without_final_message"
        return "missing_final_message"

    def _app_server_image_transport_contract(self, profile: dict[str, Any], *, model: str) -> dict[str, str]:
        transport_class = transport_class_for_profile(profile, provider_family=str(profile.get("provider_family") or "").strip() or None)
        transport = transport_class(self._router, profile)
        return {
            "provider_id": str(profile.get("provider_id") or "").strip(),
            "model_id": str(model or "").strip(),
            "native_model": str(profile.get("model") or "").strip(),
            "transport_adapter": transport.describe(),
            "transport_signature": transport_signature_for_class(transport_class),
        }

    def _app_server_image_probe_inputs(self, probe_path: Path, *, prompt: str) -> list[dict[str, Any]]:
        return [
            {
                "type": "text",
                "text": str(prompt or "").strip(),
                "text_elements": [],
            },
            {
                "type": "localImage",
                "path": self._path_for_runtime(probe_path),
                "detail": "low",
            },
        ]

    def _materialize_app_server_image_probe_fixture(self) -> tuple[Path, str]:
        fixtures_root = self._projects.require_shell_state_root() / "verification-fixtures"
        fixtures_root.mkdir(parents=True, exist_ok=True)
        probe_path = fixtures_root / "app-server-image-probe-red-square.png"
        payload = self._app_server_image_probe_png_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if not probe_path.is_file() or probe_path.read_bytes() != payload:
            probe_path.write_bytes(payload)
        return probe_path, digest

    def _app_server_image_probe_png_bytes(self) -> bytes:
        width = height = 96
        scanline = b"\x00" + (b"\xff\x00\x00\xff" * width)
        raw = scanline * height

        def chunk(kind: bytes, payload: bytes) -> bytes:
            checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
            return len(payload).to_bytes(4, "big") + kind + payload + checksum.to_bytes(4, "big")

        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x06\x00\x00\x00")
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )

    @staticmethod
    def _normalize_terminal_turn_status(value: Any) -> str:
        normalized = str(value or "").strip().lower().replace("_", "")
        if normalized in {"aborted", "interrupted", "canceled", "cancelled"}:
            return "cancelled"
        if normalized in {"inprogress", "running"}:
            return "inprogress"
        return normalized

    @staticmethod
    def _probe_turn_exact(thread: dict[str, Any], *, turn_id: str) -> dict[str, Any] | None:
        clean_turn_id = str(turn_id or "").strip()
        if not clean_turn_id:
            return None
        for turn in [item for item in list(thread.get("turns") or []) if isinstance(item, dict)]:
            if str(turn.get("id") or "") == clean_turn_id:
                return turn
        return None

    def _terminal_turn_recovery_thread(
        self,
        *,
        thread_id: str,
        turn_id: str,
        latest_thread: dict[str, Any] | None,
        notification: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        target_turn_id = str(turn_id or "").strip()
        if not target_turn_id:
            return latest_thread
        notification_turn = dict((notification or {}).get("turn") or {})
        observed_turn_id = str(
            notification_turn.get("observedTurnId") or notification_turn.get("id") or ""
        ).strip()
        candidates: list[dict[str, Any]] = []
        if isinstance(latest_thread, dict):
            candidates.append(latest_thread)
        cached_native_thread = self._read_native_thread(thread_id)
        if isinstance(cached_native_thread, dict):
            candidates.append(self._decorate_thread(cached_native_thread))
        best_candidate: dict[str, Any] | None = None
        best_score = (-1, -1, -1, -1)
        for candidate in candidates:
            turn = self._probe_turn_exact(candidate, turn_id=target_turn_id)
            if turn is None:
                continue
            score = self._turn_snapshot_quality_score(candidate, turn_id=target_turn_id)
            if score > best_score:
                best_candidate = candidate
                best_score = score
        if best_candidate is not None:
            return best_candidate
        if observed_turn_id and observed_turn_id != target_turn_id:
            prior_candidate = self._thread_with_prior_completed_turn_mapped_to_target(
                candidates=candidates,
                observed_turn_id=observed_turn_id,
                target_turn_id=target_turn_id,
                observed_started_at=notification_turn.get("startedAt"),
                observed_completed_at=notification_turn.get("completedAt"),
            )
            if prior_candidate is not None:
                return prior_candidate
            observed_candidate = self._thread_with_observed_turn_mapped_to_target(
                candidates=candidates,
                observed_turn_id=observed_turn_id,
                target_turn_id=target_turn_id,
            )
            if observed_candidate is not None:
                return observed_candidate
        if not notification_turn:
            return latest_thread
        base_thread = dict(latest_thread or {})
        turns = [item for item in list(base_thread.get("turns") or []) if isinstance(item, dict)]
        turns.append(
            {
                **notification_turn,
                "id": target_turn_id or str(notification_turn.get("id") or ""),
            }
        )
        return {
            **base_thread,
            "id": str(base_thread.get("id") or thread_id or ""),
            "turns": turns,
        }

    def _thread_with_observed_turn_mapped_to_target(
        self,
        *,
        candidates: list[dict[str, Any]],
        observed_turn_id: str,
        target_turn_id: str,
    ) -> dict[str, Any] | None:
        clean_observed_turn_id = str(observed_turn_id or "").strip()
        clean_target_turn_id = str(target_turn_id or "").strip()
        if not clean_observed_turn_id or not clean_target_turn_id:
            return None
        best_candidate: dict[str, Any] | None = None
        best_turn: dict[str, Any] | None = None
        best_score = (-1, -1, -1, -1)
        for candidate in candidates:
            observed_turn = self._probe_turn_exact(candidate, turn_id=clean_observed_turn_id)
            if observed_turn is None:
                continue
            score = self._turn_snapshot_quality_score(candidate, turn_id=clean_observed_turn_id)
            if score > best_score:
                best_candidate = candidate
                best_turn = observed_turn
                best_score = score
        if best_candidate is None or best_turn is None:
            return None
        turns: list[dict[str, Any]] = []
        replaced = False
        for item in [entry for entry in list(best_candidate.get("turns") or []) if isinstance(entry, dict)]:
            item_id = str(item.get("id") or "").strip()
            if item_id == clean_target_turn_id:
                turns.append(
                    {
                        **best_turn,
                        "id": clean_target_turn_id,
                        "observedTurnId": clean_observed_turn_id,
                    }
                )
                replaced = True
                continue
            turns.append(item)
        if not replaced:
            turns.append(
                {
                    **best_turn,
                    "id": clean_target_turn_id,
                    "observedTurnId": clean_observed_turn_id,
                }
            )
        return {**best_candidate, "turns": turns}

    @staticmethod
    def _turn_sort_timestamp_value(value: Any) -> float:
        if value is None:
            return float("-inf")
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value or "").strip()
        if not text:
            return float("-inf")
        try:
            return float(text)
        except Exception:
            pass
        try:
            return dt.datetime.fromisoformat(text).timestamp()
        except Exception:
            return float("-inf")

    def _thread_with_prior_completed_turn_mapped_to_target(
        self,
        *,
        candidates: list[dict[str, Any]],
        observed_turn_id: str,
        target_turn_id: str,
        observed_started_at: Any = None,
        observed_completed_at: Any = None,
    ) -> dict[str, Any] | None:
        clean_observed_turn_id = str(observed_turn_id or "").strip()
        clean_target_turn_id = str(target_turn_id or "").strip()
        if not clean_observed_turn_id or not clean_target_turn_id:
            return None
        observed_boundary = self._turn_sort_timestamp_value(observed_started_at)
        if observed_boundary == float("-inf"):
            observed_boundary = self._turn_sort_timestamp_value(observed_completed_at)
        best_candidate: dict[str, Any] | None = None
        best_turn: dict[str, Any] | None = None
        best_rank = ((-1, -1, -1, -1), float("-inf"))
        for candidate in candidates:
            turns = [entry for entry in list(candidate.get("turns") or []) if isinstance(entry, dict)]
            for turn in turns:
                turn_id = str(turn.get("id") or "").strip()
                if not turn_id or turn_id == clean_observed_turn_id:
                    continue
                status = self._normalize_terminal_turn_status(turn.get("status"))
                if status not in TERMINAL_TURN_STATUSES:
                    continue
                turn_boundary = self._turn_sort_timestamp_value(turn.get("completedAt"))
                if turn_boundary == float("-inf"):
                    turn_boundary = self._turn_sort_timestamp_value(turn.get("completed_at"))
                if turn_boundary == float("-inf"):
                    turn_boundary = self._turn_sort_timestamp_value(turn.get("startedAt"))
                if turn_boundary == float("-inf"):
                    turn_boundary = self._turn_sort_timestamp_value(turn.get("started_at"))
                if observed_boundary != float("-inf") and turn_boundary > observed_boundary:
                    continue
                score = self._turn_snapshot_quality_score(candidate, turn_id=turn_id)
                if score[1] <= 0 and score[2] <= 0:
                    continue
                rank = (score, turn_boundary)
                if rank > best_rank:
                    best_candidate = candidate
                    best_turn = turn
                    best_rank = rank
        if best_candidate is None or best_turn is None:
            return None
        source_turn_id = str(best_turn.get("id") or "").strip()
        turns: list[dict[str, Any]] = []
        replaced = False
        for item in [entry for entry in list(best_candidate.get("turns") or []) if isinstance(entry, dict)]:
            item_id = str(item.get("id") or "").strip()
            if item_id == clean_target_turn_id:
                turns.append(
                    {
                        **best_turn,
                        "id": clean_target_turn_id,
                        "observedTurnId": clean_observed_turn_id,
                        "recoveredFromTurnId": source_turn_id or None,
                    }
                )
                replaced = True
                continue
            turns.append(item)
        if not replaced:
            turns.append(
                {
                    **best_turn,
                    "id": clean_target_turn_id,
                    "observedTurnId": clean_observed_turn_id,
                    "recoveredFromTurnId": source_turn_id or None,
                }
            )
        return {**best_candidate, "turns": turns}

    def _enrich_terminal_turn_thread(
        self,
        *,
        thread_id: str,
        turn_id: str,
        thread: dict[str, Any],
    ) -> dict[str, Any]:
        clean_thread_id = str(thread_id or "").strip()
        clean_turn_id = str(turn_id or "").strip()
        if not clean_thread_id or not clean_turn_id:
            return thread
        current_score = self._turn_snapshot_quality_score(thread, turn_id=clean_turn_id)
        cached_native_thread = self._read_native_thread(clean_thread_id)
        if not isinstance(cached_native_thread, dict):
            return thread
        cached_candidate = self._decorate_thread(cached_native_thread)
        cached_score = self._turn_snapshot_quality_score(cached_candidate, turn_id=clean_turn_id)
        return cached_candidate if cached_score > current_score else thread

    def _turn_snapshot_quality_score(self, thread: dict[str, Any], *, turn_id: str) -> tuple[int, int, int, int]:
        turn = self._probe_turn_exact(thread, turn_id=turn_id)
        if turn is None:
            return (-1, -1, -1, -1)
        status = self._normalize_terminal_turn_status(turn.get("status"))
        _thread_status, final_text, reasoning_text = self._probe_turn_result(thread, turn_id=turn_id)
        item_count = len([item for item in list(turn.get("items") or []) if isinstance(item, dict)])
        terminal_rank = 1 if status in TERMINAL_TURN_STATUSES else 0
        return (
            terminal_rank,
            1 if bool(final_text.strip()) else 0,
            1 if bool(reasoning_text.strip()) else 0,
            item_count,
        )

    def _wait_for_probe_turn_terminal(
        self,
        client: Any,
        *,
        thread_id: str,
        turn_id: str,
        timeout_seconds: float,
        operation_label: str = "the App Server image probe",
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max(5.0, timeout_seconds)
        latest_thread: dict[str, Any] | None = None
        latest_projected_status = "missing"
        latest_notification_status = ""
        latest_read_error_type = ""
        latest_read_error_message = ""
        while time.monotonic() < deadline:
            try:
                result = client.request(
                    "thread/read",
                    {"threadId": thread_id, "includeTurns": True},
                    timeout=THREAD_READ_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                latest_read_error_type = type(exc).__name__
                latest_read_error_message = str(redact_sensitive(str(exc))).strip()[:400]
                notification = self._terminal_turn_notification(thread_id=thread_id, turn_id=turn_id)
                latest_notification_status = self._normalize_terminal_turn_status(
                    dict(notification or {}).get("status")
                )
                fallback_thread = latest_thread
                if fallback_thread is None:
                    cached_native_thread = self._read_native_thread(thread_id)
                    if isinstance(cached_native_thread, dict):
                        fallback_thread = self._decorate_thread(cached_native_thread)
                if (
                    fallback_thread is not None
                    and latest_notification_status in TERMINAL_TURN_STATUSES
                ):
                    reconciled_thread = self._reconcile_terminal_turn_notification(
                        fallback_thread,
                        turn_id=turn_id,
                        notification=dict(notification or {}),
                    )
                    reconciled_status, final_text, _reasoning_text = self._probe_turn_result(
                        reconciled_thread,
                        turn_id=turn_id,
                    )
                    if reconciled_status in {"failed", "cancelled", "errored"} or bool(
                        final_text.strip()
                    ):
                        notification_lag_ms = max(
                            0,
                            int(
                                (
                                    time.monotonic()
                                    - float(dict(notification or {}).get("observed_at_monotonic") or time.monotonic())
                                )
                                * 1000
                            ),
                        )
                        self._record_event(
                            {
                                "type": "runtime_turn_terminal_notification_reconciled",
                                "thread_id": thread_id,
                                "turn_id": turn_id,
                                "operation": str(operation_label or "runtime turn"),
                                "projected_status": latest_projected_status,
                                "notification_status": latest_notification_status,
                                "final_text_present": bool(final_text.strip()),
                                "thread_read_error_type": latest_read_error_type,
                                "thread_read_error_message": latest_read_error_message or None,
                                "terminal_projection_lag_ms": notification_lag_ms,
                            }
                        )
                        return reconciled_thread
                time.sleep(1.0)
                continue
            latest_read_error_type = ""
            latest_read_error_message = ""
            latest_thread = self._decorate_thread(dict(result.get("thread") or {}))
            target_turn = self._probe_turn_exact(latest_thread, turn_id=turn_id)
            latest_projected_status = self._normalize_terminal_turn_status(dict(target_turn or {}).get("status")) or "missing"
            if target_turn and latest_projected_status in TERMINAL_TURN_STATUSES:
                return self._enrich_terminal_turn_thread(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    thread=latest_thread,
                )
            notification = self._terminal_turn_notification(thread_id=thread_id, turn_id=turn_id)
            latest_notification_status = self._normalize_terminal_turn_status(dict(notification or {}).get("status"))
            if latest_notification_status in TERMINAL_TURN_STATUSES:
                recovery_thread = self._terminal_turn_recovery_thread(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    latest_thread=latest_thread,
                    notification=dict(notification or {}),
                )
                if recovery_thread is None:
                    time.sleep(1.0)
                    continue
                reconciled_thread = self._reconcile_terminal_turn_notification(
                    recovery_thread,
                    turn_id=turn_id,
                    notification=dict(notification or {}),
                )
                reconciled_status, final_text, _reasoning_text = self._probe_turn_result(
                    reconciled_thread,
                    turn_id=turn_id,
                )
                notification_age = time.monotonic() - float(
                    dict(notification or {}).get("observed_at_monotonic") or time.monotonic()
                )
                if (
                    reconciled_status in {"failed", "cancelled", "errored"}
                    or bool(final_text.strip())
                    or notification_age >= TERMINAL_RESULT_GRACE_SECONDS
                ):
                    self._record_event(
                        {
                            "type": "runtime_turn_terminal_notification_reconciled",
                            "thread_id": thread_id,
                            "turn_id": turn_id,
                            "operation": str(operation_label or "runtime turn"),
                            "projected_status": latest_projected_status,
                            "notification_status": latest_notification_status,
                            "final_text_present": bool(final_text.strip()),
                            "terminal_projection_lag_ms": max(0, int(notification_age * 1000)),
                        }
                    )
                    return reconciled_thread
            time.sleep(1.0)
        clean_operation_label = str(operation_label or "the runtime turn").strip() or "the runtime turn"
        self._record_event(
            {
                "type": "runtime_turn_terminal_timeout",
                "thread_id": thread_id,
                "turn_id": turn_id,
                "operation": clean_operation_label,
                "projected_status": latest_projected_status,
                "notification_status": latest_notification_status or None,
                "turn_count": len(list(dict(latest_thread or {}).get("turns") or [])),
                "thread_read_error_type": latest_read_error_type or None,
                "thread_read_error_message": latest_read_error_message or None,
            }
        )
        raise TimeoutError(f"Timed out waiting for {clean_operation_label} to reach a terminal state.")

    def _reconcile_terminal_turn_notification(
        self,
        thread: dict[str, Any],
        *,
        turn_id: str,
        notification: dict[str, Any],
    ) -> dict[str, Any]:
        notified_turn = dict(notification.get("turn") or {})
        notified_status = self._normalize_terminal_turn_status(
            notification.get("status") or notified_turn.get("status")
        )
        if notified_status not in TERMINAL_TURN_STATUSES:
            return thread
        target = self._probe_turn_exact(thread, turn_id=turn_id)
        target_id = str(dict(target or {}).get("id") or "")
        turns: list[dict[str, Any]] = []
        changed = False
        for item in list(thread.get("turns") or []):
            if not isinstance(item, dict):
                continue
            if item is target or (target_id and str(item.get("id") or "") == target_id):
                turns.append(
                    {
                        **item,
                        "status": notified_status,
                        "error": notified_turn.get("error", item.get("error")),
                        "completedAt": notified_turn.get("completedAt", item.get("completedAt")),
                        "durationMs": notified_turn.get("durationMs", item.get("durationMs")),
                    }
                )
                changed = True
            else:
                turns.append(item)
        if changed:
            return {**thread, "turns": turns}
        synthetic_turn_id = str(turn_id or notified_turn.get("id") or "").strip()
        if not synthetic_turn_id:
            return thread
        return {
            **thread,
            "turns": [
                *turns,
                {
                    **notified_turn,
                    "id": synthetic_turn_id,
                    "status": notified_status,
                },
            ],
        }

    def _probe_turn(self, thread: dict[str, Any], *, turn_id: str) -> dict[str, Any] | None:
        turns = [item for item in list(thread.get("turns") or []) if isinstance(item, dict)]
        if not turns:
            return None
        exact = self._probe_turn_exact(thread, turn_id=turn_id)
        if exact is not None:
            return exact
        return turns[-1]

    def _probe_turn_result(self, thread: dict[str, Any], *, turn_id: str) -> tuple[str, str, str]:
        turn = self._probe_turn(thread, turn_id=turn_id)
        if not turn:
            return "missing", "", ""
        status = self._normalize_terminal_turn_status(turn.get("status")) or "unknown"
        final_text = ""
        reasoning_text = ""
        for item in list(turn.get("items") or []):
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip()
            if item_type not in {"agentMessage", "assistantMessage", "agent_message", "assistant_message"}:
                if item_type == "reasoning":
                    reasoning_text = self._reasoning_item_text(item) or reasoning_text
                continue
            provider_data = dict(item.get("providerData") or item.get("provider_data") or {})
            normalized = dict(provider_data.get("normalized") or {})
            text = self._projection_item_text(item, normalized)
            if text:
                final_text = text.strip()
        return status, final_text, reasoning_text

    def _reasoning_item_text(self, item: dict[str, Any]) -> str:
        summary = item.get("summary")
        parts: list[str] = []
        if isinstance(summary, list):
            for entry in summary:
                if isinstance(entry, str) and entry.strip():
                    parts.append(entry.strip())
                    continue
                if isinstance(entry, dict):
                    text = str(entry.get("text") or "").strip()
                    if text:
                        parts.append(text)
        if parts:
            return "\n".join(parts)
        content = item.get("content")
        if isinstance(content, str):
            return content.strip()
        return ""

    def _clear_bounded_turn_goal(
        self,
        client: Any,
        *,
        thread_id: str,
        turn_id: str,
    ) -> bool:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return False
        try:
            client.request("thread/goal/clear", {"threadId": clean_thread_id})
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                {
                    "type": "bounded_turn_goal_clear_failed",
                    "thread_id": clean_thread_id,
                    "turn_id": str(turn_id or "").strip() or None,
                    "error": str(exc)[:300],
                }
            )
            return False
        self._record_event(
            {
                "type": "bounded_turn_goal_cleared",
                "thread_id": clean_thread_id,
                "turn_id": str(turn_id or "").strip() or None,
            }
        )
        return True

    def _stop_bounded_turn_follow_on_execution(
        self,
        profile: dict[str, Any],
        client: Any,
        *,
        thread_id: str,
        completed_turn_id: str,
    ) -> dict[str, Any]:
        clean_thread_id = str(thread_id or "").strip()
        clean_completed_turn_id = str(completed_turn_id or "").strip()
        if not clean_thread_id or not clean_completed_turn_id:
            return {"goal_cleared": False, "follow_on_turn_id": None, "follow_on_turn_interrupted": False}
        goal_cleared = self._clear_bounded_turn_goal(
            client,
            thread_id=clean_thread_id,
            turn_id=clean_completed_turn_id,
        )
        follow_on_turn_id: str | None = None
        follow_on_turn_interrupted = False
        try:
            result = client.request(
                "thread/read",
                {"threadId": clean_thread_id, "includeTurns": True},
                timeout=THREAD_READ_TIMEOUT_SECONDS,
            )
            thread = self._decorate_thread(dict(result.get("thread") or {}))
            turns = [item for item in list(thread.get("turns") or []) if isinstance(item, dict)]
            latest_turn = turns[-1] if turns else None
            latest_turn_id = str(dict(latest_turn or {}).get("id") or "").strip()
            latest_status = self._normalize_terminal_turn_status(dict(latest_turn or {}).get("status"))
            if (
                latest_turn is not None
                and latest_turn_id
                and latest_turn_id != clean_completed_turn_id
                and latest_status not in TERMINAL_TURN_STATUSES
            ):
                follow_on_turn_id = latest_turn_id
                self.interrupt_turn(profile, clean_thread_id, follow_on_turn_id)
                follow_on_turn_interrupted = True
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                {
                    "type": "bounded_turn_follow_on_cleanup_failed",
                    "thread_id": clean_thread_id,
                    "turn_id": clean_completed_turn_id,
                    "error": str(exc)[:300],
                }
            )
        self._record_event(
            {
                "type": "bounded_turn_follow_on_cleanup",
                "thread_id": clean_thread_id,
                "turn_id": clean_completed_turn_id,
                "goal_cleared": goal_cleared,
                "follow_on_turn_id": follow_on_turn_id,
                "follow_on_turn_interrupted": follow_on_turn_interrupted,
            }
        )
        self._clear_active_turn_execution_policy(
            thread_id=clean_thread_id,
            turn_id=clean_completed_turn_id,
        )
        return {
            "goal_cleared": goal_cleared,
            "follow_on_turn_id": follow_on_turn_id,
            "follow_on_turn_interrupted": follow_on_turn_interrupted,
        }

    def _resolve_requested_thread_id(self, thread_id: str) -> str:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id.startswith("task:") or self._tasks is None:
            return clean_thread_id
        hint = self._tasks.visible_provider_thread_id(include_missing_fallback=True)
        return str(hint or clean_thread_id).strip()

    def route_admission(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        permission_mode: str | None = None,
        execution_policy: str | None = None,
        context_mode: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        confirm_degradation: bool = False,
        operation: str | None = None,
    ) -> dict[str, Any]:
        """Return the exact, side-effect-free route posture for a task start."""

        _effective_profile, admission = self._admit_runtime_route(
            profile,
            thread_id=thread_id,
            model=model,
            effort=effort,
            permission_mode=permission_mode,
            execution_policy=execution_policy,
            context_mode=context_mode,
            attachments=attachments,
            confirm_degradation=confirm_degradation,
        )
        return self._admission_for_operation(admission, operation=operation)

    def _admit_runtime_route(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str | None,
        model: str | None,
        effort: str | None,
        permission_mode: str | None,
        execution_policy: str | None,
        context_mode: str | None,
        attachments: list[dict[str, Any]] | None,
        confirm_degradation: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Bind the admission contract to the exact selected model.

        ``ProfileService`` owns endpoint/auth defaults, while the router catalog
        owns model route proof.  This method deliberately overlays the exact
        selected model before either runtime preparation or thread creation can
        observe it; a profile's previous model proof cannot leak to a newly
        selected sibling model.
        """

        effective_profile, model_contract_present = self._profile_for_runtime_model(profile, model)
        if self._router_config is None:
            legacy_thread_backend = self._legacy_thread_backend_for_admission(
                effective_profile,
                thread_id=thread_id,
            )
            if legacy_thread_backend:
                effective_profile["execution_backend"] = legacy_thread_backend
        source_provider = self._source_provider_for_route_admission(thread_id)
        has_explicit_route_contract = isinstance(effective_profile.get("execution_route"), dict) or isinstance(
            effective_profile.get("execution_route_evidence"), dict
        )
        if self._router_config is None and not has_explicit_route_contract:
            admission = legacy_runtime_route_admission(
                effective_profile,
                requested_model=effective_profile.get("model"),
                requested_effort=effort,
                requested_permission_mode=permission_mode,
                requested_execution_policy=execution_policy,
                requested_context_mode=context_mode,
            )
        else:
            admission = resolve_runtime_route_admission(
                effective_profile,
                requested_model=effective_profile.get("model"),
                requested_effort=effort,
                requested_permission_mode=permission_mode,
                requested_execution_policy=execution_policy,
                requested_context_mode=context_mode,
                attachments=list(attachments or []),
                source_provider_id=source_provider,
                native_kernel_enabled=self._native_kernel_enabled(),
                confirm_degradation=confirm_degradation,
                model_contract_present=model_contract_present,
            )
        effective_profile["_runtime_route_admission"] = deepcopy(admission)
        return effective_profile, admission

    def _legacy_thread_backend_for_admission(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str | None,
    ) -> str | None:
        """Reuse an embedded thread's host only for its exact same route.

        Isolated callers predating RouterConfigService can retain native
        threads.  This is not a route-evidence bypass: the inherited host is
        considered only when provider and native model match exactly, and it
        never affects a configured production route or default eligibility.
        """

        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return None
        settings = self._task_thread_entry(clean_thread_id)
        if not settings:
            cache = self._read_thread_cache()
            settings = dict((cache.get("by_id") or {}).get(clean_thread_id) or {})
        source_provider = str(settings.get("provider_id") or "").strip().lower()
        target_provider = str(profile.get("provider_id") or "").strip().lower()
        source_model = str(settings.get("model") or "").strip()
        target_model = str(profile.get("model") or "").strip()
        if "/" in source_model:
            source_provider_hint, source_model = [part.strip() for part in source_model.split("/", 1)]
            source_provider = source_provider or source_provider_hint.lower()
        if not source_provider or not target_provider or source_provider != target_provider:
            return None
        if not source_model or not target_model or source_model != target_model:
            return None
        backend = self._normalize_execution_backend(settings.get("execution_backend"))
        return backend if backend == "native_kernel" else None

    def _profile_for_runtime_model(
        self,
        profile: dict[str, Any],
        model: str | None,
    ) -> tuple[dict[str, Any], bool]:
        """Return a local profile copy with the requested model's facts.

        This is intentionally not a persistence migration.  A profile stays a
        provider/endpoint choice; the effective model contract exists only for
        this request and is discarded after the runtime call.
        """

        effective = deepcopy(dict(profile or {}))
        provider_id = str(effective.get("provider_id") or "").strip().lower()
        requested = str(model or effective.get("model") or "").strip()
        selected_provider = provider_id
        selected_model = requested
        if "/" in requested:
            candidate_provider, candidate_model = [part.strip() for part in requested.split("/", 1)]
            if candidate_provider and provider_id and candidate_provider.lower() != provider_id:
                raise ValueError(
                    "Selected model provider does not match the selected runtime profile. "
                    "Choose that provider's profile before starting a turn."
                )
            selected_provider = candidate_provider.lower() or provider_id
            selected_model = candidate_model
        if not selected_model:
            raise ValueError("model is required for runtime route admission.")
        if selected_provider:
            effective["provider_id"] = selected_provider
        previous_model = str(effective.get("model") or "").strip()
        effective["model"] = selected_model
        configured_model = self._configured_runtime_model(selected_provider, selected_model)
        if configured_model is not None:
            for key, value in configured_model.items():
                if key in {"id", "provider", "provider_id", "native_model", "display_name", "displayName"}:
                    continue
                effective[key] = deepcopy(value)
            effective["runtime_model_contract_status"] = "configured"
            effective["runtime_model_contract_id"] = str(configured_model.get("id") or "").strip() or None
            return effective, True

        # A profile may carry an exact custom-model proof.  It remains usable
        # only when the caller did not switch away from that profiled model.
        # Otherwise clear all cached/derived route fields before re-resolving,
        # so a sibling model cannot inherit a stronger route.
        if previous_model and previous_model != selected_model:
            for field in (
                "execution_route",
                "execution_route_status",
                "execution_route_driver",
                "execution_route_configured_driver",
                "execution_route_authority_tier",
                "execution_route_declared_authority_tier",
                "execution_route_evidence_state",
                "execution_route_verification_status",
                "execution_route_blockers",
                "execution_route_warning",
                "execution_route_default_eligible",
                "execution_route_evidence",
            ):
                effective.pop(field, None)
        effective["runtime_model_contract_status"] = "profile_only" if previous_model == selected_model else "missing"
        return effective, previous_model == selected_model

    def _configured_runtime_model(self, provider_id: str, model_id: str) -> dict[str, Any] | None:
        if self._router_config is None or not provider_id or not model_id:
            return None
        try:
            models = self._router_config.models()
        except Exception:  # noqa: BLE001 - missing catalog data must fail closed in the resolver
            return None
        for item in list(models or []):
            if not isinstance(item, dict):
                continue
            candidate_provider = str(item.get("provider") or item.get("provider_id") or "").strip().lower()
            candidate_model = str(item.get("native_model") or "").strip()
            candidate_id = str(item.get("id") or "").strip()
            if candidate_id == f"{provider_id}/{model_id}" or (candidate_provider == provider_id and candidate_model == model_id):
                return deepcopy(item)
        return None

    def _source_provider_for_route_admission(self, thread_id: str | None) -> str | None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return None
        settings = self._task_thread_entry(clean_thread_id)
        if not settings:
            try:
                settings = self._thread_settings_for(clean_thread_id)
            except Exception:  # noqa: BLE001 - missing source metadata just avoids an unwarranted continuity claim
                settings = {}
        return str(settings.get("provider_id") or "").strip() or None

    def _assert_runtime_route_admitted(
        self,
        admission: dict[str, Any],
        *,
        operation: str,
        thread_id: str | None = None,
    ) -> None:
        status = str(admission.get("status") or "blocked").strip()
        if status == "admitted":
            return
        self._record_event(
            {
                "type": "runtime_route_admission_not_admitted",
                "operation": operation,
                "thread_id": str(thread_id or "").strip() or None,
                "route_admission": deepcopy(admission),
            }
        )
        raise RuntimeRouteAdmissionError(admission, operation=operation)

    @staticmethod
    def _admission_for_operation(
        admission: dict[str, Any],
        *,
        operation: str | None,
    ) -> dict[str, Any]:
        """Add an exact task-start constraint without changing model intent.

        A verified native-provider route can execute an existing native thread,
        but this desktop flow cannot create or fork an App Server thread for
        it.  Returning that distinction from preflight avoids an ``admitted``
        status that would immediately fail during thread setup.
        """

        normalized_operation = str(operation or "").strip().lower()
        if normalized_operation not in {"thread_create", "thread_create_receipt", "thread_fork", "graph_worker_start"}:
            return admission
        execution_backend = str(dict(admission.get("effective") or {}).get("execution_backend") or "app_server").strip()
        if execution_backend == "app_server":
            return admission
        blocked = deepcopy(admission)
        blocked["status"] = "blocked"
        blocked["presentation_state"] = "blocked"
        degradation = dict(blocked.get("degradation") or {})
        reasons = list(degradation.get("reasons") or [])
        if not any(str(item.get("code") or "") == "thread_setup_driver_not_supported" for item in reasons if isinstance(item, dict)):
            reasons.append(
                {
                    "code": "thread_setup_driver_not_supported",
                    "message": "This route cannot create or fork an App Server thread; start it through its verified native runtime instead.",
                }
            )
        degradation["active"] = True
        degradation["requires_confirmation"] = False
        degradation["reasons"] = reasons
        blocked["degradation"] = degradation
        return blocked

    def _thread_execution_backend(self, thread_id: str, profile: dict[str, Any]) -> str:
        settings = self._thread_settings_for(thread_id) if thread_id else {}
        route_admission = dict(profile.get("_runtime_route_admission") or {})
        effective_route = dict(route_admission.get("effective") or {})
        admitted_backend = str(effective_route.get("execution_backend") or "").strip()
        if admitted_backend:
            return self._normalize_execution_backend(admitted_backend)
        profile_backend = profile.get("execution_backend")
        return self._normalize_execution_backend(settings.get("execution_backend") or profile_backend)

    def _native_kernel_enabled(self) -> bool:
        raw = str(os.environ.get("ASTRABRIDGE_ENABLE_NATIVE_KERNEL") or "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _start_native_turn(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        text: str,
        attachments: list[dict[str, Any]],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        context_mode: str,
        turn_transition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._native_kernel_enabled():
            raise RuntimeError("Native kernel execution is disabled. Set ASTRABRIDGE_ENABLE_NATIVE_KERNEL=1 to enable it.")
        if self._native_turn_loop is None:
            raise RuntimeError("Native kernel dependencies are not attached.")
        prepared_inputs = self._build_user_inputs(
            text,
            attachments,
            thread_id=thread_id,
            context_mode=context_mode,
            profile_id=str(profile.get("profile_id") or ""),
            provider_id=str(profile.get("provider_id") or ""),
            model_id=str(model or profile.get("model") or ""),
        )
        prepared_inputs, context_budget_report = self._apply_context_budget_preflight(
            prepared_inputs,
            profile=profile,
            runtime_status=None,
            model=model,
            thread_id=thread_id,
            attachments=attachments,
            context_mode=context_mode,
        )
        run_turn_kwargs: dict[str, Any] = {
            "thread_id": thread_id,
            "profile": profile,
            "text": text,
            "attachments": attachments,
            "model": model,
            "effort": effort,
            "permission_mode": permission_mode,
            "collaboration_mode": collaboration_mode,
            "context_mode": context_mode,
        }
        try:
            import inspect

            if "prepared_inputs" in inspect.signature(self._native_turn_loop.run_turn).parameters:
                run_turn_kwargs["prepared_inputs"] = prepared_inputs
        except (TypeError, ValueError):
            # Test doubles and legacy native-loop shims may not expose a
            # Python signature; production NativeCodingTurnLoop does.
            pass
        result = self._native_turn_loop.run_turn(
            **run_turn_kwargs,
        )
        completed_transition = self._complete_turn_transition(
            turn_transition,
            target_thread_id=thread_id,
            reused_existing=True,
            completion_status="native_turn_started",
        )
        self._cache_thread_entry(thread_id, result.thread_cache_patch)
        self._projects.switch_thread(thread_id)
        if self._tasks is not None:
            self._tasks.force_visible_provider_thread(thread_id)
        self._update_project_runtime_defaults(
            profile,
            model,
            effort,
            route_admission=dict(profile.get("_runtime_route_admission") or {}) or None,
        )
        self._record_task_thread_snapshot(result.thread)
        self._record_event(
            {
                "type": "native_turn_completed",
                "thread_id": thread_id,
                "turn_id": result.turn.get("id"),
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": model or profile.get("model"),
                "context_mode": context_mode,
                "context_budget_report": context_budget_report,
                "turn_transition": compact_turn_transition(completed_transition),
            }
        )
        return {
            "turn": result.turn,
            "thread_id": thread_id,
            "handoff": result.handoff,
            "context_budget_report": context_budget_report,
            "turn_transition": compact_turn_transition(completed_transition),
        }

    def _turn_start_background_pending_response(
        self,
        exc: TimeoutError,
        *,
        effective_thread_id: str,
        handoff_event: dict[str, Any] | None,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        context_mode: str,
        execution_policy: str,
        runtime_status: dict[str, Any],
        attachments: list[dict[str, Any]],
        context_budget_report: dict[str, Any] | None = None,
        turn_transition: dict[str, Any] | None = None,
        route_admission: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        synthetic_turn = {
            "id": new_id("pending-turn"),
            "status": "starting",
            "synthetic": True,
            "background_start": True,
        }
        self._projects.switch_thread(effective_thread_id)
        self._record_execution_policy_started(
            thread_id=effective_thread_id,
            turn_id=str(synthetic_turn.get("id") or ""),
            policy=execution_policy,
        )
        self._cache_thread_entry(
            effective_thread_id,
            {
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": model or profile.get("model"),
                "reasoning_effort": effort or profile.get("reasoning_effort"),
                "permission_mode": permission_mode,
                "collaboration_mode": collaboration_mode or "default",
            },
        )
        self._update_project_runtime_defaults(profile, model, effort, route_admission=route_admission)
        self._record_event(
            {
                "type": "turn_start_background_pending",
                "thread_id": effective_thread_id,
                "synthetic_turn_id": synthetic_turn["id"],
                "profile_id": profile.get("profile_id"),
                "model": model or profile.get("model"),
                "runtime": runtime_status,
                "attachments": self._attachment_event_items(attachments),
                "attachment_diagnostics": self._attachment_diagnostics(
                    attachments,
                    provider_id=str(profile.get("provider_id") or ""),
                    model_id=str(model or profile.get("model") or ""),
                    context_mode=context_mode,
                ),
                "context_budget_report": dict(context_budget_report or {}) or None,
                "collaboration_mode": collaboration_mode or "default",
                "context_mode": context_mode,
                "turn_transition": compact_turn_transition(turn_transition),
                "route_admission": deepcopy(dict(route_admission or {})),
                "warning": (
                    "app-server did not answer turn/start before the sidecar timeout; "
                    "the turn may still be running and should be tracked through runtime events."
                ),
            }
        )
        return {
            "turn": synthetic_turn,
            "thread_id": effective_thread_id,
            "handoff": handoff_event,
            "background_start": True,
            "warning": str(exc),
            "attachment_diagnostics": self._attachment_diagnostics(
                attachments,
                provider_id=str(profile.get("provider_id") or ""),
                model_id=str(model or profile.get("model") or ""),
                context_mode=context_mode,
            ),
            "context_budget_report": dict(context_budget_report or {}) or None,
            "turn_transition": compact_turn_transition(turn_transition),
            "route_admission": dict(route_admission or {}),
        }

    def compact_thread(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        client = self._ensure_client(runtime_status)
        try:
            client.request("thread/compact/start", {"threadId": thread_id})
        except JsonRpcError as exc:
            message = str(exc)
            if self._is_thread_not_found_error(exc):
                failure = classify_runtime_failure(
                    '{"error":{"message":"provider thread missing","type":"runtime_error"}}',
                    current_provider=str(profile.get("provider_id") or ""),
                    current_model=str(profile.get("model") or ""),
                ).to_payload()
                self._mark_provider_thread_missing(thread_id, reason="compact_thread_not_found")
                self._record_event(
                    {
                        "type": "thread_compact_blocked",
                        "thread_id": thread_id,
                        "status": "thread_missing",
                        "reason": "thread_not_found",
                        "failure": failure,
                        "runtime": runtime_status,
                    }
                )
                return {
                    "started": False,
                    "thread_id": thread_id,
                    "status": "thread_missing",
                    "recoverable": True,
                    "recommended_action": failure.get("recommended_action") or "restart_runtime_lane",
                    "recommended_actions": list(failure.get("recommended_actions") or []),
                    "recoverability": failure.get("recoverability") or "recoverable",
                    "message": " ".join(
                        part
                        for part in [
                            str(failure.get("summary") or "").strip(),
                            str(failure.get("actionable_hint") or "").strip(),
                        ]
                        if part
                    ).strip(),
                }
            raise
        self._record_event({"type": "thread_compact_requested", "thread_id": thread_id, "runtime": runtime_status})
        return {"started": True, "thread_id": thread_id}

    def allow_context_guard_continue_once(self, thread_id: str) -> dict[str, Any]:
        clean_thread_id = thread_id.strip()
        if not clean_thread_id:
            raise ValueError("thread_id is required.")
        self._context_guard_continue_once.add(clean_thread_id)
        self._record_event({"type": "context_guard_continue_once_allowed", "thread_id": clean_thread_id})
        return {"allowed": True, "thread_id": clean_thread_id}

    def reload_mcp_servers(self, profile: dict[str, Any]) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        result = client.request("config/mcpServer/reload", None)
        self._record_event({"type": "mcp_reloaded", "runtime": runtime_status})
        return {"reloaded": True, "result": result}

    def list_mcp_status(self, profile: dict[str, Any], *, thread_id: str | None = None, detail: str = "toolsAndAuthOnly") -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        effective_thread_id = str(thread_id or "").strip()
        if not effective_thread_id:
            effective_thread_id = self._ensure_mcp_status_thread(client, profile=profile, runtime_status=runtime_status)
        params = {"detail": detail if detail in {"full", "toolsAndAuthOnly"} else "toolsAndAuthOnly"}
        params["threadId"] = effective_thread_id
        try:
            result = client.request("mcpServerStatus/list", params)
        except JsonRpcError as exc:
            if thread_id or not self._is_thread_not_found_error(exc):
                raise
            self._clear_mcp_status_thread()
            effective_thread_id = self._ensure_mcp_status_thread(client, profile=profile, runtime_status=runtime_status)
            params["threadId"] = effective_thread_id
            result = client.request("mcpServerStatus/list", params)
        self._record_event({"type": "mcp_status_listed", "count": len(result.get("data") or []), "thread_id": effective_thread_id, "runtime": runtime_status})
        return {"servers": list(result.get("data") or []), "next_cursor": result.get("nextCursor"), "thread_id": effective_thread_id}

    def _ensure_mcp_status_thread(self, client: AppServerClient, *, profile: dict[str, Any], runtime_status: dict[str, Any]) -> str:
        signature = self._runtime_config.runtime_signature(runtime_status)
        with self._lock:
            cached_thread_id = self._mcp_status_thread_id if self._mcp_status_thread_signature == signature else None
        if cached_thread_id:
            return cached_thread_id
        result = client.request(
            "thread/start",
            self._thread_start_params(profile=profile, model=None, permission_mode="auto"),
            timeout=THREAD_START_TIMEOUT_SECONDS,
        )
        thread = dict(result.get("thread") or {})
        status_thread_id = str(thread.get("id") or "")
        if not status_thread_id:
            raise RuntimeError("thread/start did not return a thread id for MCP status.")
        with self._lock:
            self._mcp_status_thread_signature = signature
            self._mcp_status_thread_id = status_thread_id
        self._record_event({"type": "mcp_status_internal_thread_started", "thread_id": status_thread_id, "runtime": runtime_status})
        return status_thread_id

    def _clear_mcp_status_thread(self) -> None:
        with self._lock:
            self._mcp_status_thread_signature = None
            self._mcp_status_thread_id = None

    def call_mcp_tool(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        server: str,
        tool: str,
        arguments: Any | None = None,
        preserve_active_thread: bool = True,
    ) -> dict[str, Any]:
        if not server.strip() or not tool.strip():
            raise ValueError("MCP server and tool are required.")
        tool_timeout = self._mcp_tool_timeout_seconds(server)
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        prior_project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "")
        prior_task_thread_id = ""
        prior_task_thread_settings: dict[str, Any] = {}
        restore_project_thread_id = prior_project_thread_id
        restore_task_thread_id = prior_task_thread_id
        if self._tasks is not None:
            prior_task = self._tasks.current_task() or {}
            prior_task_thread_id = str(prior_task.get("active_provider_thread_id") or "")
            restore_task_thread_id = prior_task_thread_id
            for item in list(prior_task.get("provider_threads") or []):
                if str(item.get("thread_id") or "") == prior_task_thread_id:
                    prior_task_thread_settings = dict(item)
                    break
        source_thread_id = (
            thread_id.strip()
            or str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
            or self._visible_task_thread_id_hint()
        )
        if source_thread_id and not restore_task_thread_id:
            restore_task_thread_id = source_thread_id
        if source_thread_id and not restore_project_thread_id:
            restore_project_thread_id = source_thread_id
        effective_thread_id = self._resolve_thread_for_direct_mcp_call(
            client,
            source_thread_id=source_thread_id,
            profile=profile,
        )
        if source_thread_id:
            if self._tasks is not None:
                projected_task = self._tasks.current_task() or {}
                projected_task_thread_id = str(projected_task.get("active_provider_thread_id") or "")
                projected_project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "")
                if projected_task_thread_id or projected_project_thread_id:
                    if projected_task_thread_id != source_thread_id or projected_project_thread_id != source_thread_id:
                        restore_task_thread_id = projected_task_thread_id or restore_task_thread_id
                        restore_project_thread_id = projected_project_thread_id or projected_task_thread_id or restore_project_thread_id
            else:
                projected_project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "")
                if projected_project_thread_id != source_thread_id:
                    restore_project_thread_id = projected_project_thread_id
        handoff_event: dict[str, Any] | None = None
        try:
            result = client.request(
                "mcpServer/tool/call",
                {"threadId": effective_thread_id, "server": server, "tool": tool, "arguments": arguments or {}},
                timeout=tool_timeout,
            )
        except JsonRpcError as exc:
            if not self._is_thread_not_found_error(exc):
                raise
            self._record_event(
                {
                    "type": "mcp_tool_thread_missing",
                    "thread_id": effective_thread_id,
                    "source_thread_id": source_thread_id,
                    "server": server,
                    "tool": tool,
                }
            )
            recovered_thread_id = self._resolve_thread_for_direct_mcp_call(
                client,
                source_thread_id=source_thread_id,
                profile=profile,
            )
            result = client.request(
                "mcpServer/tool/call",
                {"threadId": recovered_thread_id, "server": server, "tool": tool, "arguments": arguments or {}},
                timeout=tool_timeout,
            )
            effective_thread_id = recovered_thread_id
        usage_delta = self._record_yunwu_image_usage_from_tool_result(server=server, tool=tool, result=result)
        self._record_event(
            {
                "type": "mcp_tool_called",
                "server": server,
                "tool": tool,
                "thread_id": effective_thread_id,
                "source_thread_id": source_thread_id,
                "handoff_event": handoff_event,
                "usage_delta": usage_delta,
                "runtime": runtime_status,
            }
        )
        if preserve_active_thread:
            self._restore_active_thread_after_direct_mcp_tool_call(
                project_thread_id=restore_project_thread_id,
                task_thread_id=restore_task_thread_id,
                task_thread_settings=prior_task_thread_settings,
            )
        return {"result": result, "thread_id": effective_thread_id, "handoff_event": handoff_event, "usage_delta": usage_delta}

    def _restore_active_thread_after_direct_mcp_tool_call(
        self,
        *,
        project_thread_id: str,
        task_thread_id: str,
        task_thread_settings: dict[str, Any],
    ) -> None:
        """Direct tools may need an internal runtime thread, but must not steal UI focus."""
        restored: dict[str, str] = {}
        if project_thread_id:
            try:
                self._projects.switch_thread(project_thread_id)
                restored["project_thread_id"] = project_thread_id
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "mcp_tool_project_thread_restore_failed", "thread_id": project_thread_id, "error": str(exc)[:300]})
        if self._tasks is not None and task_thread_id:
            try:
                self._tasks.restore_active_provider_thread(task_thread_id)
                restored_task = self._tasks.current_task()
                if str((restored_task or {}).get("active_provider_thread_id") or "").strip() != task_thread_id:
                    self._tasks.force_visible_provider_thread(task_thread_id)
                    restored_task = self._tasks.current_task()
                restored["task_thread_id"] = task_thread_id
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "mcp_tool_task_thread_restore_failed", "thread_id": task_thread_id, "error": str(exc)[:300]})
        if task_thread_id and not str((self._projects.current_project or {}).get("current_thread_id") or "").strip():
            try:
                self._projects.switch_thread(task_thread_id)
                restored.setdefault("project_thread_id", task_thread_id)
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "mcp_tool_project_thread_fallback_restore_failed", "thread_id": task_thread_id, "error": str(exc)[:300]})
        if restored:
            self._record_event({"type": "mcp_tool_active_thread_restored", **restored})
        if self._tasks is not None:
            try:
                current_task = self._tasks.current_task() or {}
                if current_task:
                    self._projects.reconcile_task_projection(current_task)
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "mcp_tool_task_projection_reconcile_failed", "error": str(exc)[:300]})

    def _resolve_thread_for_direct_mcp_call(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
    ) -> str:
        """Find or create an internal app-server thread for direct tool calls.

        Direct MCP calls are UI/supervisor actions, not provider switches. They
        may need a thread id because the app-server API requires one, but that
        thread must not become part of the user-visible task/provider-thread
        graph. Otherwise image generation, web research, or browser smoke can
        make a task look like it switched models or lost its active thread.
        """
        clean_source = source_thread_id.strip()
        result = client.request(
            "thread/start",
            self._thread_start_params(profile=profile, model=None, permission_mode="auto"),
            timeout=THREAD_START_TIMEOUT_SECONDS,
        )
        thread = dict(result.get("thread") or {})
        target_thread_id = str(thread.get("id") or "")
        if not target_thread_id:
            raise RuntimeError("thread/start did not return a thread id for MCP tool call.")
        self._record_event(
            {
                "type": "mcp_tool_internal_thread_started",
                "thread_id": target_thread_id,
                "source_thread_id": clean_source,
                "reason": "direct_tool_context_isolated",
            }
        )
        return target_thread_id

    def _visible_task_thread_id_hint(self) -> str:
        if self._tasks is None:
            return ""
        try:
            return str(self._tasks.visible_provider_thread_id(include_missing_fallback=True) or "").strip()
        except Exception:
            return ""

    def _mcp_tool_timeout_seconds(self, server: str) -> float:
        try:
            for item in self._mcp_config.enabled_servers():
                if str(item.get("name") or "") != server:
                    continue
                return max(float(item.get("tool_timeout_sec") or 120.0), 1.0)
        except Exception:
            return 120.0
        return 120.0

    def _ensure_provider_thread_for_mcp_call(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
        force_fresh: bool = False,
    ) -> tuple[str, dict[str, Any] | None]:
        """Return an isolated internal thread for direct tool calls.

        Kept as a compatibility wrapper for older call sites. Direct MCP/tool
        calls must not become provider handoffs and must not mark the visible
        source thread missing when the tool runtime belongs to another provider.
        """
        del force_fresh
        return self._resolve_thread_for_direct_mcp_call(client, source_thread_id=source_thread_id, profile=profile), None

    def _record_yunwu_image_usage_from_tool_result(self, *, server: str, tool: str, result: Any) -> dict[str, int]:
        if server not in {"yunwu_image", "astrabridge_capabilities"} and not tool.startswith(("yunwu_image_", "astrabridge_capability_image_generate")):
            return {}
        self._refresh_asset_registry_after_yunwu_tool(tool=tool)
        actual_n = self._extract_yunwu_actual_n(result)
        if actual_n <= 0:
            return {}
        delta = {"yunwu_images": actual_n}
        if self._dogfood_run is not None:
            try:
                self._dogfood_run.record_usage(delta)
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "dogfood_usage_record_failed", "delta": delta, "error": str(exc)[:300]})
        return delta

    def _refresh_asset_registry_after_yunwu_tool(self, *, tool: str) -> None:
        if self._asset_registry is None:
            return
        try:
            response = self._asset_registry.rebuild()
            registry = dict(response.get("registry") or {})
            assets = list(registry.get("assets") or [])
            self._record_event(
                {
                    "type": "asset_registry_refreshed",
                    "source": "yunwu_image_tool",
                    "tool": tool,
                    "asset_count": len(assets),
                }
            )
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                {
                    "type": "asset_registry_refresh_failed",
                    "source": "yunwu_image_tool",
                    "tool": tool,
                    "error": str(exc)[:300],
                }
            )

    def _extract_yunwu_actual_n(self, result: Any) -> int:
        if isinstance(result, dict):
            direct = result.get("actual_n")
            if isinstance(direct, int):
                return max(0, direct)
            if isinstance(direct, str) and direct.isdigit():
                return int(direct)
            content = result.get("content")
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text") or "")
                    actual_n = self._extract_actual_n_from_text(text)
                    if actual_n > 0:
                        return actual_n
        return 0

    @staticmethod
    def _extract_actual_n_from_text(text: str) -> int:
        if not text:
            return 0
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return 0
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return 0
        actual = payload.get("actual_n")
        if isinstance(actual, int):
            return max(0, actual)
        if isinstance(actual, str) and actual.isdigit():
            return int(actual)
        return 0

    def _update_project_runtime_defaults(
        self,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        *,
        route_admission: dict[str, Any] | None = None,
    ) -> None:
        route = dict(dict(route_admission or {}).get("route") or {})
        if route_admission is not None and not bool(route.get("default_route_eligible")):
            self._record_event(
                {
                    "type": "runtime_default_route_not_promoted",
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "model": model or profile.get("model"),
                    "route_admission": deepcopy(route_admission),
                }
            )
            return
        self._projects.update_project(
            {
                "default_profile_id": profile.get("profile_id"),
                "default_model": model or profile.get("model"),
                "default_effort": effort or profile.get("reasoning_effort"),
            }
        )

    def _task_thread_settings(
        self,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        *,
        collaboration_mode: str | None = None,
        execution_backend: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        route_admission = dict(profile.get("_runtime_route_admission") or {})
        effective_route = dict(route_admission.get("effective") or {})
        settings = {
            "name": name,
            "profile_id": profile.get("profile_id"),
            "provider_id": profile.get("provider_id"),
            "model": model or profile.get("model"),
            "reasoning_effort": effort or profile.get("reasoning_effort"),
            "permission_mode": permission_mode,
            "execution_backend": self._normalize_execution_backend(
                execution_backend or effective_route.get("execution_backend") or profile.get("execution_backend")
            ),
        }
        if route_admission:
            settings.update(
                {
                    "execution_route_status": route_admission.get("status"),
                    "execution_route_driver": effective_route.get("execution_driver"),
                    "execution_route_authority_tier": effective_route.get("authority_tier"),
                    "execution_route_presentation": route_admission.get("presentation_state"),
                    "execution_route_default_eligible": bool(dict(route_admission.get("route") or {}).get("default_route_eligible")),
                }
            )
        if collaboration_mode is not None:
            settings["collaboration_mode"] = collaboration_mode or "default"
        return settings

    def _ensure_provider_thread_for_turn(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        context_mode: str = "default",
        include_dynamic_tools: bool = True,
        allowed_mcp_tool_names: set[str] | None = None,
        allow_browser_smoke: bool = True,
        turn_transition: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        turn_transition = turn_transition or self._build_turn_transition_for_start(
            source_thread_id=source_thread_id,
            profile=profile,
            model=model,
            effort=effort,
            execution_backend=profile.get("execution_backend"),
            context_mode=context_mode,
        )
        self._assert_turn_transition_admitted(
            turn_transition,
            source_thread_id=source_thread_id,
            phase="provider_thread_admission",
        )
        if self._tasks is None:
            return source_thread_id, None
        desired = self._task_thread_settings(profile, model, effort, permission_mode, collaboration_mode=collaboration_mode)
        force_fresh_contextless_thread = context_mode == "no_context"
        self._tasks.ensure_default_task()
        source_thread_available = True
        handoff_needed = True
        if source_thread_id:
            self._tasks.ensure_default_task(thread_id=source_thread_id)
            handoff_needed = self._tasks.needs_provider_handoff(
                thread_id=source_thread_id,
                profile_id=str(desired.get("profile_id") or ""),
                model=str(desired.get("model") or ""),
                effort=str(desired.get("reasoning_effort") or ""),
            )
        if source_thread_id and not handoff_needed and not self._thread_exists(client, source_thread_id):
            source_thread_available = False
            self._mark_provider_thread_missing(source_thread_id, reason="provider_handoff_source_missing")
        if source_thread_available and source_thread_id and not handoff_needed:
            if not force_fresh_contextless_thread:
                self._tasks.bind_thread(thread_id=source_thread_id, settings=desired, role="provider", make_active=True)
                return source_thread_id, None

        if force_fresh_contextless_thread:
            return self._start_fresh_provider_thread_for_turn(
                client,
                source_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                desired=desired,
                reason="no_context_fresh_thread",
                include_dynamic_tools=include_dynamic_tools,
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
                turn_transition=turn_transition,
            )

        reusable = self._tasks.find_provider_thread(
            profile_id=str(desired.get("profile_id") or ""),
            provider_id=str(desired.get("provider_id") or ""),
            model=str(desired.get("model") or ""),
            effort=str(desired.get("reasoning_effort") or ""),
        )
        reusable_thread_id = str((reusable or {}).get("thread_id") or "")
        if reusable_thread_id and reusable_thread_id != source_thread_id:
            if self._thread_exists(client, reusable_thread_id):
                self._prime_handoff_projection_source_thread(client, source_thread_id=source_thread_id)
                context_budget_report = self._project_context_budget_report(
                    thread_id=source_thread_id or reusable_thread_id,
                    profile_id=str(desired.get("profile_id") or ""),
                    provider_id=str(desired.get("provider_id") or ""),
                    model_id=str(desired.get("model") or ""),
                )
                handoff_bundle = self._provider_handoff_bundle(
                    source_thread_id=source_thread_id,
                    target_thread_id=reusable_thread_id,
                    target_provider_id=str(desired.get("provider_id") or ""),
                    target_model_id=str(desired.get("model") or ""),
                    projection_mode="reused_provider_thread",
                    target_context_budget_report=context_budget_report,
                )
                handoff_event = self._tasks.record_provider_handoff(
                    from_thread_id=source_thread_id,
                    to_thread_id=reusable_thread_id,
                    settings={**desired, "name": reusable.get("name") or desired.get("name")},
                    reused_existing=True,
                    context_budget_report=context_budget_report,
                    neutral_handoff_bundle=handoff_bundle,
                    turn_transition=self._complete_turn_transition(
                        turn_transition,
                        target_thread_id=reusable_thread_id,
                        reused_existing=True,
                        completion_status="reused_target_lane_selected",
                    ),
                    **self._handoff_projection_kwargs(
                        source_thread_id=source_thread_id,
                        target_provider_id=str(desired.get("provider_id") or ""),
                        target_model_id=str(desired.get("model") or "") or None,
                    ),
                )
                self._projects.switch_thread(reusable_thread_id)
                self._record_event(
                    {
                        "type": "provider_handoff",
                        "from_thread_id": source_thread_id,
                        "to_thread_id": reusable_thread_id,
                        "profile_id": desired.get("profile_id"),
                        "provider_id": desired.get("provider_id"),
                        "model": desired.get("model"),
                        "reasoning_effort": desired.get("reasoning_effort"),
                        "reused_existing": True,
                    }
                )
                return reusable_thread_id, handoff_event
            self._mark_provider_thread_missing(reusable_thread_id, reason="provider_handoff_target_missing")

        if not source_thread_available:
            return self._recover_missing_provider_thread(
                client,
                missing_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                collaboration_mode=collaboration_mode,
                reason="provider_handoff_source_missing",
                include_dynamic_tools=include_dynamic_tools,
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
                turn_transition=turn_transition,
            )

        if not source_thread_id:
            return self._start_fresh_provider_thread_for_turn(
                client,
                source_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                desired=desired,
                reason="provider_handoff_no_source_thread",
                include_dynamic_tools=include_dynamic_tools,
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
                turn_transition=turn_transition,
            )

        if handoff_needed:
            # A provider switch is not the same as an official Codex fork in AstraBridge:
            # the target provider's app-server cannot reliably read or fork a
            # thread owned by the source provider runtime. Keep task continuity
            # through the AstraBridge task/project/asset context pack, and reserve
            # thread/fork for same-runtime forks.
            return self._start_fresh_provider_thread_for_turn(
                client,
                source_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                desired=desired,
                reason="provider_handoff_cross_provider_fresh_thread",
                include_dynamic_tools=include_dynamic_tools,
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
                turn_transition=turn_transition,
            )

        params = {
            "threadId": source_thread_id,
            **self._thread_start_params(
                profile=profile,
                model=model,
                permission_mode=permission_mode,
                include_dynamic_tools=include_dynamic_tools,
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
            ),
        }
        try:
            result = client.request("thread/fork", params, timeout=THREAD_FORK_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            self._record_event(
                {
                    "type": "provider_handoff_timeout",
                    "from_thread_id": source_thread_id,
                    "profile_id": desired.get("profile_id"),
                    "model": desired.get("model"),
                }
            )
            raise RuntimeError(
                "Provider switch is blocked: Codex app-server did not preserve the task context into the target provider thread in time."
            ) from exc
        except JsonRpcError as exc:
            if not self._is_thread_not_found_error(exc):
                raise
            self._mark_provider_thread_missing(source_thread_id, reason="provider_handoff_source_missing")
            return self._recover_missing_provider_thread(
                client,
                missing_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                collaboration_mode=collaboration_mode,
                reason="provider_handoff_source_missing",
                include_dynamic_tools=include_dynamic_tools,
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
                turn_transition=turn_transition,
            )
        thread = dict(result.get("thread") or {})
        target_thread_id = str(thread.get("id") or "")
        if not target_thread_id:
            raise RuntimeError("Provider handoff did not return a target thread id.")
        desired["name"] = thread.get("name") or desired.get("name")
        self._cache_thread_entry(target_thread_id, desired)
        self._prime_handoff_projection_source_thread(client, source_thread_id=source_thread_id)
        context_budget_report = self._project_context_budget_report(
            thread_id=source_thread_id or target_thread_id,
            profile_id=str(desired.get("profile_id") or ""),
            provider_id=str(desired.get("provider_id") or ""),
            model_id=str(desired.get("model") or ""),
        )
        handoff_bundle = self._provider_handoff_bundle(
            source_thread_id=source_thread_id,
            target_thread_id=target_thread_id,
            target_provider_id=str(desired.get("provider_id") or ""),
            target_model_id=str(desired.get("model") or ""),
            projection_mode="task_context_fresh_thread",
            target_context_budget_report=context_budget_report,
        )
        handoff_event = self._tasks.record_provider_handoff(
            from_thread_id=source_thread_id,
            to_thread_id=target_thread_id,
            settings=desired,
            reused_existing=False,
            context_budget_report=context_budget_report,
            neutral_handoff_bundle=handoff_bundle,
            turn_transition=self._complete_turn_transition(
                turn_transition,
                target_thread_id=target_thread_id,
                reused_existing=False,
                completion_status="forked_target_lane_started",
            ),
            **self._handoff_projection_kwargs(
                source_thread_id=source_thread_id,
                target_provider_id=str(desired.get("provider_id") or ""),
                target_model_id=str(desired.get("model") or "") or None,
            ),
        )
        self._record_event(
            {
                "type": "provider_handoff",
                "from_thread_id": source_thread_id,
                "to_thread_id": target_thread_id,
                "profile_id": desired.get("profile_id"),
                "model": desired.get("model"),
                "reasoning_effort": desired.get("reasoning_effort"),
                "reused_existing": False,
            }
        )
        return target_thread_id, handoff_event

    def _start_fresh_provider_thread_for_turn(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        desired: dict[str, Any],
        reason: str,
        include_dynamic_tools: bool = True,
        allowed_mcp_tool_names: set[str] | None = None,
        allow_browser_smoke: bool = True,
        turn_transition: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        turn_transition = turn_transition or self._build_turn_transition_for_start(
            source_thread_id=source_thread_id,
            profile=profile,
            model=model,
            effort=effort,
            execution_backend=desired.get("execution_backend") or profile.get("execution_backend"),
            context_mode="no_context" if "fresh_thread" in reason else "default",
            transition_context={"trigger": reason},
        )
        self._assert_turn_transition_admitted(
            turn_transition,
            source_thread_id=source_thread_id,
            phase="fresh_provider_thread_start",
        )
        params = self._thread_start_params(
            profile=profile,
            model=model,
            permission_mode=permission_mode,
            include_dynamic_tools=include_dynamic_tools,
            allowed_mcp_tool_names=allowed_mcp_tool_names,
            allow_browser_smoke=allow_browser_smoke,
        )
        result = client.request("thread/start", params, timeout=THREAD_START_TIMEOUT_SECONDS)
        thread = dict(result.get("thread") or {})
        target_thread_id = str(thread.get("id") or "")
        if not target_thread_id:
            raise RuntimeError("thread/start did not return a target thread id.")
        desired["name"] = thread.get("name") or desired.get("name")
        self._cache_thread_entry(target_thread_id, desired)
        # A health/no-context retry deliberately starts with a reduced
        # projection.  Reading the source provider thread here both defeats
        # that contract and can pull provider-private state into a lane that
        # was explicitly selected to avoid it.
        if reason not in {"minimal_text_fresh_thread", "no_context_fresh_thread"}:
            self._prime_handoff_projection_source_thread(client, source_thread_id=source_thread_id)
        context_budget_report = self._project_context_budget_report(
            thread_id=source_thread_id or target_thread_id,
            profile_id=str(desired.get("profile_id") or ""),
            provider_id=str(desired.get("provider_id") or ""),
            model_id=str(desired.get("model") or ""),
        )
        handoff_bundle = self._provider_handoff_bundle(
            source_thread_id=source_thread_id,
            target_thread_id=target_thread_id,
            target_provider_id=str(desired.get("provider_id") or ""),
            target_model_id=str(desired.get("model") or ""),
            projection_mode="task_context_fresh_thread",
            target_context_budget_report=context_budget_report,
        )
        handoff_event = self._tasks.record_provider_handoff(
            from_thread_id=source_thread_id,
            to_thread_id=target_thread_id,
            settings=desired,
            reused_existing=False,
            context_budget_report=context_budget_report,
            neutral_handoff_bundle=handoff_bundle,
            turn_transition=self._complete_turn_transition(
                turn_transition,
                target_thread_id=target_thread_id,
                reused_existing=False,
                completion_status="fresh_target_lane_started",
            ),
            **self._handoff_projection_kwargs(
                source_thread_id=source_thread_id,
                target_provider_id=str(desired.get("provider_id") or ""),
                target_model_id=str(desired.get("model") or "") or None,
            ),
        )
        self._projects.switch_thread(target_thread_id)
        self._record_event(
            {
                "type": "provider_handoff",
                "from_thread_id": source_thread_id,
                "to_thread_id": target_thread_id,
                "profile_id": desired.get("profile_id"),
                "provider_id": desired.get("provider_id"),
                "model": desired.get("model"),
                "reasoning_effort": desired.get("reasoning_effort"),
                "reused_existing": False,
                "reason": reason,
            }
        )
        return target_thread_id, handoff_event

    def _recover_missing_provider_thread(
        self,
        client: AppServerClient,
        *,
        missing_thread_id: str,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        reason: str,
        include_dynamic_tools: bool = True,
        allowed_mcp_tool_names: set[str] | None = None,
        allow_browser_smoke: bool = True,
        turn_transition: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        desired = self._task_thread_settings(
            profile,
            model,
            effort,
            permission_mode,
            collaboration_mode=collaboration_mode,
            name="Recovered provider thread",
        )
        turn_transition = turn_transition or self._build_turn_transition_for_start(
            source_thread_id=missing_thread_id,
            profile=profile,
            model=model,
            effort=effort,
            execution_backend=desired.get("execution_backend") or profile.get("execution_backend"),
            context_mode="no_context",
            transition_context={
                "trigger": reason,
                "failure_notice": classify_runtime_failure(
                    "provider thread missing",
                    current_provider=str(profile.get("provider_id") or ""),
                    current_model=str(model or profile.get("model") or ""),
                ).to_payload(),
            },
        )
        self._assert_turn_transition_admitted(
            turn_transition,
            source_thread_id=missing_thread_id,
            phase="missing_provider_thread_recovery",
        )
        params = self._thread_start_params(
            profile=profile,
            model=model,
            permission_mode=permission_mode,
            include_dynamic_tools=include_dynamic_tools,
            allowed_mcp_tool_names=allowed_mcp_tool_names,
            allow_browser_smoke=allow_browser_smoke,
        )
        result = client.request("thread/start", params, timeout=THREAD_START_TIMEOUT_SECONDS)
        thread = dict(result.get("thread") or {})
        target_thread_id = str(thread.get("id") or "")
        if not target_thread_id:
            raise RuntimeError("thread/start did not return a replacement thread id.")
        desired["name"] = thread.get("name") or desired.get("name")
        self._cache_thread_entry(target_thread_id, desired)
        handoff_event = None
        if self._tasks is not None:
            self._prime_handoff_projection_source_thread(client, source_thread_id=missing_thread_id)
            context_budget_report = self._project_context_budget_report(
                thread_id=missing_thread_id or target_thread_id,
                profile_id=str(desired.get("profile_id") or ""),
                provider_id=str(desired.get("provider_id") or ""),
                model_id=str(desired.get("model") or ""),
            )
            handoff_bundle = self._provider_handoff_bundle(
                source_thread_id=missing_thread_id,
                target_thread_id=target_thread_id,
                target_provider_id=str(desired.get("provider_id") or ""),
                target_model_id=str(desired.get("model") or ""),
                projection_mode="task_context_fresh_thread",
                target_context_budget_report=context_budget_report,
            )
            handoff_event = self._tasks.record_provider_handoff(
                from_thread_id=missing_thread_id,
                to_thread_id=target_thread_id,
                settings=desired,
                reused_existing=False,
                context_budget_report=context_budget_report,
                neutral_handoff_bundle=handoff_bundle,
                turn_transition=self._complete_turn_transition(
                    turn_transition,
                    target_thread_id=target_thread_id,
                    reused_existing=False,
                    completion_status="missing_thread_recovery_lane_started",
                ),
                **self._handoff_projection_kwargs(
                    source_thread_id=missing_thread_id,
                    target_provider_id=str(desired.get("provider_id") or ""),
                    target_model_id=str(desired.get("model") or "") or None,
                ),
            )
        self._projects.switch_thread(target_thread_id)
        self._record_event(
            {
                "type": "provider_thread_recovered",
                "reason": reason,
                "missing_thread_id": missing_thread_id,
                "replacement_thread_id": target_thread_id,
                "profile_id": desired.get("profile_id"),
                "model": desired.get("model"),
                "reasoning_effort": desired.get("reasoning_effort"),
            }
        )
        return target_thread_id, handoff_event

    def interrupt_turn(self, profile: dict[str, Any], thread_id: str, turn_id: str) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        resolved_turn_id = turn_id
        try:
            result = client.request("turn/interrupt", {"threadId": thread_id, "turnId": resolved_turn_id})
        except JsonRpcError as exc:
            if self._is_thread_not_found_error(exc):
                self._mark_provider_thread_missing(thread_id, reason="turn_interrupt_thread_missing")
                self._record_event(
                    {
                        "type": "provider_thread_missing",
                        "reason": "turn_interrupt_thread_missing",
                        "thread_id": thread_id,
                        "turn_id": resolved_turn_id,
                        "runtime": runtime_status,
                    }
                )
                return {
                    "interrupt": {
                        "ok": False,
                        "status": "thread_missing",
                        "thread_id": thread_id,
                        "turn_id": resolved_turn_id,
                    }
                }
            active_turn_id = self._active_turn_id_from_interrupt_error(str(exc))
            if not active_turn_id or active_turn_id == turn_id:
                raise
            self._record_event(
                {
                    "type": "turn_interrupt_retry",
                    "thread_id": thread_id,
                    "requested_turn_id": turn_id,
                    "active_turn_id": active_turn_id,
                    "runtime": runtime_status,
                }
            )
            resolved_turn_id = active_turn_id
            result = client.request("turn/interrupt", {"threadId": thread_id, "turnId": resolved_turn_id})
        self._record_event(
            {
                "type": "turn_interrupted",
                "thread_id": thread_id,
                "turn_id": resolved_turn_id,
                "requested_turn_id": turn_id,
                "runtime": runtime_status,
            }
        )
        self._clear_runtime_pin(thread_id=thread_id, turn_id=resolved_turn_id, reason="turn_interrupted")
        cancelled_modals = self._modals.cancel_for_turn(
            thread_id,
            resolved_turn_id,
            reason="Turn was interrupted; pending approval is no longer actionable.",
        )
        return {"interrupt": result, "cancelled_modals": cancelled_modals}

    @staticmethod
    def _active_turn_id_from_interrupt_error(message: str) -> str | None:
        match = re.search(r"expected active turn id [0-9a-f-]+ but found ([0-9a-f-]+)", message, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _is_thread_not_found_error(error: Exception) -> bool:
        message = str(error).lower()
        return (
            "thread not found" in message
            or "thread not loaded" in message
            or "invalid thread id" in message
        )

    def _thread_exists(self, client: AppServerClient, thread_id: str, *, timeout: float | None = None) -> bool:
        if not str(thread_id or "").strip():
            return False
        try:
            client.request(
                "thread/read",
                {"threadId": thread_id, "includeTurns": False},
                timeout=THREAD_READ_TIMEOUT_SECONDS if timeout is None else timeout,
            )
            return True
        except JsonRpcError as exc:
            if self._is_thread_not_found_error(exc):
                return False
            raise

    def _mark_provider_thread_missing(self, thread_id: str, *, reason: str) -> None:
        if self._tasks is not None:
            try:
                self._tasks.mark_provider_thread_missing(thread_id, reason=reason)
            except Exception:
                pass
            try:
                self._tasks.current_task()
            except Exception:
                pass
        self._record_event(
            {
                "type": "provider_thread_missing",
                "reason": reason,
                "thread_id": thread_id,
            }
        )

    def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, Any]:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            if limit is not None and limit > 0 and after <= 0:
                start = max(0, len(self._events) - limit)
                events = self._events[start:]
            else:
                events = self._events[after:]
                if limit is not None and limit > 0:
                    events = events[:limit]
            cursor = len(self._events)
        return {"cursor": cursor, "events": [self._event_for_response(item) for item in events]}

    def _hydrate_events_from_disk_locked(self) -> None:
        try:
            shell_root = self._projects.require_shell_state_root()
        except Exception:
            return
        path = shell_root / "runtime_events.jsonl"
        if self._hydrated_event_log_path == path:
            return
        loaded: deque[dict[str, Any]] = deque(maxlen=EVENT_HYDRATE_TAIL_LIMIT)
        if path.is_file():
            try:
                size = path.stat().st_size
                with path.open("rb") as handle:
                    if size > EVENT_HYDRATE_MAX_BYTES:
                        handle.seek(-EVENT_HYDRATE_MAX_BYTES, os.SEEK_END)
                    payload = handle.read(EVENT_HYDRATE_MAX_BYTES + 1)
                lines = payload.decode("utf-8", errors="replace").splitlines()
                if size > EVENT_HYDRATE_MAX_BYTES and lines:
                    lines = lines[1:]
                for line in lines[-EVENT_HYDRATE_TAIL_LIMIT:]:
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        item = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict):
                        loaded.append(enrich_runtime_event(redact_sensitive(item)))
            except Exception:
                return
        host_events = load_host_lineage_events(shell_root.parent)
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*list(loaded), *host_events, *self._events]:
            fingerprint = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            merged.append(item)
        self._events = merged
        for index, item in enumerate(self._events):
            item["index"] = index
        self._hydrated_event_log_path = path

    def record_supervisor_event(self, event: dict[str, Any]) -> None:
        self._record_event({"type": "runtime_supervisor", **event})

    def record_external_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        clean_type = str(event_type or "").strip()
        if not clean_type:
            raise ValueError("event_type is required.")
        self._record_event({"type": clean_type, **dict(payload or {})})

    def request_native_command_approval(
        self,
        *,
        thread_id: str,
        turn_id: str,
        command: str,
        cwd: str,
        reason: str,
    ) -> dict[str, Any]:
        return dict(
            self._modals.request(
                "item/commandExecution/requestApproval",
                {
                    "threadId": thread_id,
                    "turnId": turn_id,
                    "itemId": new_id("cmd"),
                    "command": command,
                    "cwd": cwd,
                    "reason": reason,
                },
            )
            or {}
        )

    def _raise_if_context_guard_blocks_turn(self, client: AppServerClient, thread_id: str) -> None:
        state = self._context_guard_state(thread_id)
        if state.get("level") == "compacting":
            self._record_event(
                {
                    "type": "context_guard_compaction_in_progress",
                    "thread_id": thread_id,
                    "turn_id": state.get("turn_id"),
                    "started_at": state.get("started_at"),
                }
            )
            raise RuntimeError("Context compaction is still running for this thread. Wait for compaction to finish before starting the next turn.")
        if state.get("level") != "pause":
            return
        if not self._thread_exists(client, thread_id):
            self._mark_provider_thread_missing(thread_id, reason="context_guard_thread_missing")
            return
        if thread_id in self._context_guard_continue_once:
            self._context_guard_continue_once.remove(thread_id)
            self._record_event(
                {
                    "type": "context_guard_continue_once_consumed",
                    "thread_id": thread_id,
                    "context_percent": state.get("context_percent"),
                    "turn_id": state.get("turn_id"),
                }
            )
            return
        self._record_event(
            {
                "type": "context_guard_turn_blocked",
                "thread_id": thread_id,
                "turn_id": state.get("turn_id"),
                "context_percent": state.get("context_percent"),
                "recommended_action": "compact",
            }
        )
        raise RuntimeError(
            "Context is above 90% for this thread. Compact context, fork/switch provider thread, "
            "or explicitly choose Continue once before starting another long turn."
        )

    def _context_guard_state(self, thread_id: str) -> dict[str, Any]:
        token = self._latest_context_token_usage(thread_id)
        if not token:
            return {"level": "ok", "context_percent": 0}
        token_at = token.get("last_updated_at")
        missing_at = self._latest_provider_thread_missing_timestamp(thread_id)
        if missing_at and (not token_at or self._timestamp_after(str(missing_at), str(token_at))):
            return {
                "level": "missing",
                "context_percent": token.get("context_percent"),
                "turn_id": token.get("turn_id"),
                "missing_at": missing_at,
            }
        compacted_at = self._latest_completed_compaction_timestamp(thread_id)
        if compacted_at and (not token_at or self._timestamp_after(str(compacted_at), str(token_at))):
            return {
                "level": "compacted",
                "context_percent": token.get("context_percent"),
                "turn_id": token.get("turn_id"),
            }
        running_compaction = self._latest_running_compaction(thread_id)
        if running_compaction:
            compaction_turn_id = str(running_compaction.get("turn_id") or "")
            if compaction_turn_id and compaction_turn_id == str(token.get("turn_id") or ""):
                return {
                    "level": "compacting",
                    "context_percent": token.get("context_percent"),
                    "turn_id": compaction_turn_id,
                    "started_at": running_compaction.get("started_at"),
                }
        percent = float(token.get("context_percent") or 0)
        return {
            "level": "pause" if percent >= 90 else "ok",
            "context_percent": percent,
            "turn_id": token.get("turn_id"),
            "last_updated_at": token_at,
        }

    def _latest_context_token_usage(self, thread_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        for event in reversed(events):
            if event.get("type") != "notification" or event.get("method") != "thread/tokenUsage/updated":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            usage = params.get("tokenUsage") or {}
            total = usage.get("total") or {}
            last = usage.get("last") or {}
            context_window = int(usage.get("modelContextWindow") or 0)
            cumulative_total_tokens = int(total.get("totalTokens") or 0)
            context_tokens = int(last.get("inputTokens") or last.get("totalTokens") or cumulative_total_tokens or 0)
            context_source = "last.inputTokens" if int(last.get("inputTokens") or 0) > 0 else (
                "last.totalTokens" if int(last.get("totalTokens") or 0) > 0 else "total.totalTokens"
            )
            percent = round((context_tokens / context_window) * 100, 1) if context_window > 0 else 0
            return {
                "total_tokens": context_tokens,
                "context_estimate_tokens": context_tokens,
                "context_estimate_source": context_source,
                "cumulative_total_tokens": cumulative_total_tokens,
                "context_window": context_window,
                "context_percent": percent,
                "turn_id": str(params.get("turnId") or ""),
                "total": total,
                "last": last,
                "last_updated_at": event.get("timestamp"),
            }
        return None

    def _latest_completed_compaction_timestamp(self, thread_id: str) -> str | None:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        for event in reversed(events):
            if event.get("type") != "notification" or event.get("method") not in {"item/completed", "thread/compacted"}:
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            item = params.get("item") or {}
            if event.get("method") == "thread/compacted" or item.get("type") == "contextCompaction":
                return str(event.get("timestamp") or "")
        return None

    def _latest_running_compaction(self, thread_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        for event in reversed(events):
            if event.get("type") != "notification":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            method = str(event.get("method") or "")
            if method == "thread/compacted":
                return None
            item = params.get("item") or {}
            if item.get("type") != "contextCompaction":
                continue
            if method == "item/completed":
                return None
            if method == "item/started":
                return {
                    "turn_id": str(params.get("turnId") or ""),
                    "item_id": str(item.get("id") or ""),
                    "started_at": event.get("timestamp"),
                }
        return None

    def _latest_provider_thread_missing_timestamp(self, thread_id: str) -> str | None:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        for event in reversed(events):
            if event.get("type") != "provider_thread_missing":
                continue
            if thread_id and str(event.get("thread_id") or "") != thread_id:
                continue
            return str(event.get("timestamp") or "")
        return None

    def _timestamp_after(self, left: str, right: str) -> bool:
        try:
            left_dt = datetime.fromisoformat(left.replace("Z", "+00:00"))
            right_dt = datetime.fromisoformat(right.replace("Z", "+00:00"))
            return left_dt > right_dt
        except Exception:
            return left > right

    def _prepare_runtime(self, profile: dict[str, Any], *, require_secret: bool) -> dict[str, Any]:
        with self._runtime_operation_lock:
            if self._should_defer_runtime_prepare(profile):
                self._record_event(
                    {
                        "type": "runtime_switch_deferred_start_turn",
                        "requested_runtime": self._runtime_defer_preview(profile),
                        "active_runtime_signature": list(self._runtime_signature or []),
                        "reason": "start_turn_in_progress_config_write_guard",
                    }
                )
                raise RuntimeError("runtime_switch_deferred_start_turn")
            runtime_status = self._runtime_status_for_profile(profile, require_secret=require_secret)
            self._refresh_client_if_runtime_changed(runtime_status)
            return runtime_status

    def _runtime_status_for_profile(self, profile: dict[str, Any], *, require_secret: bool) -> dict[str, Any]:
        deferred_runtime = self._deferred_active_runtime_status(profile)
        if deferred_runtime is not None:
            return deferred_runtime
        router_environment = self._router_runtime_environment()
        # Runtime preparation is deliberately rendered from a private mapping.
        # Mutating ``os.environ`` here made a concurrent provider handoff race
        # with another lane and could leak a router token or proxy selection
        # into the wrong app-server process.
        runtime_environment = dict(os.environ)
        runtime_environment.update(router_environment)
        lane_codex_home = self._runtime_lane_codex_home(profile, runtime_environment)
        runtime_status = self._prepare_runtime_profile(
            profile,
            require_secret=require_secret,
            environment=runtime_environment,
            codex_home=lane_codex_home,
        )
        runtime_status = self._refresh_runtime_model_route_metadata(runtime_status, profile=profile)
        runtime_status["execution_host"] = self._execution_host()
        runtime_status["wsl_distro"] = self._wsl_distro()
        try:
            signature = self._runtime_config.runtime_signature(runtime_status)
            self._runtime_lane_environments[RuntimeClientPool.lane_id_for(signature)] = runtime_environment
        except Exception:
            # Compatibility test doubles may not expose the production
            # signature method; the client factory will fall back to a fresh
            # process-local environment in that case.
            pass
        return runtime_status

    def _prepare_runtime_profile(
        self,
        profile: dict[str, Any],
        *,
        require_secret: bool,
        environment: dict[str, str],
        codex_home: Path | None,
    ) -> dict[str, Any]:
        import inspect

        prepare = self._runtime_config.prepare_profile
        kwargs: dict[str, Any] = {"require_secret": require_secret}
        try:
            parameters = inspect.signature(prepare).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "environment" in parameters:
            kwargs["environment"] = environment
        if "codex_home" in parameters and codex_home is not None:
            kwargs["codex_home"] = codex_home
        return prepare(profile, **kwargs)

    def _runtime_lane_codex_home(self, profile: dict[str, Any], environment: dict[str, str]) -> Path | None:
        """Return a deterministic, credential-free Codex home for one lane."""

        configured_home = getattr(self._runtime_config, "codex_home", None)
        try:
            base_home = Path(configured_home() if callable(configured_home) else configured_home).expanduser().resolve()
        except (TypeError, ValueError, OSError):
            return None
        env_key = str(profile.get("env_key") or "OPENAI_API_KEY")
        secret_fingerprint = None
        fingerprint = getattr(self._secrets, "fingerprint", None)
        if callable(fingerprint):
            try:
                secret_fingerprint = fingerprint(environment.get(env_key))
            except Exception:
                secret_fingerprint = None
        mcp_updated_at = None
        try:
            mcp_updated_at = dict(self._mcp_config.snapshot() or {}).get("updated_at")
        except Exception:
            pass
        lane_hint = (
            str(profile.get("provider_id") or "").strip().lower(),
            str(profile.get("model") or "").strip(),
            str(profile.get("base_url") or "").strip(),
            str(profile.get("wire_api") or "").strip().lower(),
            env_key,
            secret_fingerprint,
            str(profile.get("proxy_mode") or "direct").strip().lower(),
            str(profile.get("proxy_url") or "").strip(),
            self._execution_host(),
            self._wsl_distro(),
            mcp_updated_at,
        )
        return base_home.parent / "runtime-lanes" / RuntimeClientPool.lane_id_for(lane_hint)

    def _refresh_runtime_model_route_metadata(
        self,
        runtime_status: dict[str, Any],
        *,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        if self._router_config is None:
            return runtime_status
        provider_id = str(runtime_status.get("provider_id") or profile.get("provider_id") or "").strip()
        model_name = str(runtime_status.get("model") or profile.get("model") or "").strip()
        if not provider_id or not model_name:
            return runtime_status
        exact_model_id = f"{provider_id}/{model_name}"
        configured_model = next(
            (
                item
                for item in self._router_config.models()
                if str(item.get("id") or "").strip() == exact_model_id
                or (
                    str(item.get("provider") or item.get("provider_id") or "").strip() == provider_id
                    and str(item.get("native_model") or "").strip() == model_name
                )
            ),
            None,
        )
        if not configured_model:
            return runtime_status
        refreshed = dict(runtime_status)
        configured_modalities = list(configured_model.get("input_modalities") or [])
        if configured_modalities:
            refreshed["input_modalities"] = configured_modalities
        configured_limits = dict(configured_model.get("modality_limits") or {})
        if configured_limits:
            refreshed["modality_limits"] = configured_limits
        return refreshed

    def _should_defer_runtime_prepare(self, profile: dict[str, Any]) -> bool:
        if not (self._runtime_start_turn_in_progress or self._runtime_thread_start_in_progress):
            return False
        if getattr(self._runtime_operation_local, "in_start_turn", False):
            return False
        if getattr(self._runtime_operation_local, "in_thread_start", False):
            return False
        active = self._runtime_config.status()
        if not active.get("configured"):
            return False
        return self._profile_targets_different_runtime(profile, active)

    def _deferred_active_runtime_status(self, profile: dict[str, Any]) -> dict[str, Any] | None:
        if getattr(self._runtime_operation_local, "in_start_turn", False):
            return None
        if getattr(self._runtime_operation_local, "in_thread_start", False):
            return None
        if not (self._runtime_start_turn_in_progress or self._runtime_thread_start_in_progress):
            return None
        active = self._runtime_config.status()
        if not active.get("configured"):
            return None
        if not self._profile_targets_different_runtime(profile, active):
            return None
        reason = "thread_start_in_progress_passive_status_guard" if self._runtime_thread_start_in_progress else "start_turn_in_progress_passive_status_guard"
        self._record_event(
            {
                "type": "runtime_switch_deferred_active_mutation",
                "requested_runtime": self._runtime_defer_preview(profile),
                "active_runtime_signature": list(self._runtime_signature or []),
                "reason": reason,
            }
        )
        return {
            **active,
            "execution_host": self._execution_host(),
            "wsl_distro": self._wsl_distro(),
        }

    def _profile_targets_different_runtime(self, profile: dict[str, Any], active: dict[str, Any]) -> bool:
        checks = (
            ("provider_id", "provider_id"),
            ("base_url", "base_url"),
            ("model", "model"),
            ("reasoning_effort", "reasoning_effort"),
            ("wire_api", "wire_api"),
        )
        for profile_key, active_key in checks:
            requested = str(profile.get(profile_key) or "").strip()
            current = str(active.get(active_key) or "").strip()
            if requested and current and requested != current:
                return True
        return False

    def _active_runtime_status(self) -> dict[str, Any]:
        status = getattr(self._runtime_config, "status", None)
        return dict(status() or {}) if callable(status) else {}

    def _runtime_defer_preview(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": profile.get("provider_id"),
            "model": profile.get("model"),
            "reasoning_effort": profile.get("reasoning_effort"),
            "wire_api": profile.get("wire_api"),
        }

    def _ensure_client(self, runtime_status: dict[str, Any]) -> AppServerClient:
        desired_signature = self._runtime_config.runtime_signature(runtime_status)
        self._runtime_client_pool.reap_idle()
        close_legacy_client = False
        with self._lock:
            current = self._client
            current_signature = self._runtime_signature
            current_is_pooled = self._runtime_projection_is_pooled
            if current is not None and current.is_running() and current_signature == desired_signature:
                # Selecting the same signature never requires a process
                # lifecycle transition. This also preserves compatibility for
                # callers that inject a legacy unpooled client in tests.
                return current
            if current is not None and current.is_running() and current_signature != desired_signature and not current_is_pooled:
                if (
                    (self._runtime_start_turn_in_progress and not getattr(self._runtime_operation_local, "in_start_turn", False))
                    or (self._runtime_thread_start_in_progress and not getattr(self._runtime_operation_local, "in_thread_start", False))
                ):
                    self._record_event(
                        {
                            "type": "runtime_switch_deferred_active_mutation",
                            "requested_runtime": runtime_status,
                            "active_runtime_signature": list(self._runtime_signature or []),
                            "reason": "runtime_request_during_active_mutation",
                        }
                    )
                    raise RuntimeError("runtime_switch_deferred_start_turn")
                if self._runtime_switch_is_pinned_signature(desired_signature):
                    raise RuntimeError("runtime_switch_deferred_active_turn")
                # Compatibility path for callers/tests that inject a legacy
                # unpooled client directly. Production clients are lane-owned
                # and are never closed merely because another signature starts.
                close_legacy_client = True
        if close_legacy_client:
            self._close_client("runtime_signature_mismatch")
        client = self._runtime_client_pool.get_or_create(
            desired_signature,
            lambda: self._create_runtime_client(runtime_status, desired_signature),
        )
        with self._lock:
            self._client = client
            self._runtime_signature = desired_signature
            self._runtime_projection_is_pooled = True
        return client

    def _create_runtime_client(
        self,
        runtime_status: dict[str, Any],
        signature: tuple[Any, ...],
    ) -> AppServerClient:
        launch = self._resolve_launch_target(runtime_status)
        lane_id = RuntimeClientPool.lane_id_for(signature)
        env = dict(self._runtime_lane_environments.get(lane_id) or os.environ)
        env.update(self._router_runtime_environment())
        try:
            workspace_root = self._projects.require_workspace_root()
            env["ASTRABRIDGE_WORKSPACE_ROOT"] = str(workspace_root)
            env["ASTRABRIDGE_ASSET_ROOT"] = str(workspace_root / WORKSPACE_STATE_DIRNAME / "assets" / "generated")
            runtime_roots = self._projects.current_runtime_roots()
            env["ASTRABRIDGE_PROJECT_RUNTIME_ROOT"] = str(runtime_roots["project_runtime_root"])
            env["ASTRABRIDGE_DOWNLOADS_ROOT"] = str(runtime_roots["downloads_root"])
            env["ASTRABRIDGE_CACHES_ROOT"] = str(runtime_roots["caches_root"])
            env["ASTRABRIDGE_TMP_ROOT"] = str(runtime_roots["tmp_root"])
        except Exception:
            pass
        client = AppServerClient(
            codex_executable=launch["codex_executable"],
            launch_command=launch["launch_command"],
            ws_url=launch.get("ws_url"),
            env={**env, **dict(launch.get("env_updates") or {})},
            cwd=launch["cwd"],
            allow_plugins=bool(launch.get("allow_plugins")),
            on_notification=self._on_notification,
            on_server_request=self._on_server_request,
            on_stderr=self._on_stderr,
        )
        try:
            client.start()
        except TimeoutError as exc:
            try:
                client.close()
            except Exception:
                pass
            raise RuntimeError(
                "Codex runtime initialization timed out. The desktop app-server did not become ready in time."
            ) from exc
        except Exception as exc:  # noqa: BLE001
            try:
                client.close()
            except Exception:
                pass
            raise RuntimeError(f"Codex runtime failed to start: {exc}") from exc
        self._record_event({"type": "runtime_started", "runtime": runtime_status})
        return client

    def _router_runtime_environment(self) -> dict[str, str]:
        router_environment = getattr(self._router, "runtime_environment", None)
        if not callable(router_environment):
            return {}
        try:
            values = dict(router_environment() or {})
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "router_runtime_environment_failed", "error": str(exc)[:300]})
            return {}
        required = {"ASTRABRIDGE_BASE_URL", ROUTER_ENV_KEY}
        if not required.issubset(values):
            self._record_event({"type": "router_runtime_environment_incomplete", "keys": sorted(values)})
            return {}
        return {key: str(value) for key, value in values.items() if value is not None}

    def _close_client(self, reason: str) -> None:
        client = self._detach_client()
        if client is None:
            self._record_event({"type": "runtime_lane_retire_requested", "reason": reason})
            return
        try:
            # ``RuntimeClientPool.close_lane`` has already closed an idle
            # client. Calling close again is harmless for legacy injected
            # clients and keeps the compatibility path straightforward.
            client.close()
        finally:
            self._record_event({"type": "runtime_stopped", "reason": reason})

    def _detach_client(self) -> Any | None:
        with self._lock:
            signature = self._runtime_signature
            client = self._client
        pooled = signature is not None and self._runtime_client_pool.has_lane(signature)
        if not pooled and client is None:
            return
        if pooled and signature is not None:
            client = self._runtime_client_pool.close_lane(signature, force=False)
            self._runtime_lane_environments.pop(RuntimeClientPool.lane_id_for(signature), None)
        with self._lock:
            self._client = None
            self._runtime_signature = None
            self._runtime_projection_is_pooled = False
            self._mcp_status_thread_signature = None
            self._mcp_status_thread_id = None
            self._runtime_pin_signature = None
            self._runtime_pin_until_monotonic = 0.0
            self._runtime_pin_thread_id = None
            self._runtime_pin_turn_id = None
            return client

    def _runtime_request_client(self, runtime_status: dict[str, Any]) -> "_RuntimeRequestClient":
        return _RuntimeRequestClient(self, runtime_status)

    def _is_app_server_transport_error(self, exc: RuntimeError) -> bool:
        message = str(exc)
        return any(
            marker in message
            for marker in (
                "codex_app_server_not_running",
                "codex_app_server_closed",
                "codex_app_server_disconnected",
                "websocket URL is not configured",
            )
        )

    def _refresh_client_if_runtime_changed(self, runtime_status: dict[str, Any]) -> None:
        with self._lock:
            signature = self._runtime_config.runtime_signature(runtime_status)
            if self._client is not None and self._runtime_signature is not None and signature != self._runtime_signature:
                if self._runtime_projection_is_pooled:
                    # A pooled lane remains valid while another provider lane
                    # is prepared. The subsequent caller selects the desired
                    # lane through ``_ensure_client`` instead of closing this
                    # one as a global singleton implementation did.
                    return
                if (
                    (self._runtime_start_turn_in_progress and not getattr(self._runtime_operation_local, "in_start_turn", False))
                    or (self._runtime_thread_start_in_progress and not getattr(self._runtime_operation_local, "in_thread_start", False))
                ):
                    self._record_event(
                        {
                            "type": "runtime_switch_deferred_active_mutation",
                            "requested_runtime": runtime_status,
                            "active_runtime_signature": list(self._runtime_signature or []),
                            "reason": "runtime_refresh_during_active_mutation",
                        }
                    )
                    return
                if self._runtime_switch_is_pinned_signature(signature):
                    self._record_event(
                        {
                            "type": "runtime_switch_deferred_active_turn",
                            "requested_runtime": runtime_status,
                            "pinned_thread_id": self._runtime_pin_thread_id,
                            "pinned_turn_id": self._runtime_pin_turn_id,
                        }
                    )
                    return
                self._close_client("runtime_configuration_changed")
            self._runtime_signature = signature

    def _pin_runtime_for_turn(self, runtime_status: dict[str, Any], thread_id: str, turn_id: str) -> None:
        with self._lock:
            self._runtime_pin_signature = self._runtime_config.runtime_signature(runtime_status)
            self._runtime_pin_until_monotonic = time.monotonic() + TURN_RUNTIME_PIN_SECONDS
            self._runtime_pin_thread_id = thread_id
            self._runtime_pin_turn_id = turn_id or None

    def _runtime_switch_is_pinned(self, runtime_status: dict[str, Any]) -> bool:
        signature = self._runtime_config.runtime_signature(runtime_status)
        return self._runtime_switch_is_pinned_signature(signature)

    def _runtime_switch_is_pinned_signature(self, requested_signature: tuple[Any, ...]) -> bool:
        if self._runtime_projection_is_pooled:
            return False
        if getattr(self._runtime_operation_local, "in_start_turn", False):
            return False
        if self._runtime_pin_signature is not None and time.monotonic() >= self._runtime_pin_until_monotonic:
            self._clear_runtime_pin(reason="runtime_pin_expired")
            return False
        return (
            self._client is not None
            and self._client.is_running()
            and self._runtime_signature is not None
            and self._runtime_pin_signature is not None
            and self._runtime_signature == self._runtime_pin_signature
            and requested_signature != self._runtime_signature
            and time.monotonic() < self._runtime_pin_until_monotonic
        )

    def _clear_runtime_pin(
        self,
        *,
        thread_id: str | None = None,
        turn_id: str | None = None,
        reason: str,
    ) -> bool:
        cleared_thread_id = ""
        cleared_turn_id = ""
        with self._lock:
            if self._runtime_pin_signature is None:
                return False
            pinned_thread_id = str(self._runtime_pin_thread_id or "")
            pinned_turn_id = str(self._runtime_pin_turn_id or "")
            if thread_id and pinned_thread_id and thread_id != pinned_thread_id:
                return False
            if turn_id and pinned_turn_id and turn_id != pinned_turn_id:
                return False
            cleared_thread_id = pinned_thread_id
            cleared_turn_id = pinned_turn_id
            self._runtime_pin_signature = None
            self._runtime_pin_until_monotonic = 0.0
            self._runtime_pin_thread_id = None
            self._runtime_pin_turn_id = None
        self._record_event(
            {
                "type": "runtime_turn_pin_cleared",
                "thread_id": cleared_thread_id,
                "turn_id": cleared_turn_id,
                "reason": reason,
            }
        )
        return True

    def _close_client(self, reason: str) -> None:
        with self._lock:
            if self._client is None:
                return
            try:
                self._client.close()
            finally:
                self._client = None
                self._mcp_status_thread_signature = None
                self._mcp_status_thread_id = None
                self._record_event({"type": "runtime_stopped", "reason": reason})

    def _on_notification(self, method: str, params: Any) -> None:
        payload = redact_sensitive(params)
        if isinstance(payload, dict):
            self._bind_observed_turn_to_active_policy(payload, source_method=method)
            self._record_no_tools_notification_violation(method, payload)
        if isinstance(payload, dict) and method in TERMINAL_TURN_NOTIFICATION_METHODS:
            thread_id = str(payload.get("threadId") or "")
            terminal_turn = dict(payload.get("turn") or {})
            observed_turn_id = str(payload.get("turnId") or terminal_turn.get("id") or "")
            active_policy = self._active_turn_execution_policy_for(
                {"threadId": thread_id, "turnId": observed_turn_id}
            )
            canonical_turn_id = str(dict(active_policy or {}).get("turn_id") or "").strip()
            turn_id = canonical_turn_id or observed_turn_id
            turn_status = self._normalize_terminal_turn_status(
                "cancelled" if method == "turn/aborted" else terminal_turn.get("status") or method.removeprefix("turn/")
            )
            self._remember_terminal_turn_notification(
                thread_id=thread_id,
                turn_id=turn_id,
                method=method,
                status=turn_status,
                turn={**terminal_turn, "observedTurnId": observed_turn_id or None},
            )
            keep_visible = self._should_keep_terminal_snapshot_visible(thread_id=thread_id, turn_id=turn_id)
            self._schedule_terminal_thread_snapshot(
                thread_id=thread_id,
                turn_id=turn_id,
                method=method,
                keep_visible=keep_visible,
            )
            self._clear_runtime_pin(
                thread_id=thread_id,
                turn_id=turn_id,
                reason=f"notification:{method}",
            )
            preserve_execution_policy = bool(
                active_policy is not None
                and active_policy.get("policy") == NO_TOOLS_EXECUTION_POLICY
                and bool(active_policy.get("strict_thread_scope"))
                and turn_status == "completed"
            )
            if preserve_execution_policy:
                self._record_event(
                    {
                        "type": "turn_execution_policy_clear_deferred",
                        "thread_id": thread_id,
                        "turn_id": turn_id,
                        "policy": NO_TOOLS_EXECUTION_POLICY,
                        "reason": "wait_for_bounded_follow_on_cleanup",
                    }
                )
            else:
                self._clear_active_turn_execution_policy(thread_id=thread_id, turn_id=turn_id)
        self._record_project_context_notification(method, payload)
        if method == "thread/name/updated" and isinstance(payload, dict):
            self._cache_thread_entry(str(payload.get("threadId") or ""), {"name": payload.get("threadName")})
        elif method == "thread/settings/updated" and isinstance(payload, dict):
            self._sync_thread_settings_from_notification(payload)
        elif method == "thread/started" and isinstance(payload, dict):
            thread = dict(payload.get("thread") or {})
            thread_id = str(thread.get("id") or "")
            if thread_id:
                self._cache_thread_entry(thread_id, {"name": thread.get("name")})
        self._record_event({"type": "notification", "method": method, "params": payload})

    def _remember_terminal_turn_notification(
        self,
        *,
        thread_id: str,
        turn_id: str,
        method: str,
        status: str,
        turn: dict[str, Any],
    ) -> None:
        clean_thread_id = str(thread_id or "").strip()
        clean_turn_id = str(turn_id or "").strip()
        clean_status = self._normalize_terminal_turn_status(status)
        if not clean_thread_id or clean_status not in TERMINAL_TURN_STATUSES:
            return
        record = {
            "thread_id": clean_thread_id,
            "turn_id": clean_turn_id,
            "method": str(method or "").strip(),
            "status": clean_status,
            "turn": deepcopy(turn),
            "observed_at": now_iso(),
            "observed_at_monotonic": time.monotonic(),
        }
        with self._lock:
            self._terminal_turn_notifications[(clean_thread_id, clean_turn_id)] = record
            while len(self._terminal_turn_notifications) > TERMINAL_TURN_NOTIFICATION_LIMIT:
                oldest_key = next(iter(self._terminal_turn_notifications))
                self._terminal_turn_notifications.pop(oldest_key, None)

    def _terminal_turn_notification(self, *, thread_id: str, turn_id: str) -> dict[str, Any] | None:
        clean_thread_id = str(thread_id or "").strip()
        clean_turn_id = str(turn_id or "").strip()
        if not clean_thread_id:
            return None
        with self._lock:
            exact = self._terminal_turn_notifications.get((clean_thread_id, clean_turn_id))
            if exact is not None:
                return deepcopy(exact)
            if clean_turn_id:
                fallback = self._terminal_turn_notifications.get((clean_thread_id, ""))
                if fallback is not None:
                    return deepcopy(fallback)
        return None

    def _should_keep_terminal_snapshot_visible(self, *, thread_id: str, turn_id: str) -> bool:
        clean_thread_id = str(thread_id or "").strip()
        clean_turn_id = str(turn_id or "").strip()
        if not clean_thread_id:
            return False
        pinned_thread_id = str(self._runtime_pin_thread_id or "").strip()
        pinned_turn_id = str(self._runtime_pin_turn_id or "").strip()
        if clean_thread_id != pinned_thread_id:
            return False
        if pinned_turn_id and clean_turn_id and clean_turn_id != pinned_turn_id:
            return False
        project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
        if project_thread_id == clean_thread_id:
            return True
        if self._tasks is None:
            return False
        current_task = self._tasks.current_task() or {}
        if not isinstance(current_task, dict) or not current_task:
            return False
        if str(current_task.get("active_provider_thread_id") or "").strip() == clean_thread_id:
            return True
        for item in list(current_task.get("provider_threads") or []):
            if isinstance(item, dict) and str(item.get("thread_id") or "").strip() == clean_thread_id:
                return True
        return False

    def _on_server_request(self, method: str, params: Any) -> Any:
        active_policy = self._active_turn_execution_policy_for(params)
        if active_policy is not None and active_policy.get("policy") == NO_TOOLS_EXECUTION_POLICY:
            payload = dict(params or {}) if isinstance(params, dict) else {}
            if method == "item/tool/call":
                self._record_execution_policy_tool_blocked(
                    payload,
                    policy=NO_TOOLS_EXECUTION_POLICY,
                    request_method=method,
                    tool_name=str(payload.get("tool") or payload.get("name") or "dynamic_tool"),
                )
                return {
                    "success": False,
                    "contentItems": [
                        {
                            "type": "inputText",
                            "text": "AstraBridge blocked this tool call because the task-graph node declares no tools.",
                        }
                    ],
                }
            if method in {
                "item/commandExecution/requestApproval",
                "item/fileChange/requestApproval",
                "item/tool/requestUserInput",
                "mcpServer/elicitation/request",
                "item/permissions/requestApproval",
                "applyPatchApproval",
                "execCommandApproval",
            }:
                self._record_execution_policy_tool_blocked(
                    payload,
                    policy=NO_TOOLS_EXECUTION_POLICY,
                    request_method=method,
                )
                return self._execution_policy_decline_response(method)
        if method == "item/tool/call":
            return self._handle_dynamic_tool_call(params)
        if (
            active_policy is not None
            and active_policy.get("policy") == PATCH_ONLY_EXECUTION_POLICY
            and method in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval", "execCommandApproval"}
        ):
            payload = dict(params or {}) if isinstance(params, dict) else {}
            self._record_event(
                {
                    "type": "turn_execution_policy_approval_blocked",
                    "thread_id": payload.get("threadId"),
                    "turn_id": payload.get("turnId"),
                    "policy": PATCH_ONLY_EXECUTION_POLICY,
                    "request_method": method,
                    "reason": "shell_or_file_change_not_allowed_by_patch_only_contract",
                }
            )
            return {"decision": "denied" if method == "execCommandApproval" else "decline"}
        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/tool/requestUserInput",
            "mcpServer/elicitation/request",
            "item/permissions/requestApproval",
            "applyPatchApproval",
            "execCommandApproval",
        }:
            return self._modals.request(method, params)
        raise RuntimeError(f"Unsupported server request: {method}")

    def _handle_dynamic_tool_call(self, params: Any) -> dict[str, Any]:
        payload = dict(params or {}) if isinstance(params, dict) else {}
        tool = str(payload.get("tool") or payload.get("name") or "").strip()
        arguments = payload.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        try:
            active_policy = self._active_turn_execution_policy_for(payload)
            allowed_names = None
            allow_browser_smoke = True
            active_mcp_policy = dict(dict(active_policy or {}).get("mcp_tool_policy") or {})
            if active_mcp_policy:
                allowed_names = allowed_mcp_dynamic_tool_names(active_mcp_policy)
                allow_browser_smoke = "web" in {
                    str(item).strip()
                    for item in list(dict(active_mcp_policy).get("allowed_tool_classes") or [])
                    if str(item or "").strip()
                }
            if tool not in self._dynamic_tool_names(
                allowed_mcp_tool_names=allowed_names,
                allow_browser_smoke=allow_browser_smoke,
            ):
                raise ValueError(f"Unsupported AstraBridge dynamic tool: {tool}")
            arguments = self._arguments_with_tool_context(tool, arguments)
            broker_internal_meta = self._dynamic_tool_broker_internal_meta(payload, active_policy=active_policy)
            result = self._call_dynamic_tool(tool, arguments, broker_internal_meta=broker_internal_meta)
            summary = self._summarize_dynamic_tool_result(tool, result)
            context = sanitize_tool_context(arguments.get("tool_context"))
            if context:
                summary["tool_context"] = context
            tool_server = self._dynamic_tool_server(tool)
            self._commit_active_mcp_tool_policy_decision(
                payload,
                decision=dict(dict(summary.get("mcp") or {}).get("policy_decision") or {}),
            )
            usage_delta = self._record_yunwu_image_usage_from_tool_result(server=tool_server, tool=tool, result=summary)
            content_text = self._dynamic_tool_text_result(tool, summary)
            self._record_event(
                {
                    "type": "dynamic_tool_called",
                    "server": tool_server,
                    "tool": tool,
                    "thread_id": payload.get("threadId"),
                    "turn_id": payload.get("turnId"),
                    "success": True,
                    "mcp_request_id": dict(summary.get("mcp") or {}).get("request_id"),
                    "mcp_operation_id": dict(summary.get("mcp") or {}).get("operation_id"),
                    "mcp_policy_decision": dict(summary.get("mcp") or {}).get("policy_decision"),
                    "mcp_audit_event": dict(summary.get("mcp") or {}).get("audit_event"),
                    "usage_delta": usage_delta,
                    "result": summary,
                }
            )
            return {"success": True, "contentItems": [{"type": "inputText", "text": content_text}]}
        except McpToolPolicyDenied as exc:
            decision = deepcopy(exc.decision)
            self._record_event(
                {
                    "type": "dynamic_tool_policy_blocked",
                    "server": self._dynamic_tool_server(tool),
                    "tool": tool,
                    "thread_id": payload.get("threadId"),
                    "turn_id": payload.get("turnId"),
                    "success": False,
                    "mcp_policy_decision": decision,
                }
            )
            return {
                "success": False,
                "contentItems": [
                    {
                        "type": "inputText",
                        "text": f"AstraBridge blocked this MCP tool call: {str(exc)}",
                    }
                ],
            }
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self._record_event(
                {
                    "type": "dynamic_tool_failed",
                    "server": self._dynamic_tool_server(tool),
                    "tool": tool,
                    "thread_id": payload.get("threadId"),
                    "turn_id": payload.get("turnId"),
                    "success": False,
                    "error": message,
                }
            )
            return {"success": False, "contentItems": [{"type": "inputText", "text": f"AstraBridge dynamic tool failed: {message}"}]}

    def _call_dynamic_tool(
        self,
        tool: str,
        arguments: dict[str, Any],
        *,
        broker_internal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if tool in BROWSER_SMOKE_TOOL_ALIASES:
            return self._call_browser_smoke_dynamic_tool(arguments)
        if _is_astrabridge_web_tool(tool):
            return self._call_astrabridge_web_dynamic_tool(tool, arguments, broker_internal_meta=broker_internal_meta)
        if tool.startswith("astrabridge_capability_"):
            return self._call_astrabridge_capability_dynamic_tool(tool, arguments, broker_internal_meta=broker_internal_meta)
        return self._call_yunwu_dynamic_tool(tool, arguments, broker_internal_meta=broker_internal_meta)

    def _arguments_with_tool_context(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        merged = dict(arguments or {})
        merged["tool_context"] = self._tool_context.build(
            tool_name=tool,
            provided=merged.get("tool_context"),
        )
        return merged

    def _summarize_dynamic_tool_result(self, tool: str, result: dict[str, Any]) -> dict[str, Any]:
        if tool.startswith("yunwu_image_"):
            summary = summarize_yunwu_image_result(result)
            if isinstance(result.get("mcp"), dict):
                summary["mcp"] = dict(result.get("mcp") or {})
            return summary
        if tool.startswith("astrabridge_capability_"):
            return result
        if _is_astrabridge_web_tool(tool):
            return result
        if tool in BROWSER_SMOKE_TOOL_ALIASES:
            record = dict(result.get("browser_smoke") or {})
            return {
                "tool": BROWSER_SMOKE_TOOL_NAME,
                "path": result.get("path"),
                "status": record.get("status"),
                "http_status": record.get("http_status"),
                "url": record.get("url"),
                "label": record.get("label"),
                "screenshot_path": record.get("screenshot_path"),
                "screenshot_status": record.get("screenshot_status"),
                "console_errors": list(record.get("console_errors") or [])[:10],
                "request_failures": list(record.get("request_failures") or [])[:10],
                "error": record.get("error"),
                "tool_event_verified": True,
            }
        return result

    def _dynamic_tool_server(self, tool: str) -> str:
        if tool in BROWSER_SMOKE_TOOL_ALIASES:
            return "astrabridge_browser"
        if _is_astrabridge_web_tool(tool):
            return "astrabridge_web"
        if tool.startswith("astrabridge_capability_"):
            return "astrabridge_capabilities"
        if tool.startswith("yunwu_image_"):
            return "yunwu_image"
        return "astrabridge"

    def _dynamic_tool_broker_internal_meta(
        self,
        payload: dict[str, Any],
        *,
        active_policy: dict[str, Any] | None,
    ) -> dict[str, Any]:
        policy = dict(dict(active_policy or {}).get("mcp_tool_policy") or {})
        trace_context = {
            **deepcopy(dict(active_policy or {}).get("mcp_tool_policy_context") or {}),
            "thread_id": str(payload.get("threadId") or "").strip() or None,
            "turn_id": str(payload.get("turnId") or "").strip() or None,
        }
        run_id = str(trace_context.get("run_id") or "").strip()
        trace_payload = {
            "trace_id": f"trace-{run_id}" if run_id else None,
            "run_id": run_id or None,
            "node_id": str(trace_context.get("node_id") or "").strip() or None,
            "attempt_count": int(trace_context.get("attempt_count") or 0) or None,
            "thread_id": str(trace_context.get("thread_id") or "").strip() or None,
            "turn_id": str(trace_context.get("turn_id") or "").strip() or None,
            "worker_thread_id": str(trace_context.get("worker_thread_id") or "").strip() or None,
        }
        if not policy:
            return {"astrabridge_trace": trace_payload} if any(trace_payload.values()) else {}
        return {
            "astrabridge_mcp_tool_policy": policy,
            "astrabridge_mcp_policy_state": {
                "tool_call_counts": deepcopy(dict(active_policy or {}).get("mcp_tool_call_counts") or {}),
                "approval_cache": deepcopy(dict(active_policy or {}).get("mcp_tool_approval_cache") or {}),
                "auto_bootstrap_approval": True,
            },
            "astrabridge_mcp_policy_context": trace_context,
            "astrabridge_trace": trace_payload,
        }

    def _commit_active_mcp_tool_policy_decision(self, payload: dict[str, Any], *, decision: dict[str, Any]) -> None:
        if not isinstance(decision, dict) or str(decision.get("decision") or "") != "allow":
            return
        thread_id = str(payload.get("threadId") or "").strip()
        turn_id = str(payload.get("turnId") or "").strip()
        if not thread_id:
            return
        counter_key = str(dict(decision.get("budget") or {}).get("counter_key") or "").strip()
        next_count = int(dict(decision.get("budget") or {}).get("observed_calls_after") or 0)
        approval_key = str(decision.get("server") or "").strip() + "::" + str(decision.get("tool") or "").strip()
        approval_reused = bool(decision.get("approval_reused"))
        approval_mode = str(decision.get("approval_mode") or "").strip().lower()
        with self._lock:
            active = self._active_turn_execution_policies.get(thread_id)
            if not active:
                return
            active_turn_id = str(active.get("turn_id") or "").strip()
            if active_turn_id and turn_id and active_turn_id != turn_id and not bool(active.get("strict_thread_scope")):
                if self._observed_turn_alias_target(thread_id=thread_id, observed_turn_id=turn_id) != active_turn_id:
                    return
            if counter_key:
                active.setdefault("mcp_tool_call_counts", {})
                active["mcp_tool_call_counts"][counter_key] = max(0, next_count)
            if approval_mode in {"ask", "manual"} and approval_key and not approval_reused:
                active.setdefault("mcp_tool_approval_cache", {})
                active["mcp_tool_approval_cache"][approval_key] = {
                    "approved_at": now_iso(),
                    "reason": str(decision.get("approval_decision") or "").strip() or "ask_auto_bootstrap",
                }

    def _call_browser_smoke_dynamic_tool(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._dogfood_run is None:
            raise ValueError("Dogfood browser smoke service is not available.")
        payload = {
            "url": str(arguments.get("url") or "").strip(),
            "label": str(arguments.get("label") or "agent browser smoke").strip(),
            "actions": list(arguments.get("actions") or []),
            "auto_milestone": bool(arguments.get("auto_milestone", True)),
        }
        return self._dogfood_run.browser_smoke(payload)

    def computer_use_browser_scenario(
        self,
        profile: dict[str, Any],
        *,
        run_model: bool = True,
        include_yunwu: bool = True,
        allow_fallback_sites: bool = True,
        max_wait_sec: float = 8.0,
        run_plugin_probe: bool = True,
    ) -> dict[str, Any]:
        scenario_id = new_id("CUA")
        generated_at = now_iso()
        targets = self._computer_use_browser_targets(allow_fallback_sites=allow_fallback_sites)
        artifact_root = self._projects.require_shell_state_root() / "dogfood" / "computer-use"
        artifact_root.mkdir(parents=True, exist_ok=True)
        report_path = artifact_root / f"{scenario_id}.json"
        attempts = self._computer_use_browser_attempts(profile, include_yunwu=include_yunwu)
        report_attempts = [{key: value for key, value in attempt.items() if key != "profile"} for attempt in attempts]
        report: dict[str, Any] = {
            "schema_version": "astrabridge-computer-use-browser-scenario-v1",
            "scenario_id": scenario_id,
            "scenario": "news-video-two-window",
            "generated_at": generated_at,
            "status": "prepared_for_computer_use",
            "artifact_path": str(report_path),
            "browser_targets": targets,
            "safety_boundaries": [
                "Do not log in.",
                "Do not submit forms except ordinary cookie consent.",
                "Do not upload, comment, purchase, or bypass CAPTCHA.",
                "Use only AstraBridge-owned windows titled AstraBridge Browser - <role>.",
            ],
            "attempts": report_attempts,
            "model_comparison": {
                "status": "runner_not_started" if not run_model else "runner_starting",
                "runner": "app_mediated_computer_use_model_runner",
                "max_wait_sec": max_wait_sec,
            },
            "app_server_plugin_gate": {
                "mode": "computer_use_plugins_allowed",
                "plugins": "enabled_for_this_probe_only",
                "plugin_sharing": "disabled",
                "remote_plugin": "disabled",
                "probe_status": "not_run",
            },
            "notes": [
                "The UI-created WebView2 windows are the target surface for Computer Use.",
                "Google News and YouTube are primary targets; fallback sites are allowed when the primary sites block, CAPTCHA, or fail to load.",
                "The model-run comparison is based on actual app-server thread/turn startup and observed plugin/tool notifications, not inferred from preparation.",
            ],
        }
        try:
            runtime_status = self._runtime_config.prepare_profile(
                profile,
                require_secret=False,
                enable_computer_use_plugins=True,
            )
            runtime_status["execution_host"] = self._execution_host()
            runtime_status["wsl_distro"] = self._wsl_distro()
            launch_target = self._resolve_launch_target(runtime_status, enable_computer_use_plugins=True)
            if run_plugin_probe:
                try:
                    plugin_report = probe_plugin_discovery(
                        codex_home=Path(str(runtime_status.get("codex_home") or "")).expanduser().resolve(),
                        client_factory=self._spawned_probe_client_factory(launch_target),
                        local_search_roots=self._kernel_probe_search_roots(),
                        artifact_root=artifact_root / "plugin-probes",
                        request_timeout=8.0,
                    )
                    report["app_server_plugin_gate"] = {
                        **report["app_server_plugin_gate"],
                        "probe_status": "ok",
                        "config_feature_state": ((plugin_report.get("plugin") or {}).get("config_feature_state") or "unknown"),
                        "list_status": ((plugin_report.get("plugin") or {}).get("list_status") or "unknown"),
                        "installed_status": ((plugin_report.get("plugin") or {}).get("installed_status") or "unknown"),
                        "discovered_plugins": [
                            (item.get("plugin_id") or item.get("name") or "")
                            for item in ((plugin_report.get("plugin") or {}).get("discovered_plugins") or [])
                            if isinstance(item, dict)
                        ],
                        "probe_artifact": plugin_report.get("report_path"),
                    }
                except Exception as exc:  # noqa: BLE001
                    report["app_server_plugin_gate"] = {
                        **report["app_server_plugin_gate"],
                        "probe_status": "error",
                        "error": str(exc)[:500],
                    }
                    report.setdefault("warnings", []).append(f"plugin_probe_failed:{str(exc)[:300]}")
            if run_model:
                report["attempts"] = [
                    self._run_computer_use_browser_model_attempt(
                        attempt,
                        targets=targets,
                        artifact_root=artifact_root,
                        scenario_id=scenario_id,
                        max_wait_sec=max_wait_sec,
                    )
                    for attempt in attempts
                ]
                report["model_comparison"] = self._summarize_computer_use_model_attempts(report["attempts"], max_wait_sec=max_wait_sec)
                report["status"] = str(report["model_comparison"].get("status") or "model_runner_attempted")
        except Exception as exc:  # noqa: BLE001
            if run_model:
                report["status"] = "model_runner_blocked"
                report["model_comparison"] = {
                    "status": "model_runner_blocked",
                    "reason": str(exc)[:500],
                    "max_wait_sec": max_wait_sec,
                }
            else:
                report["status"] = "prepared_with_plugin_probe_error"
            report["app_server_plugin_gate"] = {
                **report["app_server_plugin_gate"],
                "probe_status": "error",
                "error": str(exc)[:500],
            }
        finally:
            try:
                self._runtime_config.prepare_profile(profile, require_secret=False)
            except Exception as exc:  # noqa: BLE001
                report.setdefault("warnings", []).append(f"runtime_config_restore_failed:{str(exc)[:300]}")
        write_json(report_path, report)
        self._record_event(
            {
                "type": "computer_use_browser_scenario_prepared",
                "scenario_id": scenario_id,
                "artifact_path": str(report_path),
                "status": report.get("status"),
            }
        )
        return report

    def _computer_use_browser_targets(self, *, allow_fallback_sites: bool) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = [
            {
                "id": "ab-browser-news",
                "role": "News",
                "title": "AstraBridge Browser - News",
                "url": "https://news.google.com/search?q=%E5%AE%9E%E6%97%B6%E6%96%B0%E9%97%BB&hl=zh-CN&gl=US&ceid=US:zh-Hans",
                "fallback_urls": [
                    "https://www.bing.com/news/search?q=%E5%AE%9E%E6%97%B6%E6%96%B0%E9%97%BB",
                    "https://www.reuters.com/",
                ]
                if allow_fallback_sites
                else [],
            },
            {
                "id": "ab-browser-youtube",
                "role": "YouTube",
                "title": "AstraBridge Browser - YouTube",
                "url": "https://www.youtube.com/",
                "fallback_urls": [
                    "https://vimeo.com/watch",
                    "https://www.dailymotion.com/",
                ]
                if allow_fallback_sites
                else [],
            },
        ]
        return targets

    def _computer_use_browser_attempts(self, profile: dict[str, Any], *, include_yunwu: bool) -> list[dict[str, Any]]:
        attempts = [
            {
                "attempt_id": "current-model",
                "provider_id": profile.get("provider_id"),
                "profile_id": profile.get("profile_id"),
                "model": profile.get("model"),
                "status": "queued_for_app_model_runner",
                "expected_action": "Use Computer Use to confirm both AstraBridge browser pages are visible and record screenshots.",
                "profile": dict(profile),
            }
        ]
        if include_yunwu:
            try:
                yunwu_profile = self._profiles.resolve_runtime_profile("yunwu-default")
            except Exception:
                yunwu_profile = self._profiles.resolve_runtime_profile("yunwu")
            yunwu_profile = {**dict(yunwu_profile), "model": "gpt-5.5", "reasoning_effort": "high"}
            attempts.append(
                {
                    "attempt_id": "yunwu-gpt-5.5",
                    "provider_id": "yunwu",
                    "profile_id": yunwu_profile.get("profile_id"),
                    "model": "gpt-5.5",
                    "status": "queued_for_app_model_runner",
                    "expected_action": "Run the same Computer Use confirmation flow through yunwu/gpt-5.5.",
                    "profile": yunwu_profile,
                }
            )
        return attempts

    def _run_computer_use_browser_model_attempt(
        self,
        attempt: dict[str, Any],
        *,
        targets: list[dict[str, Any]],
        artifact_root: Path,
        scenario_id: str,
        max_wait_sec: float,
    ) -> dict[str, Any]:
        attempt_id = str(attempt.get("attempt_id") or "attempt").strip() or "attempt"
        events: list[dict[str, Any]] = []
        blocked_requests: list[dict[str, Any]] = []
        event_root = artifact_root / "model-runs"
        event_root.mkdir(parents=True, exist_ok=True)
        events_path = event_root / f"{scenario_id}-{attempt_id}-events.json"
        profile = dict(attempt.get("profile") or {})
        model = str(attempt.get("model") or profile.get("model") or "").strip() or None
        started_at = now_iso()
        client: AppServerClient | None = None

        def record_event(method: str, params: Any) -> None:
            events.append({"at": now_iso(), "method": method, "params": redact_sensitive(params)})

        def handle_server_request(method: str, params: Any) -> Any:
            record_event("runtime/server_request", {"method": method, "params": params})
            if method == "item/tool/call":
                return self._handle_dynamic_tool_call(params)
            blocked_requests.append({"method": method, "params": redact_sensitive(params)})
            if method == "item/tool/requestUserInput":
                return {"answers": {}}
            if method == "item/permissions/requestApproval":
                return {"permissions": {}, "scope": "turn"}
            if method == "mcpServer/elicitation/request":
                return {"action": "decline", "content": None, "_meta": {"reason": "CUA dogfood runner declines elicitation."}}
            if method in {"applyPatchApproval", "execCommandApproval"}:
                return {"decision": "denied"}
            if "requestApproval" in method or "approval" in method.lower():
                return {"decision": "decline", "reason": "CUA dogfood runner does not approve shell or file actions."}
            raise RuntimeError(f"Unsupported CUA dogfood server request: {method}")

        result = {
            key: value
            for key, value in attempt.items()
            if key != "profile"
        }
        result.update(
            {
                "status": "starting",
                "started_at": started_at,
                "events_path": str(events_path),
                "max_wait_sec": max_wait_sec,
            }
        )
        try:
            result["key_injection"] = self._inject_profile_key_for_runtime(profile)
            runtime_status = self._runtime_config.prepare_profile(
                profile,
                require_secret=True,
                enable_computer_use_plugins=True,
            )
            runtime_status["execution_host"] = self._execution_host()
            runtime_status["wsl_distro"] = self._wsl_distro()
            launch_target = self._resolve_launch_target(runtime_status, enable_computer_use_plugins=True)
            client = self._spawned_probe_client_factory(launch_target)(record_event, handle_server_request)
            client.start()
            thread_result = client.request(
                "thread/start",
                self._thread_start_params(profile=profile, model=model, permission_mode="ask"),
                timeout=THREAD_START_TIMEOUT_SECONDS,
            )
            thread = dict(thread_result.get("thread") or {})
            thread_id = str(thread.get("id") or "")
            if not thread_id:
                raise RuntimeError("thread/start did not return a thread id.")
            prompt = self._computer_use_browser_prompt(targets)
            turn_result = client.request(
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": self._build_user_inputs(
                        prompt,
                        [],
                        thread_id=thread_id,
                        context_mode="no_context",
                        profile_id=str(profile.get("profile_id") or ""),
                        provider_id=str(profile.get("provider_id") or ""),
                        model_id=str(model or ""),
                    ),
                    "cwd": self._runtime_workspace_root(),
                    "approvalsReviewer": "user",
                    "model": codex_model_id(profile, model),
                    "effort": codex_reasoning_effort(profile.get("reasoning_effort")),
                    **self._turn_permission_overrides("ask"),
                },
                timeout=max(8.0, min(TURN_START_TIMEOUT_SECONDS, float(max_wait_sec) + 8.0)),
            )
            turn = dict(turn_result.get("turn") or {})
            turn_id = str(turn.get("id") or "")
            deadline = time.monotonic() + max(0.0, float(max_wait_sec))
            while time.monotonic() < deadline:
                if self._computer_use_events_indicate_terminal(events, turn_id):
                    break
                time.sleep(0.25)
            summary = self._classify_computer_use_attempt_events(events, blocked_requests)
            result.update(
                {
                    **summary,
                    "thread_id": thread_id,
                    "turn_id": turn_id,
                    "finished_at": now_iso(),
                    "event_count": len(events),
                    "blocked_requests": blocked_requests[:10],
                }
            )
        except Exception as exc:  # noqa: BLE001
            result.update(
                {
                    "status": "blocked",
                    "failure_reason": str(exc)[:800],
                    "finished_at": now_iso(),
                    "event_count": len(events),
                    "blocked_requests": blocked_requests[:10],
                }
            )
            record_event("runner/error", {"error": str(exc)[:800]})
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            write_json(events_path, {"attempt": result, "events": events})
        return result

    def _inject_profile_key_for_runtime(self, profile: dict[str, Any]) -> dict[str, Any]:
        if self._key_injector is None:
            return {"injected": False, "reason": "key_injector_unavailable"}
        try:
            result = self._key_injector(profile)
            if isinstance(result, dict):
                return redact_sensitive(result)
            return {"injected": bool(result), "reason": "non_dict_result"}
        except Exception as exc:  # noqa: BLE001
            return {"injected": False, "reason": f"key_injector_failed:{str(exc)[:300]}"}

    def _computer_use_browser_prompt(self, targets: list[dict[str, Any]]) -> str:
        target_lines: list[str] = []
        for target in targets:
            fallback_urls = [str(item) for item in target.get("fallback_urls") or []]
            fallback_text = f" Fallback URLs: {', '.join(fallback_urls)}." if fallback_urls else ""
            target_lines.append(
                f"- {target.get('role')}: window title `{target.get('title')}`, primary URL `{target.get('url')}`.{fallback_text}"
            )
        return (
            "AstraBridge Computer Use dogfood validation.\n"
            "Use the computer-use or browser-control plugin if it is available. Do not use shell commands or external system browsers.\n"
            "Target only AstraBridge-owned WebView2 browser windows:\n"
            + "\n".join(target_lines)
            + "\n\nTasks:\n"
            "1. Confirm whether both target windows are visible and controllable.\n"
            "2. Confirm whether the news page and video page loaded. If Google News or YouTube is blocked, CAPTCHA-gated, or unusable, navigate the same AstraBridge window to one of its fallback URLs.\n"
            "3. Capture or report screenshot evidence if the plugin supports it.\n"
            "4. Return a compact JSON-style summary with windows_seen, fallback_used, screenshots, and blockers.\n\n"
            "Safety boundaries: do not log in, do not bypass CAPTCHA, do not upload, comment, purchase, or submit forms except ordinary cookie consent."
        )

    def _computer_use_events_indicate_terminal(self, events: list[dict[str, Any]], turn_id: str) -> bool:
        del turn_id
        terminal_methods = {"turn/completed", "turn/failed", "turn/cancelled", "turn/errored"}
        return any(str(event.get("method") or "") in terminal_methods for event in events)

    def _classify_computer_use_attempt_events(
        self,
        events: list[dict[str, Any]],
        blocked_requests: list[dict[str, Any]],
    ) -> dict[str, Any]:
        method_names = [str(event.get("method") or "") for event in events]
        tool_events = [
            event
            for event in events
            if any(marker in str(event.get("method") or "").lower() for marker in ("tool", "mcp", "plugin"))
        ]
        tool_text = json.dumps(tool_events, ensure_ascii=False).lower()
        cua_event_detected = bool(tool_events) and any(
            marker in tool_text
            for marker in ("computer", "cua", "browser", "webview", "screenshot", "youtube", "news.google")
        )
        completed = any(method in {"turn/completed", "turn/failed", "turn/cancelled", "turn/errored"} for method in method_names)
        if cua_event_detected:
            status = "cua_event_observed"
        elif tool_events:
            status = "tool_event_observed"
        elif completed:
            status = "completed_without_cua_event"
        elif blocked_requests:
            status = "blocked_by_non_cua_request"
        else:
            status = "turn_started_no_cua_event_yet"
        return {
            "status": status,
            "cua_event_detected": cua_event_detected,
            "tool_event_detected": bool(tool_events),
            "completed_event_detected": completed,
            "event_methods": sorted(set(method_names)),
        }

    def _summarize_computer_use_model_attempts(self, attempts: list[dict[str, Any]], *, max_wait_sec: float) -> dict[str, Any]:
        statuses = [str(attempt.get("status") or "") for attempt in attempts]
        if any(status == "cua_event_observed" for status in statuses):
            status = "model_runner_cua_observed"
        elif any(status in {"tool_event_observed", "completed_without_cua_event", "turn_started_no_cua_event_yet"} for status in statuses):
            status = "model_runner_attempted"
        elif any(status == "blocked_by_non_cua_request" for status in statuses):
            status = "model_runner_blocked"
        else:
            status = "model_runner_blocked"
        return {
            "status": status,
            "max_wait_sec": max_wait_sec,
            "attempt_statuses": [
                {
                    "attempt_id": attempt.get("attempt_id"),
                    "provider_id": attempt.get("provider_id"),
                    "model": attempt.get("model"),
                    "status": attempt.get("status"),
                    "thread_id": attempt.get("thread_id"),
                    "turn_id": attempt.get("turn_id"),
                    "events_path": attempt.get("events_path"),
                    "failure_reason": attempt.get("failure_reason"),
                }
                for attempt in attempts
            ],
        }

    def _call_astrabridge_web_dynamic_tool(
        self,
        tool: str,
        arguments: dict[str, Any],
        *,
        broker_internal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        broker_arguments = dict(arguments)
        if tool == "astrabridge_web_search":
            broker_arguments = {
                "query": str(arguments.get("query") or ""),
                "max_results": int(arguments.get("max_results") or 5),
                "timeout_sec": int(arguments.get("timeout_sec") or 20),
                "tool_context": arguments.get("tool_context"),
            }
        broker_result = self._mcp_broker.invoke_tool(
            "astrabridge_web",
            tool,
            broker_arguments,
            caller="runtime_dynamic_tool",
            operation_id=new_id("mcp-web-tool"),
            internal_meta=broker_internal_meta,
        )
        return self._with_broker_metadata(dict(broker_result.get("result") or {}), broker_result)
        raise ValueError(f"Unsupported AstraBridge web dynamic tool: {tool}")

    def _call_astrabridge_capability_dynamic_tool(
        self,
        tool: str,
        arguments: dict[str, Any],
        *,
        broker_internal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if tool == "astrabridge_capability_routes":
            broker_result = self._mcp_broker.invoke_capability(
                "routes",
                {"capability_id": str(arguments.get("capability_id") or "").strip() or None, **dict(arguments)},
                caller="runtime_dynamic_tool",
                operation_id=new_id("mcp-capability-routes"),
                internal_meta=broker_internal_meta,
            )
            return self._with_broker_metadata(dict(broker_result.get("result") or {}), broker_result)
        tool_map = {
            "astrabridge_capability_image_generate": "image.generate",
            "astrabridge_capability_vision_analyze": "vision.analyze",
            "astrabridge_capability_speech_transcribe": "speech.transcribe",
            "astrabridge_capability_speech_synthesize": "speech.synthesize",
        }
        capability_id = tool_map.get(tool)
        if not capability_id:
            raise ValueError(f"Unsupported AstraBridge capability dynamic tool: {tool}")
        broker_result = self._mcp_broker.invoke_capability(
            capability_id,
            arguments,
            caller="runtime_dynamic_tool",
            operation_id=new_id("mcp-capability-tool"),
            internal_meta=broker_internal_meta,
        )
        return self._with_broker_metadata(dict(broker_result.get("result") or {}), broker_result)

    def _call_yunwu_dynamic_tool(
        self,
        tool: str,
        arguments: dict[str, Any],
        *,
        broker_internal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        broker_result = self._mcp_broker.invoke_tool(
            "yunwu_image",
            tool,
            arguments,
            caller="runtime_dynamic_tool",
            operation_id=new_id("mcp-yunwu-tool"),
            internal_meta=broker_internal_meta,
        )
        return self._with_broker_metadata(dict(broker_result.get("result") or {}), broker_result)
        raise ValueError(f"Unsupported Yunwu dynamic tool: {tool}")

    @staticmethod
    def _with_broker_metadata(result: dict[str, Any], broker_result: dict[str, Any]) -> dict[str, Any]:
        merged = dict(result or {})
        merged["mcp"] = dict(broker_result.get("mcp") or {})
        return merged

    def _dynamic_tool_text_result(self, tool: str, summary: dict[str, Any]) -> str:
        return "AstraBridge dynamic tool result for " + tool + ":\n" + json.dumps(summary, ensure_ascii=False, indent=2)

    def _on_stderr(self, line: str) -> None:
        self._record_event({"type": "stderr", "line": line})

    def _build_user_inputs(
        self,
        text: str,
        attachments: list[dict[str, Any]],
        thread_id: str | None = None,
        context_mode: str | None = None,
        profile_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        clean_text = text.strip()
        normalized_context_mode = self._normalize_context_mode(context_mode)
        include_context = normalized_context_mode in {"default", "full"}
        if normalized_context_mode == "minimal_visual":
            mode_note = (
                "AstraBridge minimal visual mode: answer from the attached image(s) and the user's prompt only. "
                "Do not inspect repository files, run commands, or use tools unless the user explicitly asks for that in this turn."
            )
            clean_text = f"{mode_note}\n\n{clean_text}" if clean_text else mode_note
        project_context_items = (
            [
                *self._provider_handoff_context_inputs(thread_id=thread_id),
                *self._project_context_inputs(
                    thread_id=thread_id,
                    profile_id=profile_id,
                    provider_id=provider_id,
                    model_id=model_id,
                ),
            ]
            if include_context
            else []
        )
        project_context_text = "\n\n".join(str(item.get("text") or "") for item in project_context_items if item.get("type") == "text").strip()
        project_mentions = [item for item in project_context_items if item.get("type") == "mention"]
        asset_context_items = self._asset_context_inputs() if include_context else []
        asset_context_text = "\n\n".join(str(item.get("text") or "") for item in asset_context_items if item.get("type") == "text").strip()
        asset_mentions = [item for item in asset_context_items if item.get("type") == "mention"]
        if clean_text or not attachments:
            items.append({"type": "text", "text": clean_text or "Please inspect the attached files.", "text_elements": []})
        # Keep user-authored prompt and injected project/asset context as
        # distinct input items. Endpoint-aware preflight may drop or compact
        # only injected context; it must never silently alter the user's text.
        if project_context_text:
            items.append({"type": "text", "text": project_context_text, "text_elements": []})
        if asset_context_text:
            items.append({"type": "text", "text": asset_context_text, "text_elements": []})
        for attachment in attachments:
            staged = self._stage_attachment(str(attachment.get("path") or ""), str(attachment.get("name") or "attachment"))
            runtime_path = self._path_for_runtime(staged)
            mime_type = str(attachment.get("mime_type") or attachment.get("mimeType") or mimetypes.guess_type(staged.name)[0] or "")
            if mime_type.startswith("image/"):
                items.append({"type": "localImage", "path": runtime_path, "detail": "high"})
            else:
                items.append({"type": "mention", "name": str(attachment.get("name") or staged.name), "path": runtime_path})
        for mention in project_mentions:
            raw_path = str(mention.get("path") or "")
            if not raw_path:
                continue
            items.append(
                {
                    "type": "mention",
                    "name": str(mention.get("name") or Path(raw_path).name),
                    "path": self._path_for_runtime(Path(raw_path)),
                }
            )
        for mention in asset_mentions:
            raw_path = str(mention.get("path") or "")
            if not raw_path:
                continue
            items.append(
                {
                    "type": "mention",
                    "name": str(mention.get("name") or Path(raw_path).name),
                    "path": self._path_for_runtime(Path(raw_path)),
                }
            )
        return items

    def _apply_context_budget_preflight(
        self,
        inputs: list[dict[str, Any]],
        *,
        profile: dict[str, Any],
        runtime_status: dict[str, Any] | None,
        model: str | None,
        thread_id: str | None,
        attachments: list[dict[str, Any]],
        context_mode: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Preflight prepared inputs and compact only injected context.

        The first text item is always the user-authored turn prompt. It is
        essential and causes a deterministic block if it cannot fit. Later
        text items are AstraBridge-injected project/asset packs and may be
        compacted with a visible report before any provider request starts.
        """

        text_items = [
            (index, item)
            for index, item in enumerate(inputs)
            if isinstance(item, dict) and str(item.get("type") or "") == "text"
        ]
        if not text_items:
            return list(inputs), {
                "schema_version": "astrabridge-context-budget-v2",
                "preflight_admission": "downgrade_required",
                "recommended_action": "reduce_context_or_compact",
                "preflight_reasons": ["turn_input_text_missing"],
                "safe_context_budget_established": False,
            }
        sections: list[ContextSection] = []
        section_for_index: dict[int, str] = {}
        for position, (index, item) in enumerate(text_items):
            section_id = "turn_prompt" if position == 0 else f"injected_context_{position}"
            section_for_index[index] = section_id
            sections.append(
                ContextSection(
                    section_id=section_id,
                    label="Turn Prompt" if position == 0 else f"Injected Context {position}",
                    priority=position,
                    text=str(item.get("text") or ""),
                    essential=position == 0,
                )
            )
        route = self._context_budget_route_settings(profile=profile, runtime_status=runtime_status, model=model)
        safe_attachment_inputs = [
            {
                "kind": item.get("kind"),
                "mime_type": item.get("mime_type") or item.get("mimeType"),
                "size": item.get("size"),
            }
            for item in attachments
            if isinstance(item, dict)
        ]
        # Mentions generated by the task/project pack may be dereferenced by a
        # provider runtime. Reserve a bounded metadata envelope without storing
        # their names or paths in the durable budget report.
        safe_attachment_inputs.extend(
            {"kind": "referenced_file"}
            for item in inputs
            if isinstance(item, dict) and str(item.get("type") or "") == "mention"
        )
        observed = self._latest_context_token_usage(str(thread_id or "")) or {}
        _selected_text, budget = build_context_budget(
            sections=sections,
            provider_id=route.get("provider_id"),
            model_id=route.get("model_id"),
            context_window=route.get("context_window"),
            effective_context_window_percent=route.get("effective_context_window_percent") or 80,
            auto_compact_token_limit=route.get("auto_compact_token_limit"),
            tool_output_token_limit=route.get("tool_output_token_limit"),
            manual_compact_status=route.get("manual_compact_status") or "app_server_native",
            auto_compact_status=route.get("auto_compact_status") or "configured_unverified",
            compact_summary_quality_status=route.get("compact_summary_quality_status") or "untested",
            tool_schema_token_estimate=route.get("tool_schema_token_estimate") or 0,
            endpoint_protocol=route.get("wire_api"),
            endpoint_fingerprint=route.get("endpoint_fingerprint"),
            endpoint_protocol_overhead_tokens=route.get("endpoint_protocol_overhead_tokens"),
            endpoint_overhead_status=route.get("endpoint_overhead_status"),
            advertised_context_window_status=route.get("advertised_context_window_status") or "advertised",
            attachments=safe_attachment_inputs,
            supported_modalities=route.get("input_modalities"),
            output_reserve_tokens=route.get("output_reserve_tokens"),
            output_reserve_status=route.get("output_reserve_status"),
            reasoning_artifact_policy=route.get("reasoning_artifact_policy") or "neutral_summary_only",
            reasoning_artifact_reserve_tokens=route.get("reasoning_artifact_reserve_tokens"),
            existing_thread_context_tokens=observed.get("context_estimate_tokens") or 0,
        )
        report = budget.to_dict()
        admission = str(report.get("preflight_admission") or "downgrade_required")
        essential_estimate = next(
            (item for item in list(report.get("section_estimates") or []) if str(item.get("section_id") or "") == "turn_prompt"),
            {},
        )
        essential_is_safe = bool(essential_estimate.get("included")) and not bool(essential_estimate.get("truncated"))
        if admission in {"blocked", "downgrade_required"} or not essential_is_safe:
            reasons = [str(item).strip() for item in list(report.get("preflight_reasons") or []) if str(item).strip()]
            if not essential_is_safe and "essential_context_section_exceeds_safe_budget" not in reasons:
                reasons.append("essential_context_section_exceeds_safe_budget")
                report["preflight_reasons"] = reasons
            message = (
                "AstraBridge blocked this turn before the provider call because it could not establish a safe usable coding-context budget"
                + (f" ({', '.join(reasons[:4])})" if reasons else "")
                + ". Compact or reduce context, or choose a route with a known endpoint budget."
            )
            self._record_event(
                {
                    "type": "context_budget_preflight_blocked",
                    "thread_id": thread_id,
                    "provider_id": route.get("provider_id"),
                    "model": route.get("model_id"),
                    "context_mode": context_mode,
                    "context_budget_report": report,
                }
            )
            raise ContextBudgetPreflightError(report, message)

        selected = selected_text_by_section(sections, budget)
        prepared: list[dict[str, Any]] = []
        for index, item in enumerate(inputs):
            section_id = section_for_index.get(index)
            if section_id is None:
                prepared.append(dict(item) if isinstance(item, dict) else item)
                continue
            selected_text = selected.get(section_id)
            if selected_text is None:
                continue
            updated = dict(item)
            updated["text"] = selected_text
            prepared.append(updated)
        if admission == "admitted_after_compaction":
            self._record_event(
                {
                    "type": "context_budget_preflight_compacted",
                    "thread_id": thread_id,
                    "provider_id": route.get("provider_id"),
                    "model": route.get("model_id"),
                    "context_mode": context_mode,
                    "context_budget_report": report,
                }
            )
        elif admission == "admitted_with_conservative_budget":
            self._record_event(
                {
                    "type": "context_budget_preflight_conservative",
                    "thread_id": thread_id,
                    "provider_id": route.get("provider_id"),
                    "model": route.get("model_id"),
                    "context_mode": context_mode,
                    "context_budget_report": report,
                }
            )
        return prepared, report

    def _context_budget_route_settings(
        self,
        *,
        profile: dict[str, Any],
        runtime_status: dict[str, Any] | None,
        model: str | None,
    ) -> dict[str, Any]:
        merged = {**dict(profile or {}), **dict(runtime_status or {})}
        provider_id = str(merged.get("provider_id") or "").strip().lower()
        model_id = str(model or merged.get("model") or "").strip()
        provider_profile = None
        if provider_id:
            try:
                provider_profile = get_provider_profile(provider_id)
            except ValueError:
                provider_profile = None
        context_window = (
            merged.get("context_window")
            or merged.get("max_context_window")
            or merged.get("advertised_context_window")
            or (provider_profile.context_window() if provider_profile is not None else None)
        )
        wire_api = str(
            merged.get("wire_api")
            or (provider_profile.adapter_type() if provider_profile is not None else "")
            or ""
        ).strip().lower() or None
        route_identity = self._projection_route_identity(
            provider_id=provider_id,
            model_id=model_id or None,
            profile=merged,
        )
        context_support = dict(merged.get("context_compaction_support") or {})
        policy = normalize_context_budget_policy(dict(merged.get("context_budget_policy") or {}))
        modalities = [str(item).strip().lower() for item in list(merged.get("input_modalities") or []) if str(item).strip()]
        if not modalities and provider_profile is not None:
            modalities = [str(item).strip().lower() for item in provider_profile.context_policy.default_input_modalities]
        return {
            "provider_id": provider_id or None,
            "model_id": model_id or None,
            "context_window": context_window,
            "effective_context_window_percent": merged.get("effective_context_window_percent") or 80,
            "auto_compact_token_limit": merged.get("auto_compact_token_limit"),
            "tool_output_token_limit": merged.get("tool_output_token_limit"),
            "manual_compact_status": context_support.get("manual_compact") or "app_server_native",
            "auto_compact_status": context_support.get("auto_compact") or "configured_unverified",
            "compact_summary_quality_status": context_support.get("structured_summary_quality") or "untested",
            "tool_schema_token_estimate": estimate_tool_schema_tokens(merged),
            "wire_api": wire_api,
            "endpoint_fingerprint": route_identity.get("endpoint_fingerprint"),
            "input_modalities": modalities,
            "advertised_context_window_status": policy.get("advertised_context_window_status"),
            "endpoint_protocol_overhead_tokens": policy.get("endpoint_protocol_overhead_tokens"),
            "endpoint_overhead_status": policy.get("endpoint_overhead_status"),
            "output_reserve_tokens": policy.get("output_reserve_tokens"),
            "output_reserve_status": policy.get("output_reserve_status"),
            "reasoning_artifact_policy": policy.get("reasoning_artifact_policy"),
            "reasoning_artifact_reserve_tokens": policy.get("reasoning_artifact_reserve_tokens"),
        }

    def _assert_attachment_route_supported(
        self,
        attachments: list[dict[str, Any]],
        *,
        runtime_status: dict[str, Any],
        execution_backend: str,
        provider_id: str,
        model_id: str,
    ) -> None:
        has_images = any(
            str(item.get("kind") or "").strip().lower() == "image"
            or str(item.get("mime_type") or item.get("mimeType") or "").strip().lower().startswith("image/")
            for item in attachments
            if isinstance(item, dict)
        )
        if not has_images:
            return
        modalities = {str(item).strip().lower() for item in list(runtime_status.get("input_modalities") or [])}
        if "image" not in modalities:
            reason = "model_declares_no_image_input"
            message = "Image attachments are unavailable for the selected model. Remove the images or choose a model that declares image input."
        elif execution_backend == "app_server" and str(
            dict(runtime_status.get("modality_limits") or {}).get("app_server_image_input_status") or "unverified"
        ).strip().lower() != "verified":
            reason = "app_server_image_transport_unverified"
            message = (
                "Image attachments are blocked before dispatch because this App Server route has not verified image transport. "
                "Choose a verified vision route or use the dedicated vision capability."
            )
        else:
            return
        diagnostics = self._attachment_diagnostics(
            attachments,
            provider_id=provider_id,
            model_id=model_id,
        )
        self._record_event(
            {
                "type": "attachment_route_rejected",
                "reason": reason,
                "provider_id": provider_id,
                "model": model_id,
                "execution_backend": execution_backend,
                "attachment_diagnostics": diagnostics,
            }
        )
        raise ValueError(message)

    def _attachment_event_items(self, attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for attachment in attachments[:20]:
            if not isinstance(attachment, dict):
                continue
            name = self._safe_attachment_filename(str(attachment.get("name") or attachment.get("path") or "attachment"), default="attachment")
            mime_type = str(attachment.get("mime_type") or attachment.get("mimeType") or "").strip()
            kind = str(attachment.get("kind") or ("image" if mime_type.startswith("image/") else "file")).strip() or "file"
            event_item: dict[str, Any] = {"name": name, "kind": kind}
            if mime_type:
                event_item["mime_type"] = mime_type[:120]
            source = str(attachment.get("source") or "").strip()
            if source:
                event_item["source"] = source[:60]
            extension = Path(name).suffix.lower()
            if extension:
                event_item["extension"] = extension[:24]
            try:
                size = int(attachment.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            if size > 0:
                event_item["size"] = size
            items.append(event_item)
        return items

    def _attachment_diagnostics(
        self,
        attachments: list[dict[str, Any]],
        *,
        prepared_inputs: list[dict[str, Any]] | None = None,
        provider_id: str = "",
        model_id: str = "",
        context_mode: str = "",
    ) -> dict[str, Any]:
        event_items = self._attachment_event_items(attachments)
        image_count = sum(1 for item in event_items if item.get("kind") == "image" or str(item.get("mime_type") or "").startswith("image/"))
        folder_count = sum(1 for item in event_items if item.get("kind") == "folder")
        file_count = max(0, len(event_items) - image_count - folder_count)
        total_size = sum(int(item.get("size") or 0) for item in event_items)
        route: dict[str, Any] = {
            "provider_id": provider_id,
            "model_id": model_id,
            "context_mode": context_mode,
        }
        if prepared_inputs is not None:
            route.update(
                {
                    "text_items": sum(1 for item in prepared_inputs if item.get("type") == "text"),
                    "local_image_items": sum(1 for item in prepared_inputs if item.get("type") == "localImage"),
                    "mention_items": sum(1 for item in prepared_inputs if item.get("type") == "mention"),
                }
            )
        return {
            "total_count": len(event_items),
            "image_count": image_count,
            "file_count": file_count,
            "folder_count": folder_count,
            "total_size": total_size,
            "items": event_items,
            "route": route,
        }

    def _attachment_failure_message(self, exc: Exception) -> str:
        if isinstance(exc, FileNotFoundError):
            return "Attachment file or folder was not found. Remove it, add it again, and retry."
        if isinstance(exc, SecurityError):
            return str(redact_sensitive(str(exc)))[:240] or "Attachment was rejected by the secret scanner."
        message = str(redact_sensitive(str(exc))).strip()
        return message[:240] or "Attachment preparation failed before the model call."

    def _normalize_context_mode(self, context_mode: str | None) -> str:
        mode = str(context_mode or "default").strip().lower()
        aliases = {
            "": "default",
            "auto": "default",
            "project": "default",
            "project_context": "default",
            "with_context": "default",
            "health": "minimal_text",
            "health_check": "minimal_text",
            "light": "minimal_text",
            "lightweight": "minimal_text",
            "minimal_text": "minimal_text",
            "handoff": "default",
            "multi_provider": "default",
            "multi_provider_handoff": "default",
            "minimal": "minimal_visual",
            "visual": "minimal_visual",
            "visual_only": "minimal_visual",
            "none": "no_context",
            "off": "no_context",
        }
        mode = aliases.get(mode, mode)
        if mode not in VALID_CONTEXT_MODES:
            valid = ", ".join(sorted(VALID_CONTEXT_MODES | set(aliases)))
            raise ValueError(f"Unsupported context mode: {context_mode}. Supported context modes: {valid}")
        return "default" if mode == "full" else mode

    def _project_context_inputs(
        self,
        *,
        thread_id: str | None = None,
        profile_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._project_context is None:
            return []
        try:
            return list(
                self._project_context.context_inputs(
                    thread_id=thread_id,
                    profile_id=profile_id,
                    provider_id=provider_id,
                    model_id=model_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "project_context_pack_failed", "error": str(exc)[:300]})
            return []

    def _provider_handoff_context_inputs(self, *, thread_id: str | None = None) -> list[dict[str, Any]]:
        if self._tasks is None:
            return []
        try:
            task = self._tasks.current_task() or {}
        except Exception:
            return []
        clean_thread_id = str(thread_id or task.get("active_provider_thread_id") or "").strip()
        if not clean_thread_id:
            return []
        bundle: dict[str, Any] | None = None
        for event in reversed(list(task.get("handoff_events") or [])):
            if not isinstance(event, dict):
                continue
            if str(event.get("to_thread_id") or "").strip() != clean_thread_id:
                continue
            candidate = dict(event.get("neutral_handoff_bundle") or {})
            if str(candidate.get("path") or "").strip():
                bundle = candidate
                break
        if not isinstance(bundle, dict):
            return []
        raw_path = str(bundle.get("path") or "").strip()
        if not raw_path:
            return []
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self._projects.require_workspace_root() / candidate
        try:
            candidate = candidate.resolve()
        except Exception:
            pass
        if not candidate.exists() or not candidate.is_file():
            return []
        return [
            {
                "type": "text",
                "text": (
                    "Latest neutral handoff bundle: "
                    f"path={raw_path} "
                    f"projection_digest={str(bundle.get('projection_digest') or '').strip()} "
                    f"lineage_digest={str(bundle.get('lineage_digest') or '').strip()}\n"
                    "Use this bundle as the authoritative cross-provider continuity record for the active lane."
                ),
                "text_elements": [],
            },
            {
                "type": "mention",
                "name": candidate.name,
                "path": candidate.as_posix(),
            },
        ]

    def _project_context_budget_report(
        self,
        *,
        thread_id: str | None = None,
        profile_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> dict[str, Any] | None:
        if self._project_context is None:
            return None
        try:
            snapshot = self._project_context.snapshot(
                thread_id=thread_id,
                profile_id=profile_id,
                provider_id=provider_id,
                model_id=model_id,
            )
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "project_context_budget_failed", "error": str(exc)[:300]})
            return None
        pack = dict(snapshot.get("context_pack") or {})
        report = dict(pack.get("budget_report") or {})
        return report or None

    def _handoff_projection_kwargs(
        self,
        *,
        source_thread_id: str | None,
        target_provider_id: str,
        target_model_id: str | None = None,
    ) -> dict[str, Any]:
        summary = self._handoff_projection_summary(
            source_thread_id=source_thread_id,
            target_provider_id=target_provider_id,
            target_model_id=target_model_id,
        )
        if not summary:
            return {}
        return {
            "dropped_artifacts": int(summary.get("dropped_artifacts") or 0),
            "repaired_tool_pairs": int(summary.get("repaired_tool_pairs") or 0),
            "replayable_artifact_count": int(summary.get("replayable_artifact_count") or 0),
            "projection_preview": str(summary.get("projection_preview") or "").strip() or None,
            "warnings": list(summary.get("warnings") or []),
        }

    @staticmethod
    def _stable_json_digest(payload: Any) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _provider_handoff_bundle(
        self,
        *,
        source_thread_id: str | None,
        target_thread_id: str,
        target_provider_id: str,
        target_model_id: str | None,
        projection_mode: str,
        target_context_budget_report: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        detail = self._handoff_projection_detail(
            source_thread_id=source_thread_id,
            target_provider_id=target_provider_id,
            target_model_id=target_model_id,
        )
        if not detail:
            return None
        workspace_root = self._projects.require_workspace_root()
        shell_root = self._projects.require_shell_state_root()
        bundles_root = shell_root / "provider_handoffs"
        bundles_root.mkdir(parents=True, exist_ok=True)
        safe_target_thread_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(target_thread_id or "").strip() or "thread")
        timestamp = now_iso().replace(":", "").replace("-", "")
        bundle_path = bundles_root / f"{safe_target_thread_id}-{timestamp}.json"
        source_settings = self._thread_settings_for(str(source_thread_id or "").strip()) if str(source_thread_id or "").strip() else {}
        source_provider_id = str(detail.get("source_provider") or source_settings.get("provider_id") or "").strip() or None
        source_model_id = str(source_settings.get("model") or "").strip() or None
        task = self._tasks.current_task() if self._tasks is not None else {}
        target_settings = self._thread_settings_for(str(target_thread_id or "").strip()) if str(target_thread_id or "").strip() else {}
        target_model = str(target_model_id or target_settings.get("model") or "").strip() or None
        lineage = {
            "task_id": str(dict(task).get("task_id") or "").strip() or None,
            "source_thread_id": str(source_thread_id or "").strip() or None,
            "target_thread_id": str(target_thread_id or "").strip() or None,
            "source_provider_id": source_provider_id,
            "source_model_id": source_model_id,
            "target_provider_id": str(target_provider_id or "").strip() or None,
            "target_model_id": target_model,
            "projection_mode": str(projection_mode or "").strip() or None,
        }
        neutral_transcript = build_neutral_transcript(
            transcript_entries=[deepcopy(item) for item in list(detail.get("transcript_entries") or []) if isinstance(item, dict)],
            projected_messages=[deepcopy(item) for item in list(detail.get("messages") or []) if isinstance(item, dict)],
            replayable_artifacts=[deepcopy(item) for item in list(detail.get("replayable_artifacts") or []) if isinstance(item, dict)],
            artifact_drop_records=[deepcopy(item) for item in list(detail.get("artifact_drop_records") or []) if isinstance(item, dict)],
            lineage={
                "task_id": lineage["task_id"],
                "source_thread_id": lineage["source_thread_id"],
                "target_thread_id": lineage["target_thread_id"],
            },
            task_state=self._neutral_task_state(task),
            checkpoint_refs=list(dict(task).get("checkpoint_refs") or []),
        )
        source_route = dict(detail.get("source_route") or {})
        target_route = dict(detail.get("target_route") or {})
        source_context_budget_report = None
        if source_thread_id and source_provider_id and source_model_id:
            source_context_budget_report = self._project_context_budget_report(
                thread_id=source_thread_id,
                profile_id=str(source_settings.get("profile_id") or ""),
                provider_id=source_provider_id,
                model_id=source_model_id,
            )
        if target_context_budget_report is None:
            target_context_budget_report = self._project_context_budget_report(
                thread_id=target_thread_id,
                profile_id=str(target_settings.get("profile_id") or ""),
                provider_id=str(target_provider_id or ""),
                model_id=target_model,
            )
        context_compaction = build_context_compaction_handoff_contract(
            source_route=source_route,
            target_route=target_route,
            source_budget_report=source_context_budget_report,
            target_budget_report=target_context_budget_report,
        )
        projection_payload = {
            "source_provider": source_provider_id,
            "target_provider": str(target_provider_id or "").strip() or None,
            "projected_message_count": int(detail.get("projected_message_count") or 0),
            "replayable_artifact_count": int(detail.get("replayable_artifact_count") or 0),
            "dropped_artifacts": int(detail.get("dropped_artifacts") or 0),
            "repaired_tool_pairs": int(detail.get("repaired_tool_pairs") or 0),
            "warnings": [str(item).strip() for item in list(detail.get("warnings") or []) if str(item or "").strip()],
            "projection_preview": str(detail.get("projection_preview") or "").strip() or None,
            "messages": [deepcopy(item) for item in list(detail.get("messages") or []) if isinstance(item, dict)],
            "replayable_artifacts": [
                deepcopy(item)
                for item in list(detail.get("replayable_artifacts") or [])
                if isinstance(item, dict)
            ],
            "artifact_drop_records": [
                deepcopy(item)
                for item in list(detail.get("artifact_drop_records") or [])
                if isinstance(item, dict)
            ],
        }
        bundle = {
            "schema_version": "astrabridge-provider-handoff-context-v2",
            "generated_at": now_iso(),
            "lineage": lineage,
            "provider_private_state_removed": any(
                "provider-private" in str(item or "").strip().lower()
                for item in list(projection_payload.get("warnings") or [])
            ),
            "projection": projection_payload,
            "neutral_transcript": neutral_transcript,
            "context_compaction": context_compaction,
            "projection_digest": self._stable_json_digest(projection_payload),
            "neutral_transcript_digest": self._stable_json_digest(neutral_transcript),
            "lineage_digest": self._stable_json_digest(lineage),
        }
        bundle["bundle_digest"] = self._stable_json_digest(bundle)
        write_json(bundle_path, bundle)
        context_compaction_summary = compact_context_compaction_handoff_contract(context_compaction)
        return {
            "schema_version": str(bundle.get("schema_version") or ""),
            "path": bundle_path.relative_to(workspace_root).as_posix(),
            "bundle_digest": str(bundle.get("bundle_digest") or ""),
            "projection_digest": str(bundle.get("projection_digest") or ""),
            "neutral_transcript_schema_version": str(neutral_transcript.get("schema_version") or ""),
            "neutral_transcript_digest": str(bundle.get("neutral_transcript_digest") or ""),
            "lineage_digest": str(bundle.get("lineage_digest") or ""),
            "source_thread_id": lineage["source_thread_id"],
            "target_thread_id": lineage["target_thread_id"],
            "source_provider_id": source_provider_id,
            "source_model_id": source_model_id,
            "target_provider_id": lineage["target_provider_id"],
            "target_model_id": target_model,
            "projection_mode": lineage["projection_mode"],
            "provider_private_state_removed": bool(bundle.get("provider_private_state_removed")),
            "dropped_artifacts": int(projection_payload.get("dropped_artifacts") or 0),
            "repaired_tool_pairs": int(projection_payload.get("repaired_tool_pairs") or 0),
            "replayable_artifact_count": int(projection_payload.get("replayable_artifact_count") or 0),
            "artifact_drop_count": len(list(projection_payload.get("artifact_drop_records") or [])),
            "warning_count": len(list(projection_payload.get("warnings") or [])),
            "context_compaction": context_compaction_summary,
        }

    @staticmethod
    def _neutral_task_state(task: dict[str, Any] | None) -> dict[str, Any]:
        current = dict(task or {})
        plan = dict(current.get("plan") or {})
        goal = current.get("goal")
        if isinstance(goal, dict):
            goal_summary = str(goal.get("description") or goal.get("objective") or goal.get("title") or "").strip()
        else:
            goal_summary = str(goal or "").strip()
        return {
            "task_id": str(current.get("task_id") or "").strip() or None,
            "title": str(current.get("title") or current.get("name") or "").strip() or None,
            "goal_summary": goal_summary or None,
            "status": str(current.get("status") or "").strip() or None,
            "plan_status": str(plan.get("status") or "").strip() or None,
            "active_provider_thread_id": str(current.get("active_provider_thread_id") or "").strip() or None,
        }

    def _prime_handoff_projection_source_thread(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str | None,
    ) -> None:
        clean_thread_id = str(source_thread_id or "").strip()
        if not clean_thread_id:
            return
        try:
            result = client.request(
                "thread/read",
                {"threadId": clean_thread_id, "includeTurns": True},
                timeout=THREAD_READ_TIMEOUT_SECONDS,
            )
        except Exception:
            return
        thread = dict(result.get("thread") or {})
        if not thread:
            return
        existing = self._thread_for_handoff_projection(clean_thread_id)
        self._cache_thread_entry(
            clean_thread_id,
            {"thread": self._merge_handoff_projection_source_thread(existing=existing, incoming=thread)},
        )

    def _merge_handoff_projection_source_thread(
        self,
        *,
        existing: dict[str, Any] | None,
        incoming: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(incoming or {})
        existing_thread = dict(existing or {})
        if not existing_thread:
            return merged
        incoming_settings = dict(merged.get("shellSettings") or {})
        existing_settings = dict(existing_thread.get("shellSettings") or {})
        if existing_settings:
            merged["shellSettings"] = {
                **existing_settings,
                **{key: value for key, value in incoming_settings.items() if value is not None},
            }
        incoming_turns = [deepcopy(item) for item in list(merged.get("turns") or []) if isinstance(item, dict)]
        existing_turns = [deepcopy(item) for item in list(existing_thread.get("turns") or []) if isinstance(item, dict)]
        if existing_turns:
            incoming_messages, incoming_artifacts = self._thread_projection_inputs(merged)
            existing_messages, existing_artifacts = self._thread_projection_inputs(existing_thread)
            incoming_has_projection_inputs = bool(incoming_messages or incoming_artifacts)
            existing_has_projection_inputs = bool(existing_messages or existing_artifacts)
            if (
                not incoming_turns
                or len(incoming_turns) < len(existing_turns)
                or (existing_has_projection_inputs and not incoming_has_projection_inputs)
            ):
                merged["turns"] = existing_turns
        return merged

    def _handoff_projection_detail(
        self,
        *,
        source_thread_id: str | None,
        target_provider_id: str,
        target_model_id: str | None = None,
    ) -> dict[str, Any] | None:
        source_thread = self._thread_for_handoff_projection(source_thread_id)
        target_provider = str(target_provider_id or "").strip().lower()
        if not source_thread or not target_provider:
            return None
        source_provider = self._thread_provider_id_for_projection(source_thread)
        neutral_messages, artifacts = self._thread_projection_inputs(source_thread)
        if not neutral_messages and not artifacts:
            return None
        source_route = self._thread_route_identity_for_projection(source_thread, provider_id=source_provider)
        target_route = self._projection_route_identity(
            provider_id=target_provider,
            model_id=target_model_id,
        )
        projected = HistoryProjector().project(
            neutral_messages=neutral_messages,
            artifacts=artifacts,
            source_provider=source_provider,
            target_provider=target_provider,
            source_model_id=source_route.get("model_id"),
            target_model_id=target_route.get("model_id"),
            source_endpoint_fingerprint=source_route.get("endpoint_fingerprint"),
            target_endpoint_fingerprint=target_route.get("endpoint_fingerprint"),
            source_adapter_signature=source_route.get("adapter_signature"),
            target_adapter_signature=target_route.get("adapter_signature"),
        )
        return {
            "source_provider": source_provider,
            "target_provider": target_provider,
            "source_route": source_route,
            "target_route": target_route,
            "dropped_artifacts": projected.dropped_artifacts,
            "repaired_tool_pairs": projected.repaired_tool_pairs,
            "warnings": projected.warnings,
            "projected_message_count": len(projected.messages),
            "replayable_artifact_count": projected.replayable_artifact_count,
            "projection_preview": projected.projection_preview,
            "messages": deepcopy(projected.messages),
            "replayable_artifacts": deepcopy(projected.replayable_artifacts),
            "artifact_drop_records": deepcopy(projected.artifact_drop_records),
            "transcript_entries": deepcopy(projected.transcript_entries),
        }

    def _handoff_projection_summary(
        self,
        *,
        source_thread_id: str | None,
        target_provider_id: str,
        target_model_id: str | None = None,
    ) -> dict[str, Any] | None:
        detail = self._handoff_projection_detail(
            source_thread_id=source_thread_id,
            target_provider_id=target_provider_id,
            target_model_id=target_model_id,
        )
        if not detail:
            return None
        return {
            "source_provider": detail.get("source_provider"),
            "target_provider": detail.get("target_provider"),
            "dropped_artifacts": detail.get("dropped_artifacts"),
            "repaired_tool_pairs": detail.get("repaired_tool_pairs"),
            "warnings": list(detail.get("warnings") or []),
            "projected_message_count": int(detail.get("projected_message_count") or 0),
            "replayable_artifact_count": int(detail.get("replayable_artifact_count") or 0),
            "artifact_drop_count": len(list(detail.get("artifact_drop_records") or [])),
            "projection_preview": detail.get("projection_preview"),
        }

    def _thread_route_identity_for_projection(self, thread: dict[str, Any], *, provider_id: str | None) -> dict[str, str | None]:
        settings = dict(thread.get("shellSettings") or {})
        profile_id = str(settings.get("profile_id") or "").strip()
        resolved_profile = self._resolve_shell_profile(profile_id) if profile_id else {}
        return self._projection_route_identity(
            provider_id=provider_id,
            model_id=str(settings.get("model") or resolved_profile.get("model") or "").strip() or None,
            profile={**resolved_profile, **settings},
        )

    def _projection_route_identity(
        self,
        *,
        provider_id: str | None,
        model_id: str | None,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, str | None]:
        provider = str(provider_id or "").strip().lower()
        configured = dict(profile or {})
        built_in = None
        if provider:
            try:
                built_in = get_provider_profile(provider)
            except ValueError:
                built_in = None
        model = str(model_id or configured.get("model") or (built_in.default_model if built_in else "") or "").strip() or None
        base_url = str(configured.get("base_url") or (built_in.base_url if built_in else "") or "").strip()
        endpoint_fingerprint: str | None = None
        if provider and base_url:
            try:
                endpoint_fingerprint = str(normalize_endpoint_identity(base_url, provider_id=provider).get("fingerprint") or "").strip() or None
            except ValueError:
                endpoint_fingerprint = None
        provider_family = str(configured.get("provider_family") or configured.get("adapter_profile") or provider or "").strip().lower()
        wire_api = str(configured.get("wire_api") or (built_in.protocol if built_in else "") or "").strip().lower()
        adapter_signature: str | None = None
        if provider:
            try:
                transport_class = transport_class_for_profile(
                    {"provider_id": provider, "provider_family": provider_family, "wire_api": wire_api},
                    provider_family=provider_family,
                )
                adapter_signature = transport_signature_for_class(transport_class)
            except Exception:
                adapter_signature = None
        return {
            "provider_id": provider or None,
            "model_id": model,
            "endpoint_fingerprint": endpoint_fingerprint,
            "adapter_signature": adapter_signature,
        }

    def _thread_for_handoff_projection(self, source_thread_id: str | None) -> dict[str, Any] | None:
        clean_thread_id = str(source_thread_id or "").strip()
        if not clean_thread_id:
            return None
        native = self._read_native_thread(clean_thread_id)
        if isinstance(native, dict) and native:
            return native
        cached = self._cached_thread(clean_thread_id)
        if isinstance(cached, dict) and cached:
            return cached
        return None

    def _thread_provider_id_for_projection(self, thread: dict[str, Any]) -> str | None:
        settings = dict(thread.get("shellSettings") or {})
        provider = str(settings.get("provider_id") or "").strip().lower()
        if provider:
            return provider
        for turn in list(thread.get("turns") or []):
            if not isinstance(turn, dict):
                continue
            provider = str(turn.get("provider_id") or turn.get("providerId") or "").strip().lower()
            if provider:
                return provider
            for item in list(turn.get("items") or []):
                if not isinstance(item, dict):
                    continue
                provider_data = dict(item.get("providerData") or item.get("provider_data") or {})
                normalized = dict(provider_data.get("normalized") or {})
                reasoning_state = dict(normalized.get("reasoning_state") or {})
                provider = str(reasoning_state.get("provider_id") or normalized.get("provider_id") or "").strip().lower()
                if provider:
                    return provider
        return None

    def _thread_projection_inputs(self, thread: dict[str, Any]) -> tuple[list[NeutralMessage], list[ReasoningArtifact]]:
        neutral_messages: list[NeutralMessage] = []
        artifacts: list[ReasoningArtifact] = []
        thread_id = str(thread.get("id") or thread.get("thread_id") or "").strip()
        source_provider = self._thread_provider_id_for_projection(thread)
        route_identity = self._thread_route_identity_for_projection(thread, provider_id=source_provider)
        task_id: str | None = None
        if self._tasks is not None:
            try:
                task_id = str((self._tasks.current_task() or {}).get("task_id") or "").strip() or None
            except Exception:
                task_id = None
        for turn in list(thread.get("turns") or []):
            if not isinstance(turn, dict):
                continue
            turn_id = str(turn.get("id") or turn.get("turn_id") or "").strip()
            for item in list(turn.get("items") or []):
                if not isinstance(item, dict):
                    continue
                lineage = self._projection_item_lineage(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    item=item,
                    task_id=task_id,
                )
                neutral_messages.extend(self._projection_messages_from_item(item, lineage=lineage))
                artifacts.extend(
                    self._projection_artifacts_from_item(
                        item,
                        lineage=lineage,
                        route_identity=route_identity,
                    )
                )
        return neutral_messages, artifacts

    @staticmethod
    def _projection_item_lineage(
        *,
        thread_id: str,
        turn_id: str,
        item: dict[str, Any],
        task_id: str | None,
    ) -> dict[str, Any]:
        provider_data = dict(item.get("providerData") or item.get("provider_data") or {})
        normalized = dict(provider_data.get("normalized") or {})
        checkpoint_values = (
            item.get("checkpoint_ids")
            or normalized.get("checkpoint_ids")
            or [
                item.get("checkpoint_id") or item.get("checkpointId"),
                normalized.get("checkpoint_id") or normalized.get("checkpointId"),
            ]
        )
        checkpoint_ids = [
            str(value).strip()
            for value in (checkpoint_values if isinstance(checkpoint_values, list) else [checkpoint_values])
            if str(value or "").strip()
        ]
        return {
            "task_id": task_id,
            "thread_id": thread_id or None,
            "turn_id": turn_id or None,
            "item_id": str(item.get("id") or item.get("item_id") or "").strip() or None,
            "checkpoint_ids": checkpoint_ids[:20],
        }

    def _projection_messages_from_item(self, item: dict[str, Any], *, lineage: dict[str, Any] | None = None) -> list[NeutralMessage]:
        item_type = str(item.get("type") or "").strip()
        provider_data = dict(item.get("providerData") or item.get("provider_data") or {})
        normalized = dict(provider_data.get("normalized") or {})
        text = self._projection_item_text(item, normalized)
        base_lineage = dict(lineage or {})
        messages: list[NeutralMessage] = []
        if item_type in {"userMessage", "inputMessage", "user_message"} and text:
            messages.append(NeutralMessage(role="user", text=text, lineage=base_lineage))
            return messages
        if item_type in {"agentMessage", "assistantMessage", "agent_message", "assistant_message"}:
            if text:
                messages.append(NeutralMessage(role="assistant", text=text, lineage=base_lineage))
            for call in list(normalized.get("tool_calls") or []):
                if not isinstance(call, dict):
                    continue
                tool_id = str(call.get("id") or "").strip()
                tool_name = str(call.get("name") or "").strip()
                arguments_json = str(call.get("arguments_json") or "").strip() or "{}"
                if tool_id and tool_name:
                    messages.append(
                        NeutralMessage(
                            role="assistant",
                            text="",
                            tool_call_id=tool_id,
                            tool_name=tool_name,
                            provider_data={"arguments_json": arguments_json},
                            lineage={**base_lineage, "tool_call_id": tool_id},
                        )
                    )
            return messages
        if item_type in {"toolResult", "tool_result", "functionCallOutput", "function_call_output", "toolMessage", "tool_message"}:
            tool_call_id = str(
                normalized.get("tool_call_id")
                or normalized.get("call_id")
                or normalized.get("callId")
                or item.get("tool_call_id")
                or item.get("call_id")
                or item.get("callId")
                or ""
            ).strip()
            if tool_call_id:
                content_parts = list(normalized.get("content_parts") or item.get("content_parts") or [])
                messages.append(
                    NeutralMessage(
                        role="tool",
                        text=text,
                        tool_call_id=tool_call_id,
                        provider_data={"content_parts": content_parts},
                        content_parts=content_parts,
                        lineage={**base_lineage, "tool_call_id": tool_call_id},
                    )
                )
        return messages

    def _projection_artifacts_from_item(
        self,
        item: dict[str, Any],
        *,
        lineage: dict[str, Any] | None = None,
        route_identity: dict[str, str | None] | None = None,
    ) -> list[ReasoningArtifact]:
        provider_data = dict(item.get("providerData") or item.get("provider_data") or {})
        normalized = dict(provider_data.get("normalized") or {})
        reasoning_state = dict(normalized.get("reasoning_state") or {})
        if not reasoning_state:
            return []
        provider_id = str(reasoning_state.get("provider_id") or "").strip()
        model_id = str(reasoning_state.get("model_id") or "").strip()
        if not provider_id or not model_id:
            return []
        raw_provenance = reasoning_state.get("provenance") or reasoning_state.get("artifact_provenance")
        if isinstance(raw_provenance, dict):
            provenance = dict(raw_provenance)
        else:
            route = dict(route_identity or {})
            provenance = {
                "schema_version": REASONING_ARTIFACT_PROVENANCE_SCHEMA_VERSION,
                "issuer": {
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "endpoint_fingerprint": route.get("endpoint_fingerprint"),
                    "adapter_signature": route.get("adapter_signature"),
                },
                "lineage": dict(lineage or {}),
                "replay": {
                    "eligible": False,
                    "scope": REASONING_ARTIFACT_REPLAY_SCOPE,
                    "retention": REASONING_ARTIFACT_RETENTION,
                    "issued_at": None,
                    "expires_at": None,
                },
            }
        return [
            ReasoningArtifact(
                provider_id=provider_id,
                model_id=model_id,
                kind="reasoning_state",
                replayable=bool(reasoning_state.get("replayable")),
                payload=reasoning_state,
                provenance=provenance,
            )
        ]

    def _projection_item_text(self, item: dict[str, Any], normalized: dict[str, Any]) -> str:
        text = str(normalized.get("text") or "").strip()
        if text:
            return text
        direct = item.get("text") or item.get("message") or item.get("content")
        if isinstance(direct, str):
            return direct.strip()
        return ""

    def _asset_context_inputs(self) -> list[dict[str, Any]]:
        if self._asset_registry is None:
            return []
        try:
            return list(self._asset_registry.context_inputs())
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "asset_context_pack_failed", "error": str(exc)[:300]})
            return []

    def stage_uploaded_attachments(self, payload: dict[str, Any]) -> dict[str, Any]:
        files = list(payload.get("files") or [])
        if len(files) > ATTACHMENT_STAGE_MAX_FILES:
            raise ValueError(f"Too many attachment files. Maximum is {ATTACHMENT_STAGE_MAX_FILES}.")
        attachments_root = self._projects.require_shell_state_root() / "attachments"
        attachments_root.mkdir(parents=True, exist_ok=True)
        directory_name = str(payload.get("directory_name") or "").strip()
        skipped: list[dict[str, str]] = []
        staged_files: list[tuple[Path, str]] = []
        total_bytes = 0

        if directory_name:
            directory_root = attachments_root / f"{self._safe_attachment_filename(directory_name, default='folder')}-{new_id('ATTDIR')}"
            directory_root.mkdir(parents=True, exist_ok=False)
        else:
            directory_root = None

        for index, raw_file in enumerate(files):
            if not isinstance(raw_file, dict):
                skipped.append({"name": f"attachment-{index + 1}", "reason": "Invalid attachment record."})
                continue
            name = self._safe_attachment_filename(str(raw_file.get("name") or ""), default=f"attachment-{index + 1}")
            try:
                declared_size = int(raw_file.get("size") or 0)
            except (TypeError, ValueError):
                declared_size = 0
            if declared_size > ATTACHMENT_STAGE_MAX_FILE_BYTES:
                skipped.append({"name": name, "reason": "File is larger than the upload limit."})
                continue
            data_base64 = str(raw_file.get("data_base64") or "")
            try:
                data = base64.b64decode(data_base64, validate=True)
            except (binascii.Error, ValueError) as exc:
                skipped.append({"name": name, "reason": f"Invalid file encoding: {exc}"})
                continue
            if len(data) > ATTACHMENT_STAGE_MAX_FILE_BYTES:
                skipped.append({"name": name, "reason": "File is larger than the upload limit."})
                continue
            if total_bytes + len(data) > ATTACHMENT_STAGE_MAX_TOTAL_BYTES:
                skipped.append({"name": name, "reason": "Attachment upload total is larger than the limit."})
                continue
            total_bytes += len(data)
            try:
                target = self._uploaded_attachment_target(
                    attachments_root=attachments_root,
                    directory_root=directory_root,
                    raw_relative_path=str(raw_file.get("relative_path") or ""),
                    name=name,
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                scan_text_for_secrets(target)
            except SecurityError as exc:
                try:
                    target.unlink(missing_ok=True)
                except Exception:
                    pass
                skipped.append({"name": name, "reason": str(exc)})
                continue
            except Exception as exc:  # noqa: BLE001
                skipped.append({"name": name, "reason": str(exc)})
                continue
            staged_files.append((target, name))

        if directory_root is not None:
            if not staged_files:
                try:
                    shutil.rmtree(directory_root, ignore_errors=True)
                except Exception:
                    pass
                self._record_event(
                    {
                        "type": "attachments_staged",
                        "mode": "browser_upload_directory",
                        "created_count": 0,
                        "skipped_count": len(skipped),
                        "total_size": total_bytes,
                    }
                )
                return {"attachments": [], "skipped": skipped}
            response = {
                "attachments": [
                    {
                        "id": new_id("ATT"),
                        "path": str(directory_root),
                        "name": self._safe_attachment_filename(directory_name, default=directory_root.name),
                        "mimeType": "inode/directory",
                        "kind": "folder",
                        "size": total_bytes,
                        "source": "browser_upload",
                        "fileCount": len(staged_files),
                    }
                ],
                "skipped": skipped,
            }
            self._record_event(
                {
                    "type": "attachments_staged",
                    "mode": "browser_upload_directory",
                    "created_count": 1,
                    "file_count": len(staged_files),
                    "skipped_count": len(skipped),
                    "total_size": total_bytes,
                    "attachments": self._attachment_event_items(response["attachments"]),
                }
            )
            return response

        attachments: list[dict[str, Any]] = []
        for path, display_name in staged_files:
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            attachments.append(
                {
                    "id": new_id("ATT"),
                    "path": str(path),
                    "name": display_name,
                    "mimeType": mime_type,
                    "kind": "image" if mime_type.startswith("image/") else "file",
                    "size": path.stat().st_size,
                    "source": "browser_upload",
                }
            )
        response = {"attachments": attachments, "skipped": skipped}
        self._record_event(
            {
                "type": "attachments_staged",
                "mode": "browser_upload_files",
                "created_count": len(attachments),
                "skipped_count": len(skipped),
                "total_size": total_bytes,
                "attachments": self._attachment_event_items(attachments),
            }
        )
        return response

    def _uploaded_attachment_target(self, *, attachments_root: Path, directory_root: Path | None, raw_relative_path: str, name: str) -> Path:
        if directory_root is None:
            extension = Path(name).suffix
            stem = Path(name).stem or "attachment"
            return attachments_root / f"{stem}-{new_id('ATT')}{extension}"
        relative_parts = self._safe_attachment_relative_parts(raw_relative_path or name)
        if not relative_parts:
            relative_parts = [name]
        if Path(relative_parts[-1]).suffix == "" and Path(name).suffix:
            relative_parts[-1] = name
        return resolve_under(directory_root, Path(*relative_parts))

    def _safe_attachment_relative_parts(self, value: str) -> list[str]:
        normalized = str(value or "").replace("\\", "/")
        parts: list[str] = []
        for raw_part in normalized.split("/"):
            part = raw_part.strip()
            if not part or part == ".":
                continue
            if part == ".." or ":" in part or part.startswith("~"):
                raise SecurityError(f"Invalid attachment relative path: {value}")
            parts.append(self._safe_attachment_filename(part, default="attachment"))
        return parts

    def _safe_attachment_filename(self, value: str, *, default: str = "attachment") -> str:
        name = Path(str(value or "")).name.strip()
        cleaned = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "-", name).strip(" .-")
        return cleaned[:120] or default

    def _stage_attachment(self, raw_path: str, preferred_name: str) -> Path:
        if not raw_path.strip():
            raise ValueError("Attachment path is required.")
        source = Path(raw_path).expanduser().resolve()
        if not source.exists() or not (source.is_file() or source.is_dir()):
            raise FileNotFoundError(f"Attachment does not exist: {source}")
        try:
            workspace_root = self._projects.require_workspace_root().resolve()
            if source == workspace_root or workspace_root in source.parents:
                if source.parts.count(WORKSPACE_STATE_DIRNAME):
                    return source
                return resolve_under(workspace_root, source)
        except Exception:
            pass
        if source.is_dir():
            return self._stage_attachment_directory(source, preferred_name)
        try:
            scan_text_for_secrets(source)
        except SecurityError:
            raise
        attachments_root = self._projects.require_shell_state_root() / "attachments"
        attachments_root.mkdir(parents=True, exist_ok=True)
        extension = source.suffix or Path(preferred_name).suffix
        stem = Path(preferred_name).stem or source.stem or "attachment"
        target = attachments_root / f"{stem}-{new_id('ATT')}{extension}"
        shutil.copy2(source, target)
        return target

    def _stage_attachment_directory(self, source: Path, preferred_name: str) -> Path:
        files = sorted(path for path in source.rglob("*") if path.is_file())
        if len(files) > ATTACHMENT_STAGE_MAX_FILES:
            raise ValueError(f"Attachment folder has too many files. Maximum is {ATTACHMENT_STAGE_MAX_FILES}.")
        total_bytes = 0
        for path in files:
            total_bytes += path.stat().st_size
            if total_bytes > ATTACHMENT_STAGE_MAX_TOTAL_BYTES:
                raise ValueError("Attachment folder is larger than the staging limit.")
            scan_text_for_secrets(path)
        attachments_root = self._projects.require_shell_state_root() / "attachments"
        attachments_root.mkdir(parents=True, exist_ok=True)
        stem = self._safe_attachment_filename(preferred_name or source.name, default=source.name or "folder")
        target = attachments_root / f"{stem}-{new_id('ATTDIR')}"
        shutil.copytree(source, target)
        return target

    def _execution_host(self) -> str:
        project = self._projects.current_project or {}
        prefs = dict(project.get("ui_preferences") or {})
        host = str(prefs.get("execution_host") or "windows").strip().lower()
        return "wsl" if host == "wsl" else "windows"

    def _wsl_distro(self) -> str | None:
        project = self._projects.current_project or {}
        prefs = dict(project.get("ui_preferences") or {})
        value = str(prefs.get("wsl_distro") or "").strip()
        return value or None

    def _runtime_workspace_root(self) -> str:
        return self._path_for_runtime(self._projects.require_workspace_root())

    def _path_for_runtime(self, path: Path) -> str:
        resolved = path.expanduser().resolve()
        if self._execution_host() == "wsl":
            return self._windows_path_to_wsl(resolved)
        return str(resolved)

    def _windows_path_to_wsl(self, path: Path) -> str:
        resolved = path.expanduser().resolve()
        drive = resolved.drive.rstrip(":").lower()
        if not drive:
            raise RuntimeError(f"WSL execution requires a drive-backed Windows path. Unsupported path: {resolved}")
        tail = resolved.as_posix()[2:]
        return f"/mnt/{drive}{tail}"

    def _launch_descriptor(self) -> str | None:
        metadata = resolve_codex_binary_metadata(
            execution_host=self._execution_host(),
            wsl_distro=self._wsl_distro(),
            environ=os.environ,
        )
        return str(metadata.get("launch_descriptor") or "") or None

    def _resolve_launch_target(self, runtime_status: dict[str, Any], *, enable_computer_use_plugins: bool = False) -> dict[str, Any]:
        binary_metadata = resolve_codex_binary_metadata(
            execution_host=self._execution_host(),
            wsl_distro=self._wsl_distro(),
            environ=os.environ,
        )
        if self._execution_host() != "wsl":
            codex_executable = str(binary_metadata.get("path") or "").strip() or None
            if not codex_executable:
                raise RuntimeError("Codex CLI/runtime was not detected. Install Codex or set ASTRABRIDGE_CODEX_BIN before sending.")
            return {
                "codex_executable": codex_executable,
                "launch_command": [codex_executable, *app_server_command(allow_plugins=True)] if enable_computer_use_plugins else None,
                "ws_url": None,
                "env_updates": {},
                "cwd": self._app_server_launch_cwd(),
                "allow_plugins": bool(enable_computer_use_plugins),
            }

        wsl_executable = shutil.which("wsl.exe") or shutil.which("wsl")
        if not wsl_executable:
            raise RuntimeError("WSL execution host is selected, but wsl.exe was not detected on Windows.")
        workspace_root = self._projects.require_workspace_root()
        launcher_cwd_wsl = self._windows_path_to_wsl(self._app_server_launch_cwd())
        codex_home_wsl = os.environ.get("ASTRABRIDGE_WSL_CODEX_HOME") or ASTRABRIDGE_WSL_CODEX_HOME
        codex_binary = str(binary_metadata.get("path") or "").strip() or ASTRABRIDGE_WSL_BIN
        requested_distro = self._wsl_distro()
        installed_distros = self._list_wsl_distros(wsl_executable)
        if requested_distro and requested_distro not in installed_distros:
            raise RuntimeError(
                f"WSL execution host is selected, but the configured distro was not found: {requested_distro}. "
                f"Available distros: {', '.join(installed_distros) if installed_distros else 'none'}."
            )
        if not requested_distro and not installed_distros:
            raise RuntimeError(
                "WSL execution host is selected, but no WSL distro is installed on this machine yet. "
                "Install one first with `wsl.exe --install <Distro>`."
            )
        distro = requested_distro or (installed_distros[0] if installed_distros else None)
        distro_args = ["-d", distro] if distro else []
        self._terminate_stale_astrabridge_wsl_app_servers(wsl_executable, distro_args)
        probe = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", self._wsl_codex_probe_command(codex_binary)])
        if int(probe["returncode"]) != 0:
            detail = str(probe["stderr"] or probe["stdout"]).strip()
            suffix = f" ({detail})" if detail else ""
            raise RuntimeError(
                "WSL execution host is selected, but a Linux-native Codex CLI is not ready inside WSL. "
                "Install the AstraBridge-managed WSL runtime or set ASTRABRIDGE_WSL_CODEX_BIN." + suffix
            )
        codex_home_wsl_abs = self._wsl_expand_home(wsl_executable, distro_args, codex_home_wsl)
        home_wsl_abs = self._wsl_expand_home(wsl_executable, distro_args, "$HOME")
        codex_binary_abs = self._wsl_expand_home(wsl_executable, distro_args, codex_binary)
        self._sync_wsl_codex_home(runtime_status, wsl_executable, distro_args, codex_home_wsl_abs, home_wsl_abs)
        env_updates = self._wsl_runtime_env(runtime_status, codex_home_wsl_abs)
        env_passthrough = self._wsl_env_passthrough_args(env_updates)
        codex_command = self._wsl_codex_command(codex_binary_abs)
        clean_path = f"{home_wsl_abs.rstrip('/')}/.local/share/astrabridge/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        ws_port = self._reserve_loopback_port()
        ws_url = f"ws://127.0.0.1:{ws_port}"
        plugin_flags = "" if enable_computer_use_plugins else " --disable plugins"
        command = (
            f"cd {shlex.quote(launcher_cwd_wsl)} && "
            f"exec env -i HOME={shlex.quote(home_wsl_abs)} USER=\"${{USER:-}}\" LOGNAME=\"${{LOGNAME:-}}\" "
            f"SHELL=/bin/bash PATH={shlex.quote(clean_path)} {env_passthrough}{codex_command} "
            f"app-server --listen {shlex.quote(ws_url)}{plugin_flags} --disable plugin_sharing --disable remote_plugin"
        )
        return {
            "codex_executable": wsl_executable,
            "launch_command": [wsl_executable, *distro_args, "--exec", "/bin/bash", "-lc", command],
            "ws_url": ws_url,
            "env_updates": env_updates,
            "cwd": None,
            "allow_plugins": bool(enable_computer_use_plugins),
        }

    def _app_server_launch_cwd(self) -> Path:
        """Keep Codex app-server process-local files out of the workspace root."""
        path = self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME / "runtime-cwd"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _terminate_stale_astrabridge_wsl_app_servers(self, wsl_executable: str, distro_args: list[str]) -> None:
        script = r'''
import os
import signal
import time

needle = "/.local/share/astrabridge/bin/codex app-server"
current = os.getpid()

def matching_pids():
    matches = []
    for raw_pid in os.listdir("/proc"):
        if not raw_pid.isdigit():
            continue
        pid = int(raw_pid)
        if pid == current:
            continue
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "ignore")
        except Exception:
            continue
        if needle in cmd:
            matches.append(pid)
    return matches

terminated = []
for pid in matching_pids():
    try:
        os.kill(pid, signal.SIGTERM)
        terminated.append(pid)
    except ProcessLookupError:
        pass
    except PermissionError:
        pass

if terminated:
    time.sleep(0.3)
    for pid in matching_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
print(",".join(str(pid) for pid in terminated))
'''
        command = "python3 - <<'PY'\n" + script.strip() + "\nPY"
        result = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", command])
        text = str(result.get("stdout") or "").strip()
        if text:
            self._record_event({"type": "wsl_app_server_cleanup", "terminated_pids": text.split(",")})

    def _wsl_expand_home(self, wsl_executable: str, distro_args: list[str], path: str) -> str:
        if not path.startswith("$HOME"):
            return path
        home = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", 'printf "%s" "$HOME"'])
        if int(home["returncode"]) != 0 or not str(home["stdout"]).strip():
            raise RuntimeError("WSL execution host is selected, but the Linux home directory could not be resolved.")
        return path.replace("$HOME", str(home["stdout"]).strip(), 1)

    def _sync_wsl_codex_home(
        self,
        runtime_status: dict[str, Any],
        wsl_executable: str,
        distro_args: list[str],
        codex_home_wsl_abs: str,
        home_wsl_abs: str,
    ) -> None:
        windows_codex_home = Path(str(runtime_status.get("codex_home") or "")).expanduser()
        config_path = windows_codex_home / "config.toml"
        models_dir = windows_codex_home / "models"
        models_cache = windows_codex_home / ASTRABRIDGE_MODELS_CACHE_FILENAME
        if not config_path.is_file() or not models_dir.is_dir():
            raise RuntimeError("AstraBridge runtime config was not rendered before WSL launch.")
        wsl_config_path = windows_codex_home / "config.wsl.toml"
        wsl_catalog_path = f"{codex_home_wsl_abs.rstrip('/')}/models/{ASTRABRIDGE_MODEL_CATALOG_FILENAME}"
        wsl_router_base_url = self._wsl_router_base_url(wsl_executable, distro_args)
        sidecar_source_wsl = self._windows_path_to_wsl(Path(__file__).resolve().parents[1])
        sidecar_link_wsl = f"{home_wsl_abs.rstrip('/')}/.local/share/astrabridge/sidecar-src"
        config_text = self._rewrite_wsl_config_text(
            config_path.read_text(encoding="utf-8"),
            codex_home_wsl_abs=codex_home_wsl_abs,
            router_base_url=wsl_router_base_url,
            sidecar_source_wsl=sidecar_source_wsl,
            sidecar_link_wsl=sidecar_link_wsl,
        )
        wsl_config_path.write_text(config_text, encoding="utf-8", newline="\n")
        source_home_wsl = self._windows_path_to_wsl(windows_codex_home)
        command = (
            f"mkdir -p {shlex.quote(codex_home_wsl_abs)} {shlex.quote(codex_home_wsl_abs + '/models')} {shlex.quote(posixpath.dirname(sidecar_link_wsl))} && "
            f"ln -sfn {shlex.quote(sidecar_source_wsl)} {shlex.quote(sidecar_link_wsl)} && "
            f"cp {shlex.quote(source_home_wsl + '/config.wsl.toml')} {shlex.quote(codex_home_wsl_abs + '/config.toml')} && "
            f"cp -R {shlex.quote(source_home_wsl + '/models/.')} {shlex.quote(codex_home_wsl_abs + '/models/')}"
        )
        if models_cache.is_file():
            command += f" && cp {shlex.quote(source_home_wsl + '/' + ASTRABRIDGE_MODELS_CACHE_FILENAME)} {shlex.quote(codex_home_wsl_abs + '/' + ASTRABRIDGE_MODELS_CACHE_FILENAME)}"
        result = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", command])
        if int(result["returncode"]) != 0:
            detail = str(result["stderr"] or result["stdout"]).strip()
            raise RuntimeError(f"Failed to sync AstraBridge Codex config into WSL CODEX_HOME: {detail}")

    def _rewrite_wsl_config_text(
        self,
        config_text: str,
        *,
        codex_home_wsl_abs: str,
        router_base_url: str | None = None,
        sidecar_source_wsl: str | None = None,
        sidecar_link_wsl: str | None = None,
    ) -> str:
        wsl_catalog_path = f"{codex_home_wsl_abs.rstrip('/')}/models/{ASTRABRIDGE_MODEL_CATALOG_FILENAME}"
        config_text = re.sub(
            r'^model_catalog_json = ".*"$',
            f'model_catalog_json = "{wsl_catalog_path.replace(chr(34), chr(92) + chr(34))}"',
            config_text,
            flags=re.MULTILINE,
        )
        if router_base_url:
            config_text = re.sub(
                r'^(base_url = ")http://(?:127\.0\.0\.1|localhost|0\.0\.0\.0):([0-9]+)/v1(")$',
                lambda match: f'{match.group(1)}{router_base_url.rsplit(":", 1)[0]}:{match.group(2)}/v1{match.group(3)}',
                config_text,
                flags=re.MULTILINE,
            )
        # MCP presets are rendered by the Windows sidecar. When app-server runs
        # inside WSL, Windows executables and paths in stdio MCP blocks must be
        # translated before Codex tries to launch them.
        config_text = re.sub(
            r'^(command = )"[A-Za-z]:\\\\[^"]*python(?:\.exe)?"$',
            r'\1"python3"',
            config_text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        config_text = re.sub(r'"[A-Za-z]:\\\\[^"]*"', self._replace_toml_windows_path_for_wsl, config_text)
        if sidecar_source_wsl and sidecar_link_wsl:
            config_text = config_text.replace(sidecar_source_wsl.rstrip("/"), sidecar_link_wsl.rstrip("/"))
        return config_text

    def _replace_toml_windows_path_for_wsl(self, match: re.Match[str]) -> str:
        escaped = match.group(0)[1:-1]
        windows_text = escaped.replace("\\\\", "\\")
        try:
            wsl_path = self._windows_path_to_wsl(Path(windows_text))
        except Exception:
            return match.group(0)
        return f'"{wsl_path.replace(chr(34), chr(92) + chr(34))}"'

    def _wsl_router_base_url(self, wsl_executable: str, distro_args: list[str]) -> str | None:
        candidates: list[str] = []

        def add_candidate(value: str | None) -> None:
            host = str(value or "").strip()
            if host and host not in candidates:
                candidates.append(host)

        add_candidate(os.environ.get("ASTRABRIDGE_WSL_HOST"))
        result = self._run_capture([wsl_executable, *distro_args, "ip", "route", "show", "default"])
        text = str(result.get("stdout") or "").strip()
        match = re.search(r"\bdefault\s+via\s+([0-9a-fA-F:.]+)\b", text)
        add_candidate(match.group(1) if match else "")
        fallback = self._run_capture([wsl_executable, *distro_args, "cat", "/etc/resolv.conf"])
        fallback_text = str(fallback.get("stdout") or "")
        for nameserver in re.findall(r"^nameserver\s+([0-9a-fA-F:.]+)\s*$", fallback_text, re.MULTILINE):
            add_candidate(nameserver)
        add_candidate("host.docker.internal")
        add_candidate("localhost")
        add_candidate("127.0.0.1")
        if not candidates:
            return None
        router_port = int(os.environ.get("ASTRABRIDGE_PORT") or ROUTER_PORT)
        expected_fingerprint = str(os.environ.get("ASTRABRIDGE_TOKEN_FINGERPRINT") or "").strip()
        attempts = self._probe_wsl_router_candidates(wsl_executable, distro_args, candidates, router_port)
        for attempt in attempts:
            if attempt.get("service") != "astrabridge":
                continue
            if expected_fingerprint and attempt.get("token_fingerprint") != expected_fingerprint:
                continue
            base_url = str(attempt.get("base_url") or "").strip()
            if base_url:
                self._record_event(
                    {
                        "type": "wsl_router_probe_selected",
                        "host": attempt.get("host"),
                        "token_fingerprint": attempt.get("token_fingerprint"),
                    }
                )
                return base_url
        self._record_event(
            {
                "type": "wsl_router_probe_failed",
                "expected_fingerprint": expected_fingerprint or None,
                "attempts": attempts[:8],
            }
        )
        reason = "no reachable AstraBridge router"
        if expected_fingerprint:
            reason = f"no reachable AstraBridge router with fingerprint {expected_fingerprint}"
        raise RuntimeError(
            f"WSL execution host is selected, but WSL could not reach the current AstraBridge ({reason}). "
            "Stop stale sidecars, check Windows firewall/port forwarding, or set ASTRABRIDGE_WSL_HOST."
        )

    def _probe_wsl_router_candidates(
        self,
        wsl_executable: str,
        distro_args: list[str],
        candidates: list[str],
        router_port: int,
    ) -> list[dict[str, Any]]:
        candidate_json = json.dumps(candidates, ensure_ascii=False)
        script = f"""
import json
import urllib.request

candidates = {candidate_json}
port = {int(router_port)}

def format_host(host):
    if ":" in host and not host.startswith("["):
        return "[" + host + "]"
    return host

for host in candidates:
    formatted = format_host(host)
    record = {{"host": host, "base_url": f"http://{{formatted}}:{{port}}"}}
    try:
        url = f"http://{{formatted}}:{{port}}/readyz"
        request = urllib.request.Request(url, headers={{"Accept": "application/json"}})
        with urllib.request.urlopen(request, timeout=1.5) as response:
            body = response.read(65536).decode("utf-8", "replace")
            payload = json.loads(body or "{{}}")
            record.update({{
                "status": getattr(response, "status", None),
                "ok": payload.get("ok"),
                "service": payload.get("service"),
                "token_fingerprint": payload.get("token_fingerprint"),
            }})
    except Exception as exc:
        record["error"] = str(exc)[:200]
    print(json.dumps(record, ensure_ascii=False))
"""
        command = "python3 - <<'PY'\n" + script.strip() + "\nPY"
        result = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", command])
        attempts: list[dict[str, Any]] = []
        if int(result.get("returncode") or 0) != 0:
            return [
                {
                    "error": str(result.get("stderr") or result.get("stdout") or "WSL router probe failed")[:300],
                    "returncode": result.get("returncode"),
                }
            ]
        for line in str(result.get("stdout") or "").splitlines():
            try:
                parsed = json.loads(line)
            except Exception:
                continue
            if isinstance(parsed, dict):
                attempts.append(parsed)
        return attempts

    def _reserve_loopback_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _list_wsl_distros(self, wsl_executable: str) -> list[str]:
        result = self._run_capture([wsl_executable, "-l", "-q"])
        if int(result["returncode"]) != 0:
            return []
        return [line.strip() for line in str(result["stdout"] or "").splitlines() if line.strip()]

    def _run_capture(self, command: list[str]) -> dict[str, Any]:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return {
            "returncode": completed.returncode,
            "stdout": self._decode_output(completed.stdout),
            "stderr": self._decode_output(completed.stderr),
        }

    def _decode_output(self, payload: bytes) -> str:
        if not payload:
            return ""
        for encoding in ("utf-8", "utf-16-le", "gbk", "cp936"):
            try:
                return payload.decode(encoding).replace("\x00", "").strip()
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="replace").replace("\x00", "").strip()

    def _wsl_codex_path_export(self) -> str:
        return f'export PATH="{ASTRABRIDGE_WSL_ROOT}/bin:$PATH"; '

    def _wsl_codex_command(self, codex_binary: str) -> str:
        if codex_binary in {"codex", ASTRABRIDGE_WSL_BIN}:
            return "codex"
        return self._quote_wsl_value(codex_binary)

    def _wsl_codex_probe_command(self, codex_binary: str) -> str:
        codex_command = self._wsl_codex_command(codex_binary)
        return (
            f"export CODEX_HOME={self._quote_wsl_value(os.environ.get('ASTRABRIDGE_WSL_CODEX_HOME') or ASTRABRIDGE_WSL_CODEX_HOME)}; "
            f"{self._wsl_codex_path_export()}"
            f'if ! command -v {codex_command} > /tmp/astrabridge_codex_probe_path 2>/dev/null; then echo "codex executable not found: {codex_command}" >&2; exit 127; fi; '
            'if grep -q "WindowsApps" /tmp/astrabridge_codex_probe_path; then printf "codex resolves to WindowsApps inside WSL: " >&2; cat /tmp/astrabridge_codex_probe_path >&2; exit 126; fi; '
            f"{codex_command} --version >/dev/null 2>&1"
        )

    def _quote_wsl_value(self, value: str) -> str:
        if value.startswith("$HOME/"):
            return f'"{value}"'
        return shlex.quote(value)

    def _wsl_runtime_env(self, runtime_status: dict[str, Any], codex_home_wsl: str) -> dict[str, str]:
        values = {
            "CODEX_HOME": codex_home_wsl,
            ROUTER_ENV_KEY: os.environ.get(ROUTER_ENV_KEY, ""),
            "NO_PROXY": os.environ.get("NO_PROXY", ""),
            "no_proxy": os.environ.get("no_proxy", ""),
        }
        try:
            workspace_root = self._projects.require_workspace_root()
            asset_root = workspace_root / WORKSPACE_STATE_DIRNAME / "assets" / "generated"
            # MCP servers may be launched as either WSL-native commands or Windows
            # executables from a WSL app-server. Keep the canonical variables in
            # host paths for Windows Python MCP servers and expose WSL variants for
            # native Linux tools.
            values["ASTRABRIDGE_WORKSPACE_ROOT"] = str(workspace_root)
            values["ASTRABRIDGE_ASSET_ROOT"] = str(asset_root)
            values["ASTRABRIDGE_WORKSPACE_ROOT_WSL"] = self._windows_path_to_wsl(workspace_root)
            values["ASTRABRIDGE_ASSET_ROOT_WSL"] = self._windows_path_to_wsl(asset_root)
            runtime_roots = self._projects.current_runtime_roots()
            values["ASTRABRIDGE_PROJECT_RUNTIME_ROOT"] = str(runtime_roots["project_runtime_root"])
            values["ASTRABRIDGE_DOWNLOADS_ROOT"] = str(runtime_roots["downloads_root"])
            values["ASTRABRIDGE_CACHES_ROOT"] = str(runtime_roots["caches_root"])
            values["ASTRABRIDGE_TMP_ROOT"] = str(runtime_roots["tmp_root"])
            values["ASTRABRIDGE_PROJECT_RUNTIME_ROOT_WSL"] = self._windows_path_to_wsl(runtime_roots["project_runtime_root"])
            values["ASTRABRIDGE_DOWNLOADS_ROOT_WSL"] = self._windows_path_to_wsl(runtime_roots["downloads_root"])
            values["ASTRABRIDGE_CACHES_ROOT_WSL"] = self._windows_path_to_wsl(runtime_roots["caches_root"])
            values["ASTRABRIDGE_TMP_ROOT_WSL"] = self._windows_path_to_wsl(runtime_roots["tmp_root"])
        except Exception:
            pass
        env_key = str(runtime_status.get("env_key") or "")
        if env_key:
            values[env_key] = os.environ.get(env_key, "")
        for mcp_env_key in self._mcp_passthrough_env_keys():
            if mcp_env_key not in values:
                values[mcp_env_key] = os.environ.get(mcp_env_key, "")
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            value = os.environ.get(key)
            if value:
                values[key] = value
        sanitized = {name: str(value) for name, value in values.items() if value is not None}
        passthrough_names = [name for name in sanitized if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name)]
        existing_wslenv = str(os.environ.get("WSLENV") or "").strip()
        wslenv_parts = [part for part in existing_wslenv.split(":") if part]
        existing_names = {part.split("/", 1)[0] for part in wslenv_parts}
        wslenv_parts.extend(name for name in passthrough_names if name not in existing_names)
        if wslenv_parts:
            sanitized["WSLENV"] = ":".join(wslenv_parts)
        return sanitized

    def _mcp_passthrough_env_keys(self) -> list[str]:
        names: set[str] = set()
        try:
            servers = self._mcp_config.enabled_servers()
        except Exception:
            servers = []
        for server in servers:
            for name in list(server.get("env_vars") or []):
                text = str(name or "").strip()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", text):
                    names.add(text)
            bearer = str(server.get("bearer_token_env_var") or "").strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", bearer):
                names.add(bearer)
            for value in dict(server.get("env_http_headers") or {}).values():
                text = str(value or "").strip()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", text):
                    names.add(text)
        return sorted(names)

    def _kernel_probe_runtime_roots(self, runtime_status: dict[str, Any]) -> dict[str, Any]:
        roots: dict[str, Any] = {}
        if self._projects is not None and hasattr(self._projects, "current_runtime_roots"):
            try:
                roots = {key: str(value) for key, value in dict(self._projects.current_runtime_roots()).items()}
            except Exception:  # noqa: BLE001
                roots = {}
        workspace_runtime_cwd = None
        try:
            workspace_runtime_cwd = str(self._app_server_launch_cwd().resolve())
        except Exception:  # noqa: BLE001
            workspace_runtime_cwd = None
        return {
            **roots,
            "workspace_runtime_cwd": workspace_runtime_cwd,
            "codex_home_root": str(runtime_status.get("codex_home") or roots.get("codex_home_root") or ""),
        }

    def _kernel_probe_search_roots(self) -> list[Path]:
        roots: list[Path] = []
        if self._projects is not None and hasattr(self._projects, "require_shell_state_root"):
            try:
                shell_root = Path(self._projects.require_shell_state_root()).resolve()
            except Exception:  # noqa: BLE001
                shell_root = None
            if shell_root is not None and shell_root not in roots:
                roots.append(shell_root)
        if self._projects is not None and hasattr(self._projects, "current_runtime_roots"):
            try:
                runtime_roots = dict(self._projects.current_runtime_roots())
            except Exception:  # noqa: BLE001
                runtime_roots = {}
            candidate = runtime_roots.get("project_runtime_root")
            if candidate:
                project_runtime_root = Path(candidate).resolve()
                if project_runtime_root not in roots:
                    roots.append(project_runtime_root)
        return roots

    def _kernel_probe_plugin_search_roots(self, base_roots: list[Path] | None = None) -> tuple[list[Path], list[str]]:
        roots: list[Path] = []
        for root in list(base_roots or self._kernel_probe_search_roots()):
            resolved = Path(root).resolve()
            if resolved not in roots:
                roots.append(resolved)
        warnings: list[str] = []
        projects = getattr(self, "_projects", None)
        if projects is None or not hasattr(projects, "require_shell_state_root"):
            return roots, warnings
        try:
            shell_root = Path(projects.require_shell_state_root()).resolve()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"fixture_shell_root_unavailable:{str(exc)[:200]}")
            return roots, warnings
        try:
            materialized = materialize_controlled_plugin_fixture_catalog(shell_root)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"fixture_catalog_materialize_failed:{str(exc)[:200]}")
            return roots, warnings
        fixture_root_text = str(materialized.get("search_root") or "").strip()
        if not fixture_root_text:
            return roots, warnings
        fixture_root = Path(fixture_root_text).resolve()
        if fixture_root not in roots:
            roots.append(fixture_root)
        return roots, warnings

    def _kernel_probe_app_server_status(
        self,
        runtime_status: dict[str, Any],
    ) -> tuple[dict[str, Any], Any | None, list[str]]:
        warnings: list[str] = []
        execution_host = self._execution_host()
        transport = "websocket" if execution_host == "wsl" else "stdio"
        launch_mode = "wsl_exec" if execution_host == "wsl" else "direct"
        client_factory = None
        initialize_status = "not_checked"
        available = False
        disconnect_status = "unknown"
        desired_signature = self._runtime_config.runtime_signature(runtime_status)
        if self._client is not None and self._client.is_running() and self._runtime_signature == desired_signature:
            launch_mode = "reused_client"
            available = True
            initialize_status = "supported"
            disconnect_status = "not_observed"
            client_factory = self._shared_probe_client_factory()
        else:
            try:
                launch_target = self._resolve_launch_target(runtime_status)
            except Exception as exc:  # noqa: BLE001
                warnings.append(str(exc)[:300])
            else:
                client_factory = self._spawned_probe_client_factory(launch_target)
                probe_client = client_factory(lambda method, params: None, lambda method, params: {})
                try:
                    probe_client.start()
                    available = True
                    initialize_status = "supported"
                    disconnect_status = "clean"
                except TimeoutError:
                    initialize_status = "error"
                    disconnect_status = "error"
                    warnings.append("kernel_probe_app_server_initialize_timed_out")
                except JsonRpcError as exc:
                    initialize_status = "unsupported" if int(exc.code or 0) == -32601 else "error"
                    disconnect_status = "error"
                    warnings.append(f"kernel_probe_app_server_initialize_jsonrpc:{exc.code}")
                except Exception as exc:  # noqa: BLE001
                    initialize_status = "error"
                    disconnect_status = "error"
                    warnings.append(str(exc)[:300])
                finally:
                    try:
                        probe_client.close()
                    except Exception:  # noqa: BLE001
                        pass
        snapshot = {
            "transport": transport,
            "launch_mode": launch_mode,
            "available": available,
            "initialize_status": initialize_status,
            "thread_start_status": "not_checked",
            "thread_resume_status": "not_checked",
            "turn_start_status": "not_checked",
            "approval_events_status": "not_checked",
            "mcp_elicitation_status": "not_checked",
            "disconnect_status": disconnect_status,
            "error_shape_status": "not_checked",
            "last_checked_at": now_iso(),
        }
        return snapshot, client_factory, warnings

    def _spawned_probe_client_factory(self, launch_target: dict[str, Any]) -> Any:
        def factory(on_notification: Any, on_server_request: Any) -> AppServerClient:
            env_updates = dict(launch_target.get("env_updates") or {})
            environment = dict(os.environ)
            environment.update(env_updates)
            return AppServerClient(
                codex_executable=launch_target.get("codex_executable"),
                launch_command=launch_target.get("launch_command"),
                ws_url=launch_target.get("ws_url"),
                env=environment,
                cwd=launch_target.get("cwd"),
                allow_plugins=bool(launch_target.get("allow_plugins")),
                on_notification=on_notification,
                on_server_request=on_server_request,
            )

        return factory

    def _shared_probe_client_factory(self) -> Any:
        client = self._client

        def factory(on_notification: Any, on_server_request: Any) -> "_ExistingProbeClient":
            del on_notification, on_server_request
            if client is None:
                raise RuntimeError("codex_app_server_not_running")
            return _ExistingProbeClient(client)

        return factory

    def _wsl_env_passthrough_args(self, env_values: dict[str, str]) -> str:
        assignments: list[str] = []
        for name in env_values:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                continue
            assignments.append(f'{name}="${{{name}:-}}"')
        return (" ".join(assignments) + " ") if assignments else ""

    def _thread_start_params(
        self,
        *,
        profile: dict[str, Any],
        model: str | None,
        permission_mode: str,
        include_dynamic_tools: bool = True,
        allowed_mcp_tool_names: set[str] | None = None,
        allow_browser_smoke: bool = True,
    ) -> dict[str, Any]:
        params = {
            "cwd": self._runtime_workspace_root(),
            "approvalsReviewer": "user",
            "modelProvider": profile.get("provider_id"),
            "model": codex_model_id(profile, model),
            "serviceName": "astrabridge_desktop",
        }
        dynamic_tools = (
            self._dynamic_tools(
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
            )
            if include_dynamic_tools
            else []
        )
        if dynamic_tools:
            params["dynamicTools"] = dynamic_tools
        params.update(self._thread_permission_overrides(permission_mode))
        return params

    def _dynamic_tools(
        self,
        *,
        allowed_mcp_tool_names: set[str] | None = None,
        allow_browser_smoke: bool = True,
    ) -> list[dict[str, Any]]:
        dynamic_tools: list[dict[str, Any]] = []
        if self._dogfood_run is not None and allow_browser_smoke:
            dynamic_tools.append(
                {
                    "name": BROWSER_SMOKE_TOOL_NAME,
                    "description": (
                        "Run a local browser smoke test for a localhost, 127.0.0.1, or file:// URL, optionally "
                        "performing simple UI actions, then record console errors and a screenshot in the AstraBridge "
                        "dogfood ledger. WSL-style file URLs such as file:///mnt/d/... are supported and normalized "
                        "for the host browser; do not start an ad-hoc HTTP server just to capture a screenshot. "
                        "For story/tutorial screens, prefer click_text_until_absent over guessing a fixed number of clicks. "
                        "Use expect_text/forbidden_text for the intended final state; without assertions the result is only "
                        "a screenshot/console smoke, not verified gameplay evidence. "
                        "Use this after UI/game changes instead of only claiming visual validation."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Local URL to smoke test. Must start with http://127.0.0.1:, http://localhost:, or file://.",
                            },
                            "label": {"type": "string", "description": "Short evidence label."},
                            "actions": {
                                "type": "array",
                                "maxItems": MAX_BROWSER_SMOKE_ACTIONS,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": [
                                                "click_text",
                                                "click_text_until_absent",
                                                "click_selector",
                                                "expect_selector",
                                                "expect_selector_count_at_least",
                                                "expect_text",
                                                "wait_for_text_absent",
                                                "press",
                                                "wait_ms",
                                                "wait",
                                                "pause",
                                            ],
                                        },
                                        "text": {"type": "string"},
                                        "selector": {"type": "string"},
                                        "count": {"type": "integer", "minimum": 1, "maximum": 50},
                                        "key": {"type": "string"},
                                        "ms": {"type": "integer", "minimum": 0, "maximum": 5000},
                                        "max_clicks": {"type": "integer", "minimum": 1, "maximum": 50},
                                        "settle_ms": {"type": "integer", "minimum": 0, "maximum": 2000},
                                        "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                                    },
                                    "required": ["type"],
                                    "additionalProperties": False,
                                },
                            },
                            "expect_text": {
                                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 20}],
                                "description": "Final-state text that must be visible before the screenshot counts as verified.",
                            },
                            "expect_selector": {
                                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 20}],
                                "description": "Final-state CSS selector that must be visible before the screenshot counts as verified.",
                            },
                            "expect_selector_count_at_least": {
                                "oneOf": [
                                    {
                                        "type": "object",
                                        "properties": {
                                            "selector": {"type": "string"},
                                            "count": {"type": "integer", "minimum": 1, "maximum": 50},
                                            "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                                        },
                                        "required": ["selector", "count"],
                                        "additionalProperties": False,
                                    },
                                    {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "selector": {"type": "string"},
                                                "count": {"type": "integer", "minimum": 1, "maximum": 50},
                                                "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                                            },
                                            "required": ["selector", "count"],
                                            "additionalProperties": False,
                                        },
                                        "maxItems": 20,
                                    },
                                ],
                                "description": "Final-state CSS selector that must resolve to at least count visible nodes before the screenshot counts as verified.",
                            },
                            "forbidden_text": {
                                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 20}],
                                "description": "Text that must be absent before the screenshot counts as verified; use this to ensure tutorial/dialog text such as Next is gone.",
                            },
                            "fail_if_text_visible": {
                                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 20}],
                                "description": "Alias for forbidden_text.",
                            },
                            "assert_timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                            "auto_milestone": {"type": "boolean", "default": True},
                        },
                        "required": ["url"],
                        "additionalProperties": False,
                    },
                }
            )
        if self._mcp_server_enabled("astrabridge_web"):
            web_tools: list[dict[str, Any]] = []
            web_tool_names: set[str] = set()
            for tool in astrabridge_web_dynamic_tools():
                name = str(tool.get("name") or "").strip()
                if not name:
                    continue
                if allowed_mcp_tool_names is not None and name not in allowed_mcp_tool_names:
                    continue
                if name not in web_tool_names:
                    web_tools.append(
                        {
                            "name": name,
                            "description": str(tool.get("description") or ""),
                            "inputSchema": dict(tool.get("inputSchema") or {}),
                        }
                    )
                    web_tool_names.add(name)
            dynamic_tools.extend(web_tools)
        if self._mcp_server_enabled("astrabridge_capabilities"):
            capability_tools: list[dict[str, Any]] = []
            capability_tool_names: set[str] = set()
            for tool in astrabridge_capability_dynamic_tools():
                name = str(tool.get("name") or "").strip()
                if not name or name in capability_tool_names:
                    continue
                if allowed_mcp_tool_names is not None and name not in allowed_mcp_tool_names:
                    continue
                capability_tools.append(
                    {
                        "name": name,
                        "description": str(tool.get("description") or ""),
                        "inputSchema": dict(tool.get("inputSchema") or {}),
                    }
                )
                capability_tool_names.add(name)
            dynamic_tools.extend(capability_tools)
        if self._mcp_server_enabled("yunwu_image"):
            dynamic_tools.extend(
                {
                    "name": str(tool.get("name") or ""),
                    "description": str(tool.get("description") or ""),
                    "inputSchema": dict(tool.get("inputSchema") or {}),
                }
                for tool in yunwu_image_dynamic_tools()
                if tool.get("name")
                and (
                    allowed_mcp_tool_names is None
                    or str(tool.get("name") or "").strip() in allowed_mcp_tool_names
                )
            )
        return dynamic_tools

    def _dynamic_tool_names(
        self,
        *,
        allowed_mcp_tool_names: set[str] | None = None,
        allow_browser_smoke: bool = True,
    ) -> set[str]:
        return {
            str(tool.get("name") or "")
            for tool in self._dynamic_tools(
                allowed_mcp_tool_names=allowed_mcp_tool_names,
                allow_browser_smoke=allow_browser_smoke,
            )
        }

    def _mcp_server_enabled(self, name: str) -> bool:
        try:
            servers = self._mcp_config.enabled_servers()
        except Exception:
            return False
        server_names = {str(server.get("name") or "") for server in servers}
        if name == "astrabridge_web":
            return "astrabridge_web" in server_names
        return any(name == server_name for server_name in server_names)

    def _thread_permission_overrides(self, permission_mode: str) -> dict[str, Any]:
        mode = (permission_mode or "auto").strip().lower()
        if mode == "ask":
            return {"approvalPolicy": "untrusted", "sandbox": "read-only"}
        if mode == "full":
            return {"approvalPolicy": "never", "sandbox": "danger-full-access"}
        return {"approvalPolicy": "on-request", "sandbox": "workspace-write"}

    def _turn_permission_overrides(self, permission_mode: str) -> dict[str, Any]:
        mode = (permission_mode or "auto").strip().lower()
        if mode == "ask":
            return {
                "approvalPolicy": "untrusted",
                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            }
        if mode == "full":
            return {
                "approvalPolicy": "never",
                "sandboxPolicy": {"type": "dangerFullAccess"},
            }
        return {
            "approvalPolicy": "on-request",
            "sandboxPolicy": {
                "type": "workspaceWrite",
                "writableRoots": [self._runtime_workspace_root()],
                "networkAccess": False,
                "excludeTmpdirEnvVar": False,
                "excludeSlashTmp": False,
            },
        }

    def _normalize_turn_execution_policy(self, value: str | None) -> str:
        normalized = str(value or "standard").strip().lower().replace("-", "_")
        if normalized not in VALID_TURN_EXECUTION_POLICIES:
            raise ValueError(f"Unsupported execution_policy={value!r}. Expected one of: {', '.join(sorted(VALID_TURN_EXECUTION_POLICIES))}.")
        return normalized

    def _supports_patch_only_execution_policy(self, profile: dict[str, Any], execution_backend: str) -> bool:
        """Fail closed until a runtime explicitly advertises a native patch-only guard.

        Provider metadata saying that a model understands `apply_patch` is not enough:
        AstraBridge also needs an app-server execution boundary that excludes shell
        and arbitrary file-change requests. This explicit flag is intentionally
        absent from current profiles until that boundary is verified end to end.
        """
        return bool(
            execution_backend == "app_server"
            and profile.get("verified_native_patch_only_enforcement") is True
        )

    def _execution_policy_prompt(self, policy: str, text: str) -> str:
        if policy == NO_TOOLS_EXECUTION_POLICY:
            return (
                "AstraBridge execution contract: answer directly from the supplied task context and declared artifacts. "
                "Do not invoke shell commands, file tools, web search, MCP, dynamic tools, user-input tools, or any other tool. "
                "If the task cannot be completed without a tool, return a concise blocked result instead of requesting one.\n\n"
                f"{text}"
            )
        if policy != PATCH_ONLY_EXECUTION_POLICY:
            return text
        return (
            "AstraBridge execution contract: use only the native apply_patch tool for code changes. "
            "Do not invoke shell commands or direct file-change tools. If native apply_patch is unavailable, stop and explain why.\n\n"
            f"{text}"
        )

    def _register_active_turn_execution_policy(
        self,
        thread_id: str,
        policy: str,
        *,
        mcp_tool_policy_snapshot: dict[str, Any] | None = None,
        mcp_tool_policy_context: dict[str, Any] | None = None,
    ) -> None:
        if not thread_id:
            return
        with self._lock:
            if policy in {PATCH_ONLY_EXECUTION_POLICY, NO_TOOLS_EXECUTION_POLICY} or bool(mcp_tool_policy_snapshot):
                self._active_turn_execution_policies[thread_id] = {
                    "policy": policy,
                    "turn_id": "",
                    "strict_thread_scope": policy == NO_TOOLS_EXECUTION_POLICY,
                    "mcp_tool_policy": deepcopy(dict(mcp_tool_policy_snapshot or {})),
                    "mcp_tool_policy_context": deepcopy(dict(mcp_tool_policy_context or {})),
                    "mcp_tool_call_counts": {},
                    "mcp_tool_approval_cache": {},
                }
            else:
                self._active_turn_execution_policies.pop(thread_id, None)

    def _record_execution_policy_started(self, *, thread_id: str, turn_id: str, policy: str) -> None:
        with self._lock:
            active = self._active_turn_execution_policies.get(thread_id)
            active_snapshot = dict(active or {})
        if policy not in {PATCH_ONLY_EXECUTION_POLICY, NO_TOOLS_EXECUTION_POLICY} and not dict(active_snapshot.get("mcp_tool_policy") or {}):
            return
        with self._lock:
            active = self._active_turn_execution_policies.get(thread_id)
            if active is not None:
                active["turn_id"] = turn_id
            stale_alias_keys = [
                key for key in self._observed_turn_aliases
                if key[0] == thread_id
            ]
            for key in stale_alias_keys:
                self._observed_turn_aliases.pop(key, None)
            self._fail_closed_turn_interrupts = {
                key for key in self._fail_closed_turn_interrupts if key[0] != thread_id
            }
        self._record_event(
            {
                "type": "turn_execution_policy_started",
                "thread_id": thread_id,
                "turn_id": turn_id,
                "policy": policy,
                "enforcement": (
                    "no_dynamic_tools_read_only_with_auto_decline_and_trace_audit"
                    if policy == NO_TOOLS_EXECUTION_POLICY
                    else (
                        "node_scoped_mcp_tool_reauthorization_with_allowlisted_exposure"
                        if dict(active_snapshot.get("mcp_tool_policy") or {})
                        else "native_apply_patch_only_with_approval_fallback"
                    )
                ),
                "mcp_policy_fingerprint": str(dict(active_snapshot.get("mcp_tool_policy") or {}).get("fingerprint") or "").strip() or None,
                "mcp_policy_revision": int(dict(active_snapshot.get("mcp_tool_policy") or {}).get("revision") or 0) or None,
                "mcp_policy_context": deepcopy(dict(active_snapshot.get("mcp_tool_policy_context") or {})),
            }
        )

    def _observed_turn_alias_target(self, *, thread_id: str, observed_turn_id: str) -> str:
        clean_thread_id = str(thread_id or "").strip()
        clean_observed_turn_id = str(observed_turn_id or "").strip()
        if not clean_thread_id or not clean_observed_turn_id:
            return ""
        with self._lock:
            record = dict(self._observed_turn_aliases.get((clean_thread_id, clean_observed_turn_id)) or {})
        return str(record.get("canonical_turn_id") or "").strip()

    def _remember_observed_turn_alias(
        self,
        *,
        thread_id: str,
        observed_turn_id: str,
        canonical_turn_id: str,
        source_method: str,
    ) -> None:
        clean_thread_id = str(thread_id or "").strip()
        clean_observed_turn_id = str(observed_turn_id or "").strip()
        clean_canonical_turn_id = str(canonical_turn_id or "").strip()
        if (
            not clean_thread_id
            or not clean_observed_turn_id
            or not clean_canonical_turn_id
            or clean_observed_turn_id == clean_canonical_turn_id
        ):
            return
        record = {
            "canonical_turn_id": clean_canonical_turn_id,
            "observed_turn_id": clean_observed_turn_id,
            "source_method": str(source_method or "").strip() or None,
            "updated_at": now_iso(),
        }
        with self._lock:
            self._observed_turn_aliases[(clean_thread_id, clean_observed_turn_id)] = record
            while len(self._observed_turn_aliases) > TERMINAL_TURN_NOTIFICATION_LIMIT:
                oldest_key = next(iter(self._observed_turn_aliases))
                self._observed_turn_aliases.pop(oldest_key, None)
        self._record_event(
            {
                "type": "turn_execution_policy_observed_turn_alias",
                "thread_id": clean_thread_id,
                "turn_id": clean_canonical_turn_id,
                "observed_turn_id": clean_observed_turn_id,
                "source_method": str(source_method or "").strip() or None,
            }
        )

    def _bind_observed_turn_to_active_policy(self, payload: dict[str, Any], *, source_method: str) -> str:
        if not isinstance(payload, dict):
            return ""
        alias_payload = dict(payload)
        if not str(alias_payload.get("turnId") or "").strip():
            nested_turn = dict(alias_payload.get("turn") or {})
            if nested_turn:
                alias_payload["turnId"] = nested_turn.get("id")
        thread_id = str(alias_payload.get("threadId") or "").strip()
        observed_turn_id = str(alias_payload.get("turnId") or "").strip()
        if not thread_id or not observed_turn_id:
            return ""
        active = self._active_turn_execution_policy_for(alias_payload)
        canonical_turn_id = str(dict(active or {}).get("turn_id") or "").strip()
        if not canonical_turn_id or canonical_turn_id == observed_turn_id:
            return canonical_turn_id
        terminal_notification = self._terminal_turn_notification(
            thread_id=thread_id,
            turn_id=canonical_turn_id,
        )
        terminal_status = self._normalize_terminal_turn_status(
            dict(terminal_notification or {}).get("status")
        )
        if terminal_status in TERMINAL_TURN_STATUSES:
            return canonical_turn_id
        self._remember_observed_turn_alias(
            thread_id=thread_id,
            observed_turn_id=observed_turn_id,
            canonical_turn_id=canonical_turn_id,
            source_method=source_method,
        )
        return canonical_turn_id

    def _active_turn_execution_policy_for(self, params: Any) -> dict[str, Any] | None:
        payload = dict(params or {}) if isinstance(params, dict) else {}
        thread_id = str(payload.get("threadId") or "")
        turn_id = str(payload.get("turnId") or "")
        if not thread_id:
            return None
        with self._lock:
            active = dict(self._active_turn_execution_policies.get(thread_id) or {})
        if not active:
            return None
        active_turn_id = str(active.get("turn_id") or "")
        if (
            active_turn_id
            and turn_id
            and active_turn_id != turn_id
            and not bool(active.get("strict_thread_scope"))
        ):
            if self._observed_turn_alias_target(thread_id=thread_id, observed_turn_id=turn_id) != active_turn_id:
                return None
        return active

    def _clear_active_turn_execution_policy(self, *, thread_id: str, turn_id: str) -> None:
        clean_thread_id = str(thread_id or "").strip()
        clean_turn_id = str(turn_id or "").strip()
        if not clean_thread_id:
            return
        with self._lock:
            active = dict(self._active_turn_execution_policies.get(clean_thread_id) or {})
            if not active:
                return
            active_turn_id = str(active.get("turn_id") or "").strip()
            if (
                active_turn_id
                and clean_turn_id
                and active_turn_id != clean_turn_id
                and not bool(active.get("strict_thread_scope"))
            ):
                if self._observed_turn_alias_target(thread_id=clean_thread_id, observed_turn_id=clean_turn_id) != active_turn_id:
                    return
            self._active_turn_execution_policies.pop(clean_thread_id, None)
            stale_alias_keys = [
                key for key in self._observed_turn_aliases
                if key[0] == clean_thread_id
            ]
            for key in stale_alias_keys:
                self._observed_turn_aliases.pop(key, None)
            self._fail_closed_turn_interrupts = {
                key for key in self._fail_closed_turn_interrupts if key[0] != clean_thread_id
            }

    @staticmethod
    def _execution_policy_decline_response(method: str) -> dict[str, Any]:
        if method == "execCommandApproval":
            return {"decision": "denied"}
        if method == "item/tool/requestUserInput":
            return {"answers": {}}
        if method == "mcpServer/elicitation/request":
            return {"action": "decline"}
        return {"decision": "decline"}

    def _record_execution_policy_tool_blocked(
        self,
        payload: dict[str, Any],
        *,
        policy: str,
        request_method: str,
        tool_name: str | None = None,
        item_type: str | None = None,
        item_id: str | None = None,
    ) -> None:
        active = self._active_turn_execution_policy_for(payload)
        observed_turn_id = str(payload.get("turnId") or "").strip()
        canonical_turn_id = str(dict(active or {}).get("turn_id") or observed_turn_id).strip()
        self._record_event(
            {
                "type": "turn_execution_policy_tool_blocked",
                "thread_id": payload.get("threadId"),
                "turn_id": canonical_turn_id or None,
                "observed_turn_id": observed_turn_id or None,
                "policy": policy,
                "request_method": request_method,
                "tool_name": str(tool_name or "").strip() or None,
                "item_type": str(item_type or "").strip() or None,
                "item_id": str(item_id or "").strip() or None,
                "reason": "tool_not_declared_by_task_graph_node",
                "compliant_success": False,
            }
        )

    def _record_no_tools_notification_violation(self, method: str, payload: dict[str, Any]) -> None:
        if method not in {"item/started", "item/completed", "item/updated"}:
            return
        active = self._active_turn_execution_policy_for(payload)
        if active is None or active.get("policy") != NO_TOOLS_EXECUTION_POLICY:
            return
        item = dict(payload.get("item") or {})
        item_type = str(item.get("type") or "").strip()
        compact_type = re.sub(r"[^a-z]", "", item_type.lower())
        if not any(
            marker in compact_type
            for marker in ("commandexecution", "filechange", "toolcall", "websearch", "applypatch")
        ):
            return
        self._record_execution_policy_tool_blocked(
            payload,
            policy=NO_TOOLS_EXECUTION_POLICY,
            request_method=method,
            tool_name=str(item.get("tool") or item.get("name") or "").strip() or None,
            item_type=item_type,
            item_id=str(item.get("id") or "").strip() or None,
        )
        if method == "item/started":
            self._interrupt_fail_closed_no_tools_turn(
                payload,
                request_method=method,
                item_type=item_type,
                item_id=str(item.get("id") or "").strip() or None,
            )

    def _interrupt_fail_closed_no_tools_turn(
        self,
        payload: dict[str, Any],
        *,
        request_method: str,
        item_type: str | None = None,
        item_id: str | None = None,
    ) -> None:
        active = self._active_turn_execution_policy_for(payload)
        if active is None or active.get("policy") != NO_TOOLS_EXECUTION_POLICY:
            return
        thread_id = str(payload.get("threadId") or "").strip()
        observed_turn_id = str(payload.get("turnId") or "").strip()
        canonical_turn_id = str(dict(active).get("turn_id") or "").strip()
        if not thread_id or not observed_turn_id:
            return
        if canonical_turn_id:
            terminal_notification = self._terminal_turn_notification(
                thread_id=thread_id,
                turn_id=canonical_turn_id,
            )
            terminal_status = self._normalize_terminal_turn_status(
                dict(terminal_notification or {}).get("status")
            )
            if terminal_status in TERMINAL_TURN_STATUSES:
                return
        interrupt_key = (thread_id, observed_turn_id)
        with self._lock:
            if interrupt_key in self._fail_closed_turn_interrupts:
                return
            self._fail_closed_turn_interrupts.add(interrupt_key)
        settings = self._thread_settings_for(thread_id)
        profile = self._resolve_shell_profile(str(settings.get("profile_id") or ""))
        self._record_event(
            {
                "type": "turn_execution_policy_fail_closed_interrupt_requested",
                "thread_id": thread_id,
                "turn_id": canonical_turn_id or None,
                "observed_turn_id": observed_turn_id,
                "policy": NO_TOOLS_EXECUTION_POLICY,
                "request_method": request_method,
                "item_type": str(item_type or "").strip() or None,
                "item_id": str(item_id or "").strip() or None,
            }
        )
        try:
            interrupt_result = self.interrupt_turn(profile, thread_id, observed_turn_id)
        except Exception as exc:
            self._record_event(
                {
                    "type": "turn_execution_policy_fail_closed_interrupt_failed",
                    "thread_id": thread_id,
                    "turn_id": canonical_turn_id or None,
                    "observed_turn_id": observed_turn_id,
                    "policy": NO_TOOLS_EXECUTION_POLICY,
                    "request_method": request_method,
                    "error": str(exc)[:300],
                }
            )
            return
        resolved_turn_id = str(
            dict(dict(interrupt_result or {}).get("interrupt") or {}).get("turnId")
            or observed_turn_id
        ).strip() or observed_turn_id
        self._record_event(
            {
                "type": "turn_execution_policy_fail_closed_interrupt_succeeded",
                "thread_id": thread_id,
                "turn_id": canonical_turn_id or None,
                "observed_turn_id": observed_turn_id,
                "resolved_turn_id": resolved_turn_id,
                "policy": NO_TOOLS_EXECUTION_POLICY,
                "request_method": request_method,
            }
        )

    def _turn_execution_policy_violation(self, *, thread_id: str, turn_id: str) -> dict[str, Any] | None:
        clean_thread_id = str(thread_id or "").strip()
        clean_turn_id = str(turn_id or "").strip()
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        matches = [
            event
            for event in events
            if event.get("type") == "turn_execution_policy_tool_blocked"
            and str(event.get("thread_id") or "").strip() == clean_thread_id
            and (not clean_turn_id or not str(event.get("turn_id") or "").strip() or str(event.get("turn_id") or "").strip() == clean_turn_id)
        ]
        if not matches:
            return None
        unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for event in matches:
            key = (
                str(event.get("request_method") or ""),
                str(event.get("item_id") or ""),
                str(event.get("item_type") or ""),
                str(event.get("tool_name") or ""),
            )
            unique[key] = event
        return {
            "status": "violated",
            "policy": NO_TOOLS_EXECUTION_POLICY,
            "blocked_tool_call_count": len(unique),
            "request_methods": sorted({str(item.get("request_method") or "") for item in unique.values()}),
            "tool_names": sorted({str(item.get("tool_name") or "") for item in unique.values() if item.get("tool_name")}),
            "item_types": sorted({str(item.get("item_type") or "") for item in unique.values() if item.get("item_type")}),
            "reason": "model_requested_tools_outside_task_graph_contract",
            "compliant_success": False,
        }

    def _collaboration_mode_params(
        self,
        *,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        collaboration_mode: str | None,
    ) -> dict[str, Any] | None:
        if collaboration_mode is None:
            return None
        mode = collaboration_mode.strip().lower()
        if mode not in VALID_COLLABORATION_MODES:
            raise ValueError(f"Unsupported collaboration mode: {collaboration_mode}")
        return {
            "mode": mode,
            "settings": {
                "model": codex_model_id(profile, model),
                "reasoning_effort": codex_reasoning_effort(effort or profile.get("reasoning_effort")),
                "developer_instructions": None,
            },
        }

    def _read_thread_cache(self) -> dict[str, Any]:
        path = self._projects.require_shell_state_root() / "thread_cache.json"
        with self._thread_cache_lock:
            try:
                cache = read_json(path, {"by_id": {}, "updated_at": None})
            except Exception as exc:  # noqa: BLE001
                self._record_event(
                    {
                        "type": "thread_cache_read_failed",
                        "path": str(path),
                        "error": str(exc)[:300],
                    }
                )
                return {"by_id": {}, "updated_at": None}
        if not isinstance(cache, dict):
            return {"by_id": {}, "updated_at": None}
        return cache

    def _cached_threads_response(self, *, archived: bool = False, warning: str | None = None) -> dict[str, Any]:
        if archived:
            return {"threads": [], "next_cursor": None, "backwards_cursor": None, "warning": warning}
        cache = self._read_thread_cache()
        by_id = dict(cache.get("by_id") or {})
        current = self._projects.current_project or {}
        ordered_ids: list[str] = []
        for thread_id in current.get("recent_threads") or []:
            if isinstance(thread_id, str) and thread_id and thread_id not in ordered_ids:
                ordered_ids.append(thread_id)
        for thread_id in by_id.keys():
            if thread_id not in ordered_ids:
                ordered_ids.append(thread_id)
        threads = [thread for thread_id in ordered_ids if (thread := self._cached_thread(thread_id))]
        return {"threads": threads, "next_cursor": None, "backwards_cursor": None, "warning": warning}

    def _cached_thread(self, thread_id: str, warning: str | None = None) -> dict[str, Any] | None:
        if not thread_id:
            return None
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        native_thread = entry.get("thread")
        if isinstance(native_thread, dict):
            thread = dict(native_thread)
            if warning:
                thread["shellWarning"] = warning
            return self._decorate_thread(thread)
        if not entry and thread_id not in (self._projects.current_project or {}).get("recent_threads", []):
            return None
        name = entry.get("name") or thread_id
        thread = {
            "id": thread_id,
            "sessionId": thread_id,
            "name": name,
            "preview": "",
            "status": self._thread_cache_status(thread_id) or {"type": "idle"},
            "cwd": self._runtime_workspace_root(),
            "turns": [],
            "shellWarning": warning,
        }
        return self._decorate_thread(thread)

    def _native_cached_threads(self) -> list[dict[str, Any]]:
        cache = self._read_thread_cache()
        threads: list[dict[str, Any]] = []
        for entry in list((cache.get("by_id") or {}).values()):
            if not isinstance(entry, dict):
                continue
            native_thread = entry.get("thread")
            if not isinstance(native_thread, dict):
                continue
            threads.append(self._decorate_thread(dict(native_thread)))
        threads.sort(key=lambda item: str(item.get("status", {}).get("updated_at") or ""), reverse=True)
        return threads

    def _read_native_thread(self, thread_id: str) -> dict[str, Any] | None:
        if not thread_id:
            return None
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        native_thread = entry.get("thread")
        if not isinstance(native_thread, dict):
            native_thread = None
        transcript_thread = None
        if self._task_conversation is not None:
            try:
                transcript_thread = self._task_conversation.thread_snapshot(thread_id)
            except Exception:
                transcript_thread = None
        if isinstance(native_thread, dict) and isinstance(transcript_thread, dict):
            native_turns = len([item for item in list(native_thread.get("turns") or []) if isinstance(item, dict)])
            transcript_turns = len([item for item in list(transcript_thread.get("turns") or []) if isinstance(item, dict)])
            return dict(transcript_thread if transcript_turns > native_turns else native_thread)
        if isinstance(native_thread, dict):
            return dict(native_thread)
        # An empty task transcript is only a route placeholder created during
        # thread setup. It must not hide a later provider-backed thread/read,
        # otherwise a fresh handoff appears to have no assistant output.
        if isinstance(transcript_thread, dict) and list(transcript_thread.get("turns") or []):
            return dict(transcript_thread)
        return None

    def _cache_thread_entry(self, thread_id: str, patch: dict[str, Any]) -> None:
        if not thread_id:
            return
        with self._thread_cache_lock:
            cache = self._read_thread_cache()
            by_id = dict(cache.get("by_id") or {})
            current = dict(by_id.get(thread_id) or {})
            sanitized_patch = dict(patch)
            if "name" in sanitized_patch:
                sanitized_patch["name"] = _display_thread_name(
                    sanitized_patch.get("name"),
                    sanitized_patch.get("provider_id") or current.get("provider_id"),
                )
            merged = {
                **current,
                **{key: value for key, value in sanitized_patch.items() if value is not None},
                "thread_id": thread_id,
                "updated_at": now_iso(),
            }
            by_id[thread_id] = merged
            cache["by_id"] = by_id
            cache["updated_at"] = now_iso()
            path = self._projects.require_shell_state_root() / "thread_cache.json"
            try:
                write_json(path, cache)
            except Exception as exc:  # noqa: BLE001
                self._record_event(
                    {
                        "type": "thread_cache_write_failed",
                        "thread_id": thread_id,
                        "path": str(path),
                        "error": str(exc)[:300],
                    }
                )
                return
        hint_patch = {key: value for key, value in merged.items() if key != "thread"}
        self._record_project_context_hint(thread_id, hint_patch)

    def _record_project_context_hint(self, thread_id: str, patch: dict[str, Any]) -> None:
        if self._project_context is None:
            return
        try:
            self._project_context.record_thread_hint(thread_id, patch)
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "project_context_hint_failed", "thread_id": thread_id, "error": str(exc)[:300]})

    def _record_project_context_notification(self, method: str, payload: Any) -> None:
        if self._project_context is None:
            return
        try:
            self._project_context.record_runtime_notification(method, payload)
            if self._tasks is not None and isinstance(payload, dict):
                thread_id = str(payload.get("threadId") or payload.get("thread_id") or "")
                if not thread_id and isinstance(payload.get("thread"), dict):
                    thread_id = str(payload.get("thread", {}).get("id") or "")
                if method == "turn/plan/updated" and thread_id:
                    self._tasks.record_plan(
                        thread_id,
                        {
                            "turn_id": str(payload.get("turnId") or ""),
                            "explanation": payload.get("explanation"),
                            "steps": list(payload.get("plan") or []),
                            "updated_at": now_iso(),
                        },
                    )
                elif method == "thread/goal/updated" and thread_id:
                    incoming_goal = payload.get("goal") or {}
                    if isinstance(incoming_goal, dict):
                        existing_goal = self._local_goal_state(thread_id)
                        normalized_goal = {**incoming_goal, "threadId": thread_id}
                        existing_status = str((existing_goal or {}).get("status") or "").strip()
                        incoming_status = str(normalized_goal.get("status") or "").strip()
                        if existing_status and incoming_status in {"", "active"} and existing_status != "active":
                            normalized_goal["status"] = existing_status
                        self._tasks.record_goal(thread_id, normalized_goal)
                    else:
                        self._tasks.record_goal(thread_id, incoming_goal)
                elif method == "thread/goal/cleared" and thread_id:
                    self._tasks.record_goal(thread_id, None)
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "project_context_notification_failed", "method": method, "error": str(exc)[:300]})

    def _thread_settings_for(self, thread_id: str) -> dict[str, Any]:
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        task_entry = self._task_thread_entry(thread_id)
        if task_entry:
            entry = {**task_entry, **entry}
        current = self._projects.current_project or {}
        normalized = self._normalize_shell_settings(entry, current_project=current, prefer_project_defaults=True)
        cache_patch = {
            "profile_id": normalized.get("profile_id"),
            "model": normalized.get("model"),
            "reasoning_effort": normalized.get("reasoning_effort"),
            "permission_mode": normalized.get("permission_mode"),
            "collaboration_mode": normalized.get("collaboration_mode"),
            "execution_backend": normalized.get("execution_backend"),
        }
        if any(entry.get(key) != value for key, value in cache_patch.items() if value is not None):
            self._cache_thread_entry(thread_id, cache_patch)
        return normalized

    def _task_thread_entry(self, thread_id: str) -> dict[str, Any]:
        if self._tasks is None:
            return {}
        try:
            task = self._tasks.current_task() or {}
        except Exception:
            return {}
        for collection_key in ("provider_threads", "fork_threads"):
            for item in list(task.get(collection_key) or []):
                if str((item or {}).get("thread_id") or "") == thread_id:
                    return dict(item)
        return {}

    def _normalize_shell_settings(
        self,
        settings: dict[str, Any],
        *,
        current_project: dict[str, Any],
        prefer_project_defaults: bool,
    ) -> dict[str, Any]:
        project_profile_id = str(current_project.get("default_profile_id") or "").strip()
        chosen_profile_id = str(settings.get("profile_id") or "").strip()
        target_profile = self._resolve_shell_profile(chosen_profile_id or project_profile_id)
        provider_id = str(target_profile.get("provider_id") or "openai").strip() or "openai"
        profile_id = str(target_profile.get("profile_id") or project_profile_id or "openai-compatible").strip()
        project_model = self._normalize_shell_model(current_project.get("default_model"), provider_id)
        chosen_model = self._normalize_shell_model(settings.get("model"), provider_id)
        if prefer_project_defaults and not chosen_model:
            chosen_model = project_model
        if not chosen_model or self._shell_model_provider_mismatch(chosen_model, provider_id):
            chosen_model = self._normalize_shell_model(target_profile.get("model"), provider_id) or project_model
        project_effort = codex_reasoning_effort(current_project.get("default_effort"))
        chosen_effort = codex_reasoning_effort(settings.get("reasoning_effort"))
        if prefer_project_defaults and not str(settings.get("reasoning_effort") or "").strip():
            chosen_effort = project_effort
        permission_mode = str(settings.get("permission_mode") or "").strip().lower() or "auto"
        if permission_mode not in {"ask", "auto", "full"}:
            permission_mode = "auto"
        collaboration_mode = str(settings.get("collaboration_mode") or "").strip().lower() or "default"
        if collaboration_mode not in VALID_COLLABORATION_MODES:
            collaboration_mode = "default"
        execution_backend = self._normalize_execution_backend(settings.get("execution_backend"))
        return {
            "profile_id": profile_id,
            "model": (
                chosen_model
                or self._normalize_shell_model(target_profile.get("model"), provider_id)
                or self._default_model_for_provider(provider_id)
            ),
            "reasoning_effort": chosen_effort or codex_reasoning_effort(target_profile.get("reasoning_effort")),
            "permission_mode": permission_mode,
            "collaboration_mode": collaboration_mode,
            "execution_backend": execution_backend,
        }

    def _normalize_execution_backend(self, value: Any) -> str:
        backend = str(value or "").strip().lower() or "app_server"
        if backend not in VALID_EXECUTION_BACKENDS:
            return "app_server"
        return backend

    def _resolve_shell_profile(self, profile_id: str) -> dict[str, Any]:
        fallback = "openai-compatible"
        try:
            return self._profiles.resolve_runtime_profile(profile_id or fallback)
        except Exception:
            try:
                return self._profiles.resolve_runtime_profile(fallback)
            except Exception:
                return {
                    "profile_id": fallback,
                    "provider_id": "openai",
                    "model": _OPENAI_DEFAULT_MODEL,
                    "reasoning_effort": "high",
                }

    @staticmethod
    def _default_model_for_provider(provider_id: str) -> str:
        provider = str(provider_id or "openai").strip() or "openai"
        preferred_model = (preferred_provider_model_record(provider, include_deprecated=False) or {}).get("native_model")
        return str(preferred_model or _OPENAI_DEFAULT_MODEL).strip() or _OPENAI_DEFAULT_MODEL

    def _normalize_shell_model(self, value: Any, provider_id: str) -> str:
        model = str(value or "").strip()
        if not model:
            return ""
        if "/" not in model:
            return model
        model_provider, native_model = model.split("/", 1)
        if model_provider.strip().lower() == provider_id.strip().lower():
            return native_model.strip()
        return model

    def _shell_model_provider_mismatch(self, model: str, provider_id: str) -> bool:
        if "/" not in model:
            return False
        model_provider, _native_model = model.split("/", 1)
        return model_provider.strip().lower() != provider_id.strip().lower()

    def _decorate_thread(self, thread: dict[str, Any]) -> dict[str, Any]:
        thread_id = str(thread.get("id") or "")
        settings = self._thread_settings_for(thread_id) if thread_id else {}
        display_name = (
            _display_thread_name(thread.get("name"), settings.get("provider_id") or settings.get("profile_id"))
            or self._thread_cache_name(thread_id)
            or str(thread.get("preview") or thread_id)
        )
        normalized_status = self._normalize_thread_status(thread)
        if thread_id:
            normalized_status = self._overlay_cached_thread_status(thread_id, normalized_status)
        return {**thread, "status": normalized_status, "shellSettings": settings, "displayName": display_name}

    def _decorate_turn_coding_events(self, thread: dict[str, Any]) -> dict[str, Any]:
        turns = list(thread.get("turns") or [])
        if not turns:
            return thread
        thread_id = str(thread.get("id") or "")
        task_id = self._task_id_for_thread(thread_id)
        execution_backend = str((thread.get("shellSettings") or {}).get("execution_backend") or "").strip()
        source = "native_kernel" if execution_backend == "native_kernel" else "codex_app_server"
        decorated_turns: list[dict[str, Any]] = []
        changed = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            enriched = dict(turn)
            if thread_id and not enriched.get("source_thread_id") and not enriched.get("sourceThreadId"):
                enriched["source_thread_id"] = thread_id
            if not enriched.get("provider_id") and not enriched.get("providerId"):
                provider_id = str((thread.get("shellSettings") or {}).get("provider_id") or "").strip()
                if provider_id:
                    enriched["provider_id"] = provider_id
            if not enriched.get("model"):
                model = str((thread.get("shellSettings") or {}).get("model") or "").strip()
                if model:
                    enriched["model"] = model
            coding_events = project_turn_to_coding_events(
                task_id=task_id,
                visible_thread_id=thread_id or "thread:unknown",
                turn=enriched,
                source=source,
            )
            if enriched.get("coding_events") != coding_events:
                enriched["coding_events"] = coding_events
                changed = True
            decorated_turns.append(enriched)
        return {**thread, "turns": decorated_turns} if changed else thread

    def _task_id_for_thread(self, thread_id: str) -> str:
        if not thread_id or self._tasks is None:
            return ""
        snapshot = self._tasks.snapshot() or {}
        for task in list(snapshot.get("tasks") or []):
            if not isinstance(task, dict):
                continue
            if any(str(item.get("thread_id") or "") == thread_id for item in list(task.get("provider_threads") or []) if isinstance(item, dict)):
                return str(task.get("task_id") or "")
        return ""

    def _normalize_thread_status(self, thread: dict[str, Any]) -> dict[str, Any] | Any:
        status = thread.get("status")
        if not isinstance(status, dict):
            return status
        status_type = str(status.get("type") or "")
        if status_type not in {"systemError", "notLoaded"}:
            return status
        turns = [item for item in list(thread.get("turns") or []) if isinstance(item, dict)]
        if not turns:
            return status
        latest_turn = turns[-1]
        latest_error = latest_turn.get("error")
        if str(latest_turn.get("status") or "") == "completed" and (
            latest_error is None or latest_error == "" or latest_error == {}
        ):
            normalized = dict(status)
            normalized["type"] = "idle"
            normalized["stale_error_type"] = status_type
            normalized["stale_error_normalized"] = True
            return normalized
        return status

    def _thread_cache_status(self, thread_id: str) -> dict[str, Any] | None:
        if not thread_id:
            return None
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        status = entry.get("status")
        return dict(status) if isinstance(status, dict) else None

    def _overlay_cached_thread_status(self, thread_id: str, status: dict[str, Any] | Any) -> dict[str, Any] | Any:
        if not isinstance(status, dict):
            return status
        cached_status = self._thread_cache_status(thread_id)
        if not isinstance(cached_status, dict):
            return status
        if str(status.get("type") or "") not in {"systemError", "notLoaded"}:
            return status
        if str(cached_status.get("type") or "") == "idle" and cached_status.get("stale_error_normalized"):
            return cached_status
        return status

    def _overlay_dynamic_tool_events(self, thread: dict[str, Any]) -> dict[str, Any]:
        """Make app-server dynamic tool events visible when thread/read omits them."""
        thread_id = str(thread.get("id") or "")
        turns = list(thread.get("turns") or [])
        if not thread_id or not turns:
            return thread
        turn_ids = {str(turn.get("id") or "") for turn in turns if isinstance(turn, dict)}
        if not turn_ids:
            return thread
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        tool_items: dict[str, list[tuple[int, dict[str, Any]]]] = {turn_id: [] for turn_id in turn_ids}
        latest_by_item: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
        for event in events:
            if event.get("type") != "notification" or event.get("method") not in {"item/started", "item/completed"}:
                continue
            params = dict(event.get("params") or {})
            if str(params.get("threadId") or "") != thread_id:
                continue
            turn_id = str(params.get("turnId") or "")
            if turn_id not in turn_ids:
                continue
            item = dict(params.get("item") or {})
            if item.get("type") != "dynamicToolCall":
                continue
            item_id = str(item.get("id") or "")
            if not item_id:
                continue
            latest_by_item[(turn_id, item_id)] = (int(event.get("index") or 0), item)
        for (turn_id, _item_id), entry in latest_by_item.items():
            tool_items.setdefault(turn_id, []).append(entry)
        decorated_turns: list[dict[str, Any]] = []
        changed_thread = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            turn_id = str(turn.get("id") or "")
            extras = [item for _index, item in sorted(tool_items.get(turn_id, []), key=lambda pair: pair[0])]
            if not extras:
                decorated_turns.append(turn)
                continue
            items = [dict(item) if isinstance(item, dict) else item for item in list(turn.get("items") or [])]
            latest_by_id = {
                str(item.get("id") or ""): item
                for item in extras
                if isinstance(item, dict) and str(item.get("id") or "")
            }
            merged_items: list[Any] = []
            turn_changed = False
            existing_ids: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    merged_items.append(item)
                    continue
                item_id = str(item.get("id") or "")
                if item_id:
                    existing_ids.add(item_id)
                latest_item = latest_by_id.get(item_id)
                if latest_item:
                    merged_item = {**item, **latest_item}
                    if merged_item != item:
                        turn_changed = True
                    merged_items.append(merged_item)
                else:
                    merged_items.append(item)
            missing = [item for item in extras if str(item.get("id") or "") not in existing_ids]
            if not missing:
                if turn_changed:
                    decorated_turns.append({**turn, "items": merged_items})
                    changed_thread = True
                else:
                    decorated_turns.append(turn)
                continue
            insert_at = next(
                (idx for idx, item in enumerate(merged_items) if isinstance(item, dict) and item.get("type") == "agentMessage"),
                len(merged_items),
            )
            merged_items[insert_at:insert_at] = missing
            decorated_turns.append({**turn, "items": merged_items})
            changed_thread = True
        return {**thread, "turns": decorated_turns} if changed_thread else thread

    def _decorate_dynamic_tool_evidence(self, thread: dict[str, Any]) -> dict[str, Any]:
        """Attach compact, UI-ready verification metadata to dynamic tool items."""
        turns = list(thread.get("turns") or [])
        if not turns:
            return thread
        decorated_turns: list[dict[str, Any]] = []
        changed = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            items = list(turn.get("items") or [])
            decorated_items: list[Any] = []
            for item in items:
                if not isinstance(item, dict):
                    decorated_items.append(item)
                    continue
                evidence = self._item_verified_evidence(item)
                if evidence:
                    item = {**item, "verifiedEvidence": evidence}
                    changed = True
                decorated_items.append(item)
            decorated_turns.append({**turn, "items": decorated_items} if changed else turn)
        return {**thread, "turns": decorated_turns} if changed else thread

    def _item_verified_evidence(self, item: dict[str, Any]) -> dict[str, Any] | None:
        item_type = str(item.get("type") or "")
        if item_type == "dynamicToolCall":
            return self._dynamic_tool_verified_evidence(item)
        if item_type == "commandExecution":
            return self._command_execution_verified_evidence(item)
        return None

    def _dynamic_tool_verified_evidence(self, item: dict[str, Any]) -> dict[str, Any] | None:
        tool = str(item.get("tool") or item.get("name") or "").strip()
        if not tool:
            return None
        summary = self._dynamic_tool_summary_from_item(item)
        verified = bool(summary.get("tool_event_verified")) if summary else False
        content_text = self._dynamic_tool_content_text(item)
        if not verified and "tool_event_verified" in content_text:
            verified = True
        if not verified and str(item.get("status") or "").lower() == "completed" and summary:
            if self._dynamic_tool_evidence_values(summary, ("local_path", "asset_id", "record_id", "url", "path", "screenshot_path")):
                verified = True
        evidence: dict[str, Any] = {
            "tool": tool,
            "server": self._dynamic_tool_server(tool),
            "status": item.get("status") or ("completed" if verified else "unknown"),
            "verified": verified,
            "label": "tool-event verified" if verified else "tool-event unverified",
            "summary": self._dynamic_tool_evidence_lines(tool, summary, content_text),
        }
        paths = self._dynamic_tool_evidence_values(summary, ("path", "screenshot_path", "manifest_path", "local_path"))
        urls = self._dynamic_tool_evidence_values(summary, ("url", "navigation_url"))
        if paths:
            evidence["paths"] = paths[:6]
        if urls:
            evidence["urls"] = urls[:6]
        return evidence

    def _command_execution_verified_evidence(self, item: dict[str, Any]) -> dict[str, Any] | None:
        command = str(item.get("command") or "").strip()
        if not command:
            return None
        status = str(item.get("status") or "unknown")
        exit_code = item.get("exitCode")
        completed = status in {"completed", "failed", "cancelled"} or exit_code is not None
        summary = [f"command: {command[:220]}"]
        if exit_code is not None:
            summary.append(f"exit code: {exit_code}")
        output = str(item.get("aggregatedOutput") or item.get("output") or "").strip()
        if output:
            summary.append("output: " + " ".join(output.split())[:220])
        return {
            "tool": "shell_command",
            "server": "codex_builtin",
            "status": status,
            "verified": completed,
            "label": "command-event verified" if completed else "command-event pending",
            "summary": summary[:6],
        }

    def _dynamic_tool_content_text(self, item: dict[str, Any]) -> str:
        texts: list[str] = []
        for content in item.get("contentItems") or []:
            if isinstance(content, dict) and content.get("type") in {"inputText", "text"}:
                texts.append(str(content.get("text") or ""))
        return "\n".join(texts).strip()

    def _dynamic_tool_summary_from_item(self, item: dict[str, Any]) -> dict[str, Any]:
        content_text = self._dynamic_tool_content_text(item)
        if not content_text:
            return {}
        match = re.search(r"\{.*\}\s*$", content_text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except Exception:  # noqa: BLE001
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _dynamic_tool_evidence_lines(self, tool: str, summary: dict[str, Any], fallback_text: str) -> list[str]:
        lines: list[str] = []
        if tool in BROWSER_SMOKE_TOOL_ALIASES:
            status = summary.get("status")
            label = summary.get("label")
            if status or label:
                lines.append(f"browser smoke {label or ''} {status or ''}".strip())
            if summary.get("screenshot_path"):
                lines.append(f"screenshot: {summary.get('screenshot_path')}")
            errors = summary.get("console_errors")
            if isinstance(errors, list):
                lines.append(f"console errors: {len(errors)}")
            request_failures = summary.get("request_failures")
            if isinstance(request_failures, list):
                lines.append(f"request failures: {len(request_failures)}")
        elif _is_astrabridge_web_tool(tool):
            if summary.get("record_id"):
                lines.append(f"research record: {summary.get('record_id')}")
            result = summary.get("result")
            sources = result.get("sources") if isinstance(result, dict) else summary.get("sources")
            if isinstance(sources, list):
                lines.append(f"sources: {len(sources)}")
                for source in sources[:2]:
                    if isinstance(source, dict) and source.get("url"):
                        lines.append(str(source.get("url")))
        elif tool.startswith("yunwu_image_"):
            if summary.get("actual_n") is not None or summary.get("requested_n") is not None:
                lines.append(f"images: {summary.get('actual_n', '?')}/{summary.get('requested_n', '?')}")
            for asset_id in self._dynamic_tool_evidence_values(summary, ("asset_id",)):
                lines.append(f"asset: {asset_id}")
            if summary.get("has_alpha") is not None:
                lines.append(f"alpha: {summary.get('has_alpha')}")
        if not lines and fallback_text:
            compact = " ".join(fallback_text.split())
            lines.append(compact[:240])
        return lines[:6]

    def _dynamic_tool_evidence_values(self, value: Any, keys: tuple[str, ...]) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key in keys:
                current = value.get(key)
                if isinstance(current, str) and current:
                    found.append(current)
            for current in value.values():
                found.extend(self._dynamic_tool_evidence_values(current, keys))
        elif isinstance(value, list):
            for item in value:
                found.extend(self._dynamic_tool_evidence_values(item, keys))
        deduped: list[str] = []
        for item in found:
            if item not in deduped:
                deduped.append(item)
        return deduped

    def _decorate_turn_completion_quality(self, thread: dict[str, Any]) -> dict[str, Any]:
        turns = list(thread.get("turns") or [])
        if not turns:
            return thread
        decorated_turns: list[dict[str, Any]] = []
        changed = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            quality = self._turn_completion_quality(turn)
            if quality:
                decorated_turns.append({**turn, "completionQuality": quality})
                changed = True
            else:
                decorated_turns.append(turn)
        return {**thread, "turns": decorated_turns} if changed else thread

    def _turn_completion_quality(self, turn: dict[str, Any]) -> dict[str, Any] | None:
        if str(turn.get("status") or "") != "completed":
            return None
        items = [item for item in list(turn.get("items") or []) if isinstance(item, dict)]
        tool_count = sum(1 for item in items if item.get("type") in {"dynamicToolCall", "commandExecution"})
        if tool_count == 0:
            return None
        agent_texts = [str(item.get("text") or "").strip() for item in items if item.get("type") == "agentMessage"]
        nonempty = [text for text in agent_texts if text]
        max_chars = max((len(text) for text in nonempty), default=0)
        final_text = nonempty[-1] if nonempty else ""
        if max_chars >= 240:
            return None
        weak_markers = (
            "let me",
            "now i",
            "now let",
            "i will",
            "i'll",
            "produce the",
            "start by",
        )
        looks_like_progress_note = any(marker in final_text.lower() for marker in weak_markers)
        if not looks_like_progress_note and max_chars >= 120:
            return None
        return {
            "status": "suspect",
            "reason": "completed_with_short_or_progress_only_final_after_verified_activity",
            "tool_item_count": tool_count,
            "agent_message_count": len(nonempty),
            "max_agent_chars": max_chars,
            "final_preview": final_text[:240],
            "recommended_action": "continue_or_retry_final_answer",
        }

    def _decorate_turn_execution_policy(self, thread: dict[str, Any]) -> dict[str, Any]:
        turns = list(thread.get("turns") or [])
        thread_id = str(thread.get("id") or "")
        if not turns or not thread_id:
            return thread
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        policy_events = [
            event
            for event in events
            if event.get("type") == "turn_execution_policy_started" and str(event.get("thread_id") or "") == thread_id
        ]
        if not policy_events:
            return thread
        decorated_turns: list[dict[str, Any]] = []
        changed = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            turn_id = str(turn.get("id") or "")
            matching = [event for event in policy_events if str(event.get("turn_id") or "") == turn_id]
            if not matching:
                decorated_turns.append(turn)
                continue
            policy_event = matching[-1]
            policy = str(policy_event.get("policy") or "standard")
            items = [item for item in list(turn.get("items") or []) if isinstance(item, dict)]
            if policy == NO_TOOLS_EXECUTION_POLICY:
                prohibited = [
                    str(item.get("type") or "unknown")
                    for item in items
                    if any(
                        marker in re.sub(r"[^a-z]", "", str(item.get("type") or "").lower())
                        for marker in ("commandexecution", "filechange", "toolcall", "websearch", "applypatch")
                    )
                ]
            else:
                prohibited = [
                    str(item.get("type") or "unknown")
                    for item in items
                    if str(item.get("type") or "") in {"commandExecution", "fileChange"}
                ]
            recorded_violation = self._turn_execution_policy_violation(thread_id=thread_id, turn_id=turn_id)
            status = "enforcing"
            if self._normalize_terminal_turn_status(turn.get("status")) in TERMINAL_TURN_STATUSES:
                status = "violated" if prohibited or recorded_violation is not None else "passed"
            detail: dict[str, Any] = {
                "policy": policy,
                "status": status,
                "enforcement": policy_event.get("enforcement"),
                "prohibited_tool_types": prohibited,
                "blocked_tool_calls": recorded_violation,
            }
            if status == "violated":
                detail.update(
                    {
                        "reason": "prohibited_execution_observed_in_turn_trace",
                        "recommended_action": (
                            "retry_in_a_fresh_no_tools_graph_lane"
                            if policy == NO_TOOLS_EXECUTION_POLICY
                            else "review_changes_and_retry_in_a_fresh_patch_only_turn"
                        ),
                        "compliant_success": False,
                    }
                )
            elif status == "passed":
                detail["compliant_success"] = True
            decorated_turns.append({**turn, "executionPolicy": detail})
            changed = True
        return {**thread, "turns": decorated_turns} if changed else thread

    def _thread_cache_name(self, thread_id: str) -> str | None:
        if not thread_id:
            return None
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        name = entry.get("name")
        return _display_thread_name(name, entry.get("provider_id")) if name else None

    def _sync_thread_settings_from_notification(self, payload: dict[str, Any]) -> None:
        thread_id = str(payload.get("threadId") or "")
        thread_settings = dict(payload.get("threadSettings") or {})
        if not thread_id:
            return
        self._cache_thread_entry(
            thread_id,
            {
                "model": thread_settings.get("model"),
                "reasoning_effort": thread_settings.get("effort"),
                "collaboration_mode": (thread_settings.get("collaborationMode") or {}).get("mode")
                if isinstance(thread_settings.get("collaborationMode"), dict)
                else None,
            },
        )

    def _record_event(self, event: dict[str, Any]) -> None:
        record = enrich_runtime_event(redact_sensitive({"index": None, "timestamp": now_iso(), **event}))
        with self._lock:
            record["index"] = len(self._events)
            self._events.append(record)
        try:
            shell_root = self._projects.require_shell_state_root()
            append_jsonl(shell_root / "runtime_events.jsonl", record)
        except Exception:
            pass

    def _event_for_response(self, event: dict[str, Any]) -> dict[str, Any]:
        return self._summarize_value(event, 0)

    def _summarize_value(self, value: Any, depth: int) -> Any:
        if depth > EVENT_RESPONSE_DEPTH_LIMIT:
            return {"summary": "Nested event details truncated for UI response."}
        if isinstance(value, str):
            if len(value) <= EVENT_RESPONSE_STRING_LIMIT:
                return value
            omitted = len(value) - EVENT_RESPONSE_STRING_LIMIT
            return value[:EVENT_RESPONSE_STRING_LIMIT] + f"\n...[truncated {omitted} chars]"
        if isinstance(value, list):
            items = [self._summarize_value(item, depth + 1) for item in value[:EVENT_RESPONSE_LIST_LIMIT]]
            if len(value) > EVENT_RESPONSE_LIST_LIMIT:
                items.append({"summary": f"{len(value) - EVENT_RESPONSE_LIST_LIMIT} additional items truncated."})
            return items
        if isinstance(value, dict):
            return {key: self._summarize_value(item, depth + 1) for key, item in value.items()}
        return value


class _RuntimeRequestClient:
    """Stable request facade for one prepared runtime.

    `start_turn` can perform several app-server calls before the actual
    `turn/start`: read source thread, fork/start a provider thread, then start
    the turn. UI polling may concurrently request another provider profile. This
    facade keeps the whole handoff on the intended runtime and retries one
    transport-level app-server disconnect without recording large request
    payloads or secrets.
    """

    def __init__(self, runtime: RuntimeService, runtime_status: dict[str, Any]) -> None:
        self._runtime = runtime
        self._runtime_status = runtime_status
        self._client = runtime._ensure_client(runtime_status)
        self._lease = None
        try:
            signature = runtime._runtime_config.runtime_signature(runtime_status)
            if runtime._runtime_client_pool.has_lane(signature):
                self._lease = runtime._runtime_client_pool.acquire(
                    signature,
                    lambda: self._client,
                )
                self._client = self._lease.client
        except Exception:
            # Compatibility doubles may not implement the production pool
            # surface. They continue to use the raw client facade.
            self._lease = None

    def is_running(self) -> bool:
        return self._client.is_running()

    def request(self, method: str, params: Any | None = None, timeout: float = 120.0) -> Any:
        try:
            return self._client.request(method, params, timeout=timeout)
        except RuntimeError as exc:
            if not self._runtime._is_app_server_transport_error(exc):
                raise
            self._runtime._record_event(
                {
                    "type": "runtime_request_transport_retry",
                    "method": method,
                    "thread_id": str(params.get("threadId") or "") if isinstance(params, dict) else None,
                    "error": str(exc),
                    "runtime": self._runtime_status,
                }
            )
            self._release_lease()
            self._runtime._close_client(f"{method}_transport_retry")
            self._client = self._runtime._ensure_client(self._runtime_status)
            try:
                signature = self._runtime._runtime_config.runtime_signature(self._runtime_status)
                if self._runtime._runtime_client_pool.has_lane(signature):
                    self._lease = self._runtime._runtime_client_pool.acquire(signature, lambda: self._client)
                    self._client = self._lease.client
            except Exception:
                self._lease = None
            return self._client.request(method, params, timeout=timeout)

    def close(self) -> None:
        self._release_lease()

    def _release_lease(self) -> None:
        lease = self._lease
        self._lease = None
        if lease is not None:
            lease.release()

    def __del__(self) -> None:
        try:
            self._release_lease()
        except Exception:
            pass


class _ExistingProbeClient:
    def __init__(self, client: AppServerClient) -> None:
        self._client = client

    def start(self) -> None:
        return None

    def close(self) -> None:
        return None

    def request(self, method: str, params: Any | None = None, timeout: float = 120.0) -> Any:
        return self._client.request(method, params, timeout=timeout)


