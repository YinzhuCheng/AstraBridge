from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .coding_kernel import task_refs_from_coding_events
from .common import WORKSPACE_STATE_DIRNAME, new_id, now_iso, read_json, write_json
from .durable_run_store import DurableRunEventStore
from .agent_orchestration_contract import (
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    lift_task_graph_to_agent_orchestration_graph,
    lower_agent_orchestration_graph_to_task_graph,
    validate_agent_orchestration_graph,
)
from .agent_orchestration_checks import (
    build_known_model_capabilities,
    diff_agent_orchestration_graphs,
    render_agent_orchestration_report_markdown,
)
from .agent_orchestration_compiler import compile_agent_orchestration_graph
from .agent_orchestration_file_format import (
    parse_agent_orchestration_graph_text,
    serialize_agent_orchestration_graph,
    write_agent_orchestration_graph_file,
)
from .comfyui_workflow_adapter import (
    COMFYUI_WORKFLOW_SOURCE_FORMAT,
    export_comfyui_workflow,
    import_comfyui_workflow,
    looks_like_comfyui_workflow,
)
from .langgraph_stategraph_adapter import (
    LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
    export_langgraph_stategraph_manifest,
    import_langgraph_stategraph_manifest,
    looks_like_langgraph_stategraph_manifest,
)
from .model_catalog.catalog import provider_model_records
from .node_type_registry import (
    OPAQUE_DISABLED_NODE_TYPE_ID,
    journaled_compiled_plan_executor_capability_report,
    node_type_registry_snapshot,
)
from .protocol.compatibility import adapt_legacy_artifact_path
from .protocol.generated.v1 import (
    ProtocolValidationError,
    SCHEMA_VERSION as PROTOCOL_SCHEMA_VERSION,
    validate_protocol_payload,
)
from .providers.runtime_transition import summarize_transition
from .providers.tooling import assess_default_route_verification
from .security import DESKTOP_KEY_PATH_RE, SECRET_RE, SecurityError, redact_sensitive, resolve_under
from .task_graph_contract import (
    ARTIFACT_KINDS,
    GRAPH_TEMPLATE_IDS,
    TASK_GRAPH_SCHEMA_VERSION,
    load_task_graph_fixture,
    validate_graph_definition,
    validate_task_graph_run,
)
from .task_graph_mutation_service import TaskGraphMutationService
from .task_graph_run_ref_service import TaskGraphRunRefService
from .usage_signal import normalize_usage_signal, usage_not_available


TASK_STATE_SCHEMA_VERSION = "astrabridge-task-state-v1"
TASK_GRAPH_DRY_RUN_SCHEMA_VERSION = "astrabridge-task-graph-dry-run-v1"
DEFAULT_HANDOFF_POLICY = "multi_provider_handoff"
GRAPH_DEFINITION_LIMIT = 20
GRAPH_RUN_REF_LIMIT = 40
GRAPH_SNAPSHOT_REF_LIMIT = 80
AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT = "agent_orchestration_graph"
GRAPH_DOCUMENT_SCHEMA_VERSION = "astrabridge-graph-document-v3"
GRAPH_DOCUMENT_LEGACY_SCHEMA_V2 = "astrabridge-graph-document-v2"
GRAPH_DOCUMENT_MIGRATION_VERSIONS = (
    "legacy_task_graph_definition",
    GRAPH_DOCUMENT_LEGACY_SCHEMA_V2,
    GRAPH_DOCUMENT_SCHEMA_VERSION,
)
GRAPH_SOURCE_OWNERSHIP_SCHEMA_VERSION = "astrabridge-graph-source-ownership-v1"
GRAPH_SOURCE_OWNERSHIP_SOURCE_OWNED = "source_owned"
GRAPH_SOURCE_OWNERSHIP_DETACHED = "detached_gui_edit"
GRAPH_SOURCE_OWNERSHIP_WRITABLE_SOURCE = "source_owned_canonical_file"
GRAPH_SOURCE_OWNERSHIP_DETACHED_WRITABLE_SOURCE = "detached_gui_graph"
_GRAPH_CONFLICT_DELETE = object()
GRAPH_TEMPLATE_SUMMARIES = {
    "supervisor_worker_synthesizer": "Supervisor plans, one worker executes, one synthesizer returns the bounded result.",
    "fanout_fanin_research": "One planner fans out bounded research branches and one synthesizer merges their artifacts.",
    "code_fix_test_review": "Planner, code worker, test validator, and review node for code-change workflows.",
    "provider_update_smoke_gate": "Metadata discovery, smoke validation, and manual promotion gate for provider updates.",
    "document_extract_analyze_report": "Extractor, analyst, and report writer for bounded document workflows.",
    "multimodal_capability_adapter": "Probe supported input/output modes, adapt the message contract, and verify multimodal fallback behavior.",
    "custom_blank_graph": "Minimal starter graph with one neutral entry node for custom orchestration authoring.",
}


class GraphRevisionConflictError(RuntimeError):
    def __init__(self, message: str, *, payload: dict[str, Any]) -> None:
        super().__init__(message)
        self.payload = dict(payload)

    def response_payload(self) -> dict[str, Any]:
        return {"ok": False, **dict(self.payload)}


class GraphSourceOwnershipError(RuntimeError):
    def __init__(self, message: str, *, payload: dict[str, Any]) -> None:
        super().__init__(message)
        self.payload = dict(payload)

    def response_payload(self) -> dict[str, Any]:
        return {"ok": False, **dict(self.payload)}


GRAPH_TEMPLATE_PRODUCT_METADATA = {
    "supervisor_worker_synthesizer": {
        "recommended_provider_ids": ["qwen", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "kimi-k2.6"],
        "artifact_expectations": ["Structured plan", "Bounded worker report", "Final run summary"],
        "validation_hints": ["Check the worker route before dry-run.", "Keep the worker-to-synth handoff artifact-first."],
        "constraints": ["Single worker lane.", "No silent high-risk writes."],
    },
    "fanout_fanin_research": {
        "recommended_provider_ids": ["qwen", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "kimi-k2.6"],
        "artifact_expectations": ["Branch research notes", "Merge summary", "Attributed branch outputs"],
        "validation_hints": ["Validate every fan-out edge policy.", "Keep branch outputs bounded before merge."],
        "constraints": ["Parallel branch lanes.", "Synthesizer consumes declared artifacts only."],
    },
    "code_fix_test_review": {
        "recommended_provider_ids": ["qwen", "deepseek", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "deepseek-v4-pro", "kimi-k2.6"],
        "artifact_expectations": ["Fix plan", "Code diff", "Test report", "Review report"],
        "validation_hints": ["Pin the code worker model.", "Keep code-change, test, and review as separate nodes."],
        "constraints": ["Code changes stay bounded.", "Review evidence must survive reload."],
    },
    "provider_update_smoke_gate": {
        "recommended_provider_ids": ["qwen", "glm"],
        "recommended_model_ids": ["qwen3.7-plus", "glm-5.2"],
        "artifact_expectations": ["Provider diff bundle", "Smoke matrix", "Promotion decision record"],
        "validation_hints": ["Dry-run should surface blocked provider cases.", "Promotion remains gated until review."],
        "constraints": ["Human approval before promotion.", "No silent external writeback."],
    },
    "document_extract_analyze_report": {
        "recommended_provider_ids": ["qwen", "glm"],
        "recommended_model_ids": ["qwen3.7-plus", "glm-5.2"],
        "artifact_expectations": ["Document extract", "Structured analysis", "Final report"],
        "validation_hints": ["Check extract node output schema first.", "Preserve artifact handoff into the report node."],
        "constraints": ["Document path stays bounded.", "Report is generated from declared extract artifacts only."],
    },
    "multimodal_capability_adapter": {
        "recommended_provider_ids": ["qwen", "glm", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "glm-5.2", "kimi-k2.6"],
        "artifact_expectations": ["Capability probe", "Adapted multimodal contract", "Fallback validation report"],
        "validation_hints": ["Confirm the target model actually supports the intended input modes.", "Keep fallback behavior explicit instead of silent degradation."],
        "constraints": ["Bound multimodal payload sizes.", "Declare fallback paths before live provider execution."],
    },
    "custom_blank_graph": {
        "recommended_provider_ids": ["qwen", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "kimi-k2.6"],
        "artifact_expectations": ["Starter graph manifest"],
        "validation_hints": ["Rename the seed node before dry-run.", "Add at least one downstream worker before fixture execution."],
        "constraints": ["Treat this as an authoring scaffold, not a finished workflow."],
    },
}
AUTO_INJECTED_CONTEXT_NAME_MARKERS = (
    "--- astrabridge project context pack",
    "astrabridge project context pack",
    "--- astrabridge asset context pack",
    "astrabridge asset context pack",
    "freshness rule:",
)
SMOKE_TASK_PREFIX_PATTERN = re.compile(r"^Step\s+\d+\s+(?:source|target)\s+for\s+", re.IGNORECASE)


def _compact_text(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _promote_dry_run_status(current: str, next_status: str) -> str:
    rank = {"pass": 0, "warning": 1, "blocked": 2}
    return next_status if rank.get(next_status, 0) > rank.get(current, 0) else current


def _dry_run_status_counts(*, node_results: list[dict[str, Any]], edge_results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warning": 0, "blocked": 0}
    for item in [*node_results, *edge_results]:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip()
        if status in counts:
            counts[status] = int(counts[status] or 0) + 1
    return counts


def _sanitize_graph_machine_result(value: Any) -> Any:
    private_keys = {
        "raw_history",
        "history_transcript",
        "reasoning_content",
        "private_memory",
        "conversation_history",
        "full_history",
        "scratchpad",
    }
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            clean_key = str(key or "").strip()
            if clean_key in private_keys:
                continue
            sanitized[clean_key] = _sanitize_graph_machine_result(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_graph_machine_result(item) for item in value]
    return value


class GraphContractValidationError(ValueError):
    """Raised when live task-graph contracts fail closed."""


class TaskService:
    """User-facing task state over internal provider-specific Codex threads.

    A task is what the user perceives as one conversation or objective. Each
    task may use multiple internal Codex threads, one per provider/model route.
    Provider switching should therefore preserve the task and only change the
    active provider thread.
    """

    def __init__(self, project_service) -> None:
        self._projects = project_service
        self._durable_store: DurableRunEventStore | None = None
        self._durable_store_workspace: Path | None = None
        self._graph_mutation = TaskGraphMutationService(self)
        self._graph_run_refs = TaskGraphRunRefService(self)

    def durable_run_store(self) -> DurableRunEventStore:
        """Return the workspace-local durable run store for this service.

        The store is initialized lazily so ordinary task-list reads keep their
        existing lightweight path.  A workspace switch closes the old logical
        owner before opening the new store; SQLite connections themselves are
        short-lived and never cross request lifetimes.
        """

        workspace = Path(self._projects.require_workspace_root()).expanduser().resolve()
        if self._durable_store is not None and self._durable_store_workspace == workspace:
            return self._durable_store
        if self._durable_store is not None:
            self._durable_store.close()
        store = DurableRunEventStore(workspace)
        store.initialize()
        store.migrate_legacy_state()
        self._durable_store = store
        self._durable_store_workspace = workspace
        return store

    def snapshot(self) -> dict[str, Any]:
        state = self._state()
        current = self._current_task_response_view(state=state)
        return {
            "schema_version": TASK_STATE_SCHEMA_VERSION,
            # This endpoint is polled by the shell. Full graph runs can contain
            # large artifact payloads, so callers load their detail through the
            # dedicated graph/run endpoints instead of repeatedly transferring it.
            "current_task": current,
            "tasks": [
                self.task_list_item(task)
                for task in list(state.get("tasks") or [])
                if isinstance(task, dict)
            ],
            "updated_at": state.get("updated_at"),
        }

    def task_list_item(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return navigation metadata without duplicating task or graph payloads."""
        graph_summary = self._graph_activity_summary(task)
        provider_threads = [item for item in list(task.get("provider_threads") or []) if isinstance(item, dict)]
        return {
            "schema_version": str(task.get("schema_version") or TASK_STATE_SCHEMA_VERSION),
            "task_id": str(task.get("task_id") or "").strip(),
            "project_id": str(task.get("project_id") or "").strip(),
            "title": _display_task_title(task.get("title")) or "New task",
            "status": str(task.get("status") or "").strip(),
            "created_at": str(task.get("created_at") or "").strip(),
            "updated_at": str(task.get("updated_at") or "").strip(),
            "active_provider_thread_id": str(task.get("active_provider_thread_id") or "").strip() or None,
            "lane_state": {
                "lane_count": len(provider_threads),
                "handoff_count": len([item for item in list(task.get("handoff_events") or []) if isinstance(item, dict)]),
            },
            "graph_activity_summary": graph_summary,
        }

    def task_view(
        self,
        task: dict[str, Any] | None = None,
        *,
        compact_graph_runs: bool = False,
        compact_graph_details: bool = False,
    ) -> dict[str, Any] | None:
        current = dict(task) if isinstance(task, dict) else self.current_task()
        if not isinstance(current, dict):
            return None
        current["title"] = _display_task_title(current.get("title")) or "New task"
        current["lane_state"] = self.lane_state(task=current)
        current["graph_activity_summary"] = self._graph_activity_summary(current)
        if compact_graph_runs:
            current["graph_run_refs"] = self._task_response_graph_run_refs(current.get("graph_run_refs"))
        if compact_graph_details:
            current["graph_definitions"] = self._task_response_graph_definition_refs(current.get("graph_definitions"))
            current["graph_snapshot_refs"] = self._task_response_graph_snapshot_refs(current.get("graph_snapshot_refs"))
            current["handoff_events"] = [
                self.compact_handoff_event(item)
                for item in list(current.get("handoff_events") or [])
                if isinstance(item, dict)
            ][-12:]
        return current

    def _task_response_graph_run_refs(self, value: Any) -> list[dict[str, Any]]:
        return self._graph_run_refs.task_response_graph_run_refs(value, limit=12)

    def _task_response_graph_definition_refs(self, value: Any) -> list[dict[str, Any]]:
        compacted: list[dict[str, Any]] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            graph_policy = dict(item.get("graph_policy") or {})
            revision = self._graph_revision_payload(item)
            compacted.append(
                {
                    "graph_id": str(item.get("graph_id") or "").strip(),
                    "task_id": str(item.get("task_id") or "").strip(),
                    "title": str(item.get("title") or "").strip(),
                    "template_id": str(item.get("template_id") or "").strip(),
                    "status": str(item.get("status") or "").strip(),
                    "state_version": int(item.get("state_version") or 0),
                    "node_count": len(list(item.get("nodes") or [])),
                    "edge_count": len(list(item.get("edges") or [])),
                    "graph_policy": {"entry_node_ids": list(graph_policy.get("entry_node_ids") or [])[:12]},
                    "created_at": str(item.get("created_at") or "").strip(),
                    "updated_at": str(item.get("updated_at") or "").strip(),
                    "graph_revision": revision,
                }
            )
        return compacted[:20]

    def _task_response_graph_snapshot_refs(self, value: Any) -> list[dict[str, Any]]:
        compacted: list[dict[str, Any]] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            compacted.append(
                {
                    "snapshot_id": str(item.get("snapshot_id") or "").strip(),
                    "graph_id": str(item.get("graph_id") or "").strip(),
                    "task_id": str(item.get("task_id") or "").strip(),
                    "run_id": str(item.get("run_id") or "").strip(),
                    "status": str(item.get("status") or "").strip(),
                    "label": str(item.get("label") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                    "created_at": str(item.get("created_at") or "").strip(),
                    "updated_at": str(item.get("updated_at") or "").strip(),
                }
            )
        return compacted[:24]

    def ensure_default_task(self, *, thread_id: str | None = None, title: str | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        project = self._project()
        state = self._state()
        tasks = list(state.get("tasks") or [])
        current_task_id = self._resolved_current_task_id(state=state, project=project)
        task = self._find_task(tasks, current_task_id)
        if not task:
            task = self._new_task(title or project.get("name") or "New task")
            tasks.insert(0, task)
            current_task_id = str(task["task_id"])
        if thread_id:
            task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role="provider", make_active=True)
        updated_tasks = self._replace_task(tasks, task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = current_task_id
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def create_task(self, title: str | None = None, *, thread_id: str | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self._new_task(title or "New task")
        if thread_id:
            task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role="provider", make_active=True)
        state = self._state()
        tasks = [item for item in list(state.get("tasks") or []) if item.get("task_id") != task.get("task_id")]
        tasks.insert(0, task)
        tasks = self._enforce_task_thread_ownership(tasks[:100], owner_task=task)
        task = self._find_task(tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def switch_task(self, task_id: str) -> dict[str, Any]:
        state = self._state()
        tasks = list(state.get("tasks") or [])
        task = self._find_task(tasks, task_id)
        if not task:
            raise ValueError("Task not found.")
        task["updated_at"] = now_iso()
        state["tasks"] = self._replace_task(tasks, task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return self._current_task_response_view(state=state) or self.task_view(task, compact_graph_runs=True, compact_graph_details=True) or task

    def update_current_task_title(self, title: str) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        clean_title = str(title or "").strip()
        if not clean_title:
            raise ValueError("Task title cannot be empty.")
        redacted_title = str(redact_sensitive(clean_title)).strip()
        if SECRET_RE.search(redacted_title):
            raise SecurityError("Secret-like content is not allowed in task titles.")
        task["title"] = redacted_title[:160]
        task["updated_at"] = now_iso()
        self._save_task(task)
        return task

    def current_task(self) -> dict[str, Any] | None:
        project = self._project()
        state = self._state()
        task_id = self._resolved_current_task_id(state=state, project=project)
        task = self._find_task(list(state.get("tasks") or []), task_id)
        if task:
            normalized_task, changed = self._normalize_task(task)
            if changed:
                state["tasks"] = self._replace_task(list(state.get("tasks") or []), normalized_task)
                state["current_task_id"] = normalized_task["task_id"]
                state["updated_at"] = now_iso()
                self._write_state(state)
                self._sync_project_current_task(normalized_task)
            elif self._project_sync_needed(normalized_task):
                self._sync_project_current_task(normalized_task)
            return normalized_task
        return None

    def _raw_current_task_from_state(self, *, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        current_state = state if isinstance(state, dict) else self._state()
        project = self._project()
        task_id = self._resolved_current_task_id(state=current_state, project=project)
        task = self._find_task(list(current_state.get("tasks") or []), task_id)
        return dict(task) if isinstance(task, dict) else None

    def _current_task_response_view(self, *, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        raw_task = self._raw_current_task_from_state(state=state)
        if raw_task:
            return self.task_view(raw_task, compact_graph_runs=True, compact_graph_details=True)
        current = self.current_task()
        if not current:
            return None
        return self.task_view(current, compact_graph_runs=True, compact_graph_details=True)

    def reconcile_after_project_reload(self, *, preferred_thread_id: str | None = None) -> dict[str, Any] | None:
        """Re-anchor task pointers after project reopen or checkpoint restore."""
        state = self._state()
        tasks = [dict(item) for item in list(state.get("tasks") or []) if isinstance(item, dict)]
        if not tasks:
            return None
        normalized_tasks: list[dict[str, Any]] = []
        changed = False
        for item in tasks:
            normalized, item_changed = self._normalize_task(item)
            normalized_tasks.append(normalized)
            changed = changed or item_changed or normalized != item
        project = self._project()
        selected = self._select_reloaded_task(
            normalized_tasks,
            current_task_id=self._resolved_current_task_id(state=state, project=project),
            preferred_thread_id=str(preferred_thread_id or project.get("current_thread_id") or "").strip(),
        )
        if not selected:
            return None
        selected_id = str(selected.get("task_id") or "").strip()
        if str(state.get("current_task_id") or "") != selected_id:
            state["current_task_id"] = selected_id
            changed = True
        if normalized_tasks != list(state.get("tasks") or []):
            state["tasks"] = normalized_tasks
            changed = True
        if changed:
            state["updated_at"] = now_iso()
            self._write_state(state)
        if self._project_sync_needed(selected):
            self._sync_project_current_task(selected)
        return selected

    def bind_thread(
        self,
        *,
        thread_id: str,
        settings: dict[str, Any] | None = None,
        role: str = "provider",
        title: str | None = None,
        make_active: bool = True,
    ) -> dict[str, Any]:
        task = self.ensure_default_task(title=title, settings=settings)
        task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role=role, make_active=make_active)
        state = self._state()
        updated_tasks = self._replace_task(list(state.get("tasks") or []), task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def bind_thread_to_task_id(
        self,
        *,
        task_id: str,
        thread_id: str,
        settings: dict[str, Any] | None = None,
        role: str = "provider",
        make_active: bool = True,
    ) -> dict[str, Any]:
        """Bind a runtime thread to the task selected before first-turn bootstrap."""
        clean_task_id = str(task_id or "").strip()
        if not clean_task_id:
            raise ValueError("task_id is required.")
        state = self._state()
        tasks = list(state.get("tasks") or [])
        task = self._find_task(tasks, clean_task_id)
        if not task:
            raise ValueError("Task not found.")
        task = self._bind_thread_to_task(
            task,
            thread_id=thread_id,
            settings=settings or {},
            role=role,
            make_active=make_active,
        )
        updated_tasks = self._replace_task(tasks, task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, clean_task_id) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = clean_task_id
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def find_provider_thread(
        self,
        *,
        profile_id: str | None,
        provider_id: str | None = None,
        model: str | None,
        effort: str | None,
    ) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        desired_profile = str(profile_id or "")
        desired_provider = str(provider_id or "").strip().lower()
        desired_model = _canonical_model_key(model)
        desired_effort = _canonical_effort_key(effort)
        matches: list[dict[str, Any]] = []
        for item in list(task.get("provider_threads") or []):
            if item.get("missing_at"):
                continue
            if not _provider_thread_entry_is_plausible(item):
                continue
            item_profile = str(item.get("profile_id") or "")
            item_provider = str(item.get("provider_id") or "").strip().lower()
            if desired_profile and item_profile != desired_profile:
                if not desired_provider or item_provider != desired_provider:
                    continue
            elif not desired_profile and desired_provider and item_provider != desired_provider:
                continue
            if desired_model and _canonical_model_key(item.get("model")) != desired_model:
                continue
            if desired_effort and _canonical_effort_key(item.get("reasoning_effort")) != desired_effort:
                continue
            matches.append(dict(item))
        if not matches:
            return None
        matches.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return matches[0]

    def active_provider_thread(self, *, include_missing_fallback: bool = False) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        active_thread_id = str(task.get("active_provider_thread_id") or "")
        provider_threads = [dict(item) for item in list(task.get("provider_threads") or [])]
        for item in provider_threads:
            if (
                str(item.get("thread_id") or "") == active_thread_id
                and not item.get("missing_at")
                and _provider_thread_entry_is_plausible(item)
            ):
                return dict(item)
        if not include_missing_fallback:
            return None
        project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
        if project_thread_id:
            for item in provider_threads:
                if str(item.get("thread_id") or "") == project_thread_id:
                    return dict(item)
        live_threads = [
            item for item in provider_threads if not item.get("missing_at") and _provider_thread_entry_is_plausible(item)
        ]
        if live_threads:
            live_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return dict(live_threads[0])
        if provider_threads:
            provider_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return dict(provider_threads[0])
        return None

    def visible_provider_thread_id(self, *, include_missing_fallback: bool = False) -> str:
        """Return the best secret-free visible provider thread hint for the current task."""
        task = self.current_task()
        if not task:
            return ""
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        if active_thread_id:
            return active_thread_id
        fallback = self.active_provider_thread(include_missing_fallback=include_missing_fallback)
        return str((fallback or {}).get("thread_id") or "").strip()

    def restore_active_provider_thread(self, thread_id: str) -> dict[str, Any] | None:
        """Restore UI focus without mutating thread metadata or missing diagnostics."""
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return self.current_task()
        state = self._state()
        tasks = [dict(item) for item in list(state.get("tasks") or []) if isinstance(item, dict)]
        task = self._find_task_for_thread(tasks, clean_thread_id)
        if not task:
            task_id = str(self._project().get("current_task_id") or state.get("current_task_id") or "")
            task = self._find_task(tasks, task_id) or self.current_task()
        if not task:
            return None
        task["active_provider_thread_id"] = clean_thread_id
        task["updated_at"] = now_iso()
        updated_tasks = self._replace_task(tasks, task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def force_visible_provider_thread(self, thread_id: str) -> dict[str, Any] | None:
        """Force the visible task/project pointers onto a known provider thread.

        This is intentionally stronger than restore_active_provider_thread() and is
        only meant for supervisor-style actions such as direct MCP tool calls,
        where we want to preserve the user's visible task continuity even if the
        source provider thread has been marked missing in the runtime.
        """
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return self.current_task()
        project = self._project()
        state = self._state()
        task_id = self._resolved_current_task_id(state=state, project=project)
        task = self._find_task(list(state.get("tasks") or []), task_id)
        if not task:
            return None
        task["active_provider_thread_id"] = clean_thread_id
        task["updated_at"] = now_iso()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def needs_provider_handoff(self, *, thread_id: str | None, profile_id: str | None, model: str | None, effort: str | None) -> bool:
        if not thread_id:
            return False
        task = self.ensure_default_task(thread_id=thread_id)
        current = None
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == str(thread_id):
                current = item
                break
        if not current:
            return False
        if not current.get("profile_id") and not current.get("model") and not current.get("reasoning_effort"):
            return False
        if profile_id and str(current.get("profile_id") or "") != str(profile_id):
            return True
        if model and _canonical_model_key(current.get("model")) != _canonical_model_key(model):
            return True
        if effort and _canonical_effort_key(current.get("reasoning_effort")) != _canonical_effort_key(effort):
            return True
        return False

    def record_provider_handoff(
        self,
        *,
        from_thread_id: str | None,
        to_thread_id: str,
        settings: dict[str, Any],
        reused_existing: bool,
        context_budget_report: dict[str, Any] | None = None,
        dropped_artifacts: int = 0,
        repaired_tool_pairs: int = 0,
        replayable_artifact_count: int = 0,
        projection_preview: str | None = None,
        warnings: list[str] | None = None,
        neutral_handoff_bundle: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.bind_thread(thread_id=to_thread_id, settings=settings, role="provider", make_active=True)
        source_settings = self._provider_thread_settings(task, from_thread_id)
        transition = summarize_transition(
            from_provider=str((source_settings or {}).get("provider_id") or "") or None,
            to_provider=str(settings.get("provider_id") or "openai"),
            to_model=str(settings.get("model") or "") or None,
            dropped_artifacts=dropped_artifacts,
            repaired_tool_pairs=repaired_tool_pairs,
            replayable_artifact_count=replayable_artifact_count,
            projection_preview=projection_preview,
            warnings=warnings,
            projection_mode="reused_provider_thread" if reused_existing else "task_context_fresh_thread",
            reasoning_effort=str(settings.get("reasoning_effort") or "") or None,
            context_budget_report=context_budget_report,
        )
        event = {
            "event_id": new_id("handoff"),
            "type": "provider_handoff",
            "handoff_policy": DEFAULT_HANDOFF_POLICY,
            "from_thread_id": from_thread_id,
            "from_profile_id": (source_settings or {}).get("profile_id"),
            "from_provider_id": (source_settings or {}).get("provider_id"),
            "from_model": _display_model_id((source_settings or {}).get("model")),
            "from_reasoning_effort": _display_effort(
                (source_settings or {}).get("reasoning_effort"),
                (source_settings or {}).get("provider_id"),
            ),
            "from_permission_mode": (source_settings or {}).get("permission_mode"),
            "to_thread_id": to_thread_id,
            "profile_id": settings.get("profile_id"),
            "provider_id": settings.get("provider_id"),
            "model": settings.get("model"),
            "reasoning_effort": settings.get("reasoning_effort"),
            "permission_mode": settings.get("permission_mode"),
            "reused_existing": reused_existing,
            "transition_summary": transition.to_dict(),
            "neutral_handoff_bundle": (
                {
                    "schema_version": str(dict(neutral_handoff_bundle).get("schema_version") or "").strip(),
                    "path": str(dict(neutral_handoff_bundle).get("path") or "").strip(),
                    "bundle_digest": str(dict(neutral_handoff_bundle).get("bundle_digest") or "").strip(),
                    "projection_digest": str(dict(neutral_handoff_bundle).get("projection_digest") or "").strip(),
                    "lineage_digest": str(dict(neutral_handoff_bundle).get("lineage_digest") or "").strip(),
                    "source_thread_id": str(dict(neutral_handoff_bundle).get("source_thread_id") or "").strip() or None,
                    "target_thread_id": str(dict(neutral_handoff_bundle).get("target_thread_id") or "").strip() or None,
                    "source_provider_id": str(dict(neutral_handoff_bundle).get("source_provider_id") or "").strip() or None,
                    "source_model_id": str(dict(neutral_handoff_bundle).get("source_model_id") or "").strip() or None,
                    "target_provider_id": str(dict(neutral_handoff_bundle).get("target_provider_id") or "").strip() or None,
                    "target_model_id": str(dict(neutral_handoff_bundle).get("target_model_id") or "").strip() or None,
                    "projection_mode": str(dict(neutral_handoff_bundle).get("projection_mode") or "").strip() or None,
                    "provider_private_state_removed": bool(dict(neutral_handoff_bundle).get("provider_private_state_removed")),
                    "dropped_artifacts": int(dict(neutral_handoff_bundle).get("dropped_artifacts") or 0),
                    "repaired_tool_pairs": int(dict(neutral_handoff_bundle).get("repaired_tool_pairs") or 0),
                    "replayable_artifact_count": int(dict(neutral_handoff_bundle).get("replayable_artifact_count") or 0),
                    "warning_count": int(dict(neutral_handoff_bundle).get("warning_count") or 0),
                }
                if isinstance(neutral_handoff_bundle, dict) and str(dict(neutral_handoff_bundle).get("path") or "").strip()
                else None
            ),
            "created_at": now_iso(),
        }
        handoff_events = list(task.get("handoff_events") or [])
        handoff_events.append(event)
        task["handoff_events"] = handoff_events[-80:]
        task["updated_at"] = now_iso()
        state = self._state()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return event

    def compact_handoff_event(self, event: dict[str, Any]) -> dict[str, Any]:
        transition = dict(event.get("transition_summary") or {})
        neutral_handoff_bundle = dict(event.get("neutral_handoff_bundle") or {})
        warnings = [str(item).strip() for item in list(transition.get("warnings") or []) if str(item or "").strip()]
        return {
            "event_id": str(event.get("event_id") or ""),
            "type": str(event.get("type") or ""),
            "handoff_policy": str(event.get("handoff_policy") or ""),
            "from_thread_id": str(event.get("from_thread_id") or ""),
            "from_profile_id": str(event.get("from_profile_id") or ""),
            "from_provider_id": str(event.get("from_provider_id") or ""),
            "from_model": str(event.get("from_model") or ""),
            "from_reasoning_effort": str(event.get("from_reasoning_effort") or ""),
            "from_permission_mode": str(event.get("from_permission_mode") or ""),
            "to_thread_id": str(event.get("to_thread_id") or ""),
            "profile_id": str(event.get("profile_id") or ""),
            "provider_id": str(event.get("provider_id") or ""),
            "model": str(event.get("model") or ""),
            "reasoning_effort": str(event.get("reasoning_effort") or ""),
            "permission_mode": str(event.get("permission_mode") or ""),
            "reused_existing": bool(event.get("reused_existing")),
            "created_at": str(event.get("created_at") or ""),
            "transition_summary": {
                "from_provider": str(transition.get("from_provider") or ""),
                "to_provider": str(transition.get("to_provider") or ""),
                "to_model": str(transition.get("to_model") or ""),
                "projection_mode": str(transition.get("projection_mode") or ""),
                "dropped_artifacts": int(transition.get("dropped_artifacts") or 0),
                "repaired_tool_pairs": int(transition.get("repaired_tool_pairs") or 0),
                "replayable_artifact_count": int(transition.get("replayable_artifact_count") or 0),
                "projection_preview": str(transition.get("projection_preview") or ""),
                "warnings": warnings,
                "warning_count": len(warnings),
            },
            "neutral_handoff_bundle": (
                {
                    "path": str(neutral_handoff_bundle.get("path") or ""),
                    "bundle_digest": str(neutral_handoff_bundle.get("bundle_digest") or ""),
                    "projection_digest": str(neutral_handoff_bundle.get("projection_digest") or ""),
                    "lineage_digest": str(neutral_handoff_bundle.get("lineage_digest") or ""),
                    "source_thread_id": str(neutral_handoff_bundle.get("source_thread_id") or ""),
                    "target_thread_id": str(neutral_handoff_bundle.get("target_thread_id") or ""),
                    "source_provider_id": str(neutral_handoff_bundle.get("source_provider_id") or ""),
                    "source_model_id": str(neutral_handoff_bundle.get("source_model_id") or ""),
                    "target_provider_id": str(neutral_handoff_bundle.get("target_provider_id") or ""),
                    "target_model_id": str(neutral_handoff_bundle.get("target_model_id") or ""),
                    "projection_mode": str(neutral_handoff_bundle.get("projection_mode") or ""),
                    "provider_private_state_removed": bool(neutral_handoff_bundle.get("provider_private_state_removed")),
                    "dropped_artifacts": int(neutral_handoff_bundle.get("dropped_artifacts") or 0),
                    "repaired_tool_pairs": int(neutral_handoff_bundle.get("repaired_tool_pairs") or 0),
                    "replayable_artifact_count": int(neutral_handoff_bundle.get("replayable_artifact_count") or 0),
                    "warning_count": int(neutral_handoff_bundle.get("warning_count") or 0),
                }
                if str(neutral_handoff_bundle.get("path") or "").strip()
                else None
            ),
        }

    def lane_state(self, task: dict[str, Any] | None = None) -> dict[str, Any]:
        current = dict(task) if isinstance(task, dict) else self.current_task()
        if not isinstance(current, dict):
            return {
                "lane_count": 0,
                "handoff_count": 0,
                "active_lane": None,
                "previous_lane": None,
                "latest_handoff": None,
            }
        provider_threads = [dict(item) for item in list(current.get("provider_threads") or []) if isinstance(item, dict)]
        by_thread_id = {
            str(item.get("thread_id") or "").strip(): item
            for item in provider_threads
            if str(item.get("thread_id") or "").strip()
        }
        active_thread_id = str(current.get("active_provider_thread_id") or "").strip()
        handoff_events = [dict(item) for item in list(current.get("handoff_events") or []) if isinstance(item, dict)]
        latest_handoff = handoff_events[-1] if handoff_events else None
        active_lane = _lane_view(by_thread_id.get(active_thread_id))
        if active_lane is None and active_thread_id:
            active_lane = _lane_view({"thread_id": active_thread_id})
        previous_handoff = next(
            (
                event
                for event in reversed(handoff_events)
                if str(event.get("to_thread_id") or "").strip() == active_thread_id
            ),
            latest_handoff,
        )
        previous_thread_id = str((previous_handoff or {}).get("from_thread_id") or "").strip()
        previous_lane = _lane_view(by_thread_id.get(previous_thread_id))
        if previous_lane is None:
            previous_lane = _lane_view_from_handoff_event(previous_handoff, source=True)
        compact_handoff = self.compact_handoff_event(previous_handoff) if isinstance(previous_handoff, dict) else None
        return {
            "lane_count": len(provider_threads),
            "handoff_count": len(handoff_events),
            "active_lane": active_lane,
            "previous_lane": previous_lane,
            "latest_handoff": compact_handoff,
        }

    def _provider_thread_settings(self, task: dict[str, Any] | None, thread_id: str | None) -> dict[str, Any] | None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id or not isinstance(task, dict):
            return None
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                return dict(item)
        return None

    def mark_provider_thread_missing(self, thread_id: str, *, reason: str | None = None) -> None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return
        task = self.current_task()
        if not task:
            return
        updated = False
        provider_threads: list[dict[str, Any]] = []
        for item in list(task.get("provider_threads") or []):
            entry = dict(item)
            if str(entry.get("thread_id") or "") == clean_thread_id:
                entry["missing_at"] = now_iso()
                entry["missing_reason"] = str(reason or "app_server_thread_not_found")
                updated = True
            provider_threads.append(entry)
        if not updated:
            return
        task["provider_threads"] = self._prune_provider_threads(provider_threads)
        if str(task.get("active_provider_thread_id") or "") == clean_thread_id:
            task["active_provider_thread_id"] = None
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_goal(self, thread_id: str, goal: Any) -> None:
        task = self.ensure_default_task(thread_id=thread_id)
        task["goal"] = redact_sensitive(goal)
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_plan(self, thread_id: str, plan: dict[str, Any]) -> None:
        task = self.ensure_default_task(thread_id=thread_id)
        task["plan"] = redact_sensitive(plan)
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        task = self.current_task()
        if not task:
            return
        refs = list(task.get("checkpoint_refs") or [])
        refs.insert(
            0,
            {
                "save_id": checkpoint.get("save_id"),
                "description": checkpoint.get("description") or checkpoint.get("default_description"),
                "created_at": checkpoint.get("created_at") or now_iso(),
            },
        )
        task["checkpoint_refs"] = refs[:40]
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_coding_events(self, events: list[dict[str, Any]] | None) -> None:
        task = self.current_task()
        if not task:
            return
        refs = task_refs_from_coding_events(events)
        checkpoint_refs = [
            *list(refs.get("checkpoint_refs") or []),
            *list(task.get("checkpoint_refs") or []),
        ]
        verification_refs = [
            *list(refs.get("verification_refs") or []),
            *list(task.get("verification_refs") or []),
        ]
        diagnostic_refs = [
            *list(refs.get("diagnostic_refs") or []),
            *list(task.get("diagnostic_refs") or []),
        ]
        task["checkpoint_refs"] = self._dedupe_records(checkpoint_refs, key_fields=("save_id",), limit=40)
        task["verification_refs"] = self._dedupe_records(verification_refs, key_fields=("event_id",), limit=40)
        task["diagnostic_refs"] = self._dedupe_records(diagnostic_refs, key_fields=("event_id",), limit=40)
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_context_ref(self, *, pack_type: str, path: str, generated_at: str, summary: dict[str, Any] | None = None) -> None:
        task = self.current_task()
        if not task:
            return
        ref = {
            "pack_type": str(pack_type or "").strip() or "context",
            "path": str(path or "").strip(),
            "generated_at": str(generated_at or "").strip() or now_iso(),
            "summary": dict(summary or {}),
        }
        refs = [item for item in list(task.get("context_pack_refs") or []) if not self._same_context_ref(item, ref)]
        refs.insert(0, ref)
        task["context_pack_refs"] = refs[:20]
        if ref["pack_type"] == "asset":
            asset_refs = [item for item in list(task.get("asset_context_refs") or []) if not self._same_context_ref(item, ref)]
            asset_refs.insert(0, ref)
            task["asset_context_refs"] = asset_refs[:10]
        task["updated_at"] = now_iso()
        self._save_task(task)

    def upsert_graph_definition(self, graph_definition: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        validated = validate_graph_definition(graph_definition)
        if str(validated.get("task_id") or "") != str(task.get("task_id") or ""):
            raise ValueError("graph_definition.task_id must match the current task.")
        prior_graph = self.graph_definition(str(validated.get("graph_id") or ""))
        prior_document = dict(dict(prior_graph or {}).get("graph_document") or {})
        canonical_graph = validate_agent_orchestration_graph(
            self._sync_orchestration_graph_with_task_graph(
                dict(validated.get("orchestration_graph") or prior_document.get("canonical_graph") or {}),
                task_graph=validated,
            )
        )
        graph_document = self._graph_document_from_task_graph(
            validated,
            canonical_graph=canonical_graph,
            existing_document=prior_document if prior_document else None,
        )
        validated["orchestration_graph"] = deepcopy(canonical_graph)
        validated["graph_document"] = deepcopy(graph_document)
        validated["graph_revision"] = deepcopy(dict(graph_document.get("current_revision") or {}))
        existing = [
            dict(item)
            for item in list(task.get("graph_definitions") or [])
            if isinstance(item, dict) and str(item.get("graph_id") or "").strip() != str(validated.get("graph_id") or "").strip()
        ]
        task["graph_definitions"] = [validated, *existing][:GRAPH_DEFINITION_LIMIT]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return validated

    @staticmethod
    def _legacy_graph_revision_id(graph_id: str, etag: str) -> str:
        digest = hashlib.sha256(f"{graph_id}|{etag}".encode("utf-8")).hexdigest()[:16]
        return f"graph-revision-legacy-{digest}"

    @staticmethod
    def _graph_document_etag(canonical_graph: dict[str, Any]) -> str:
        payload = json.dumps(redact_sensitive(canonical_graph), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    def _normalize_graph_source_ownership(self, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        source_file = dict(value.get("source_file") or {})
        path = str(source_file.get("path") or "").strip()
        sha256 = str(source_file.get("sha256") or "").strip()
        if not path or not sha256:
            return None
        ownership_mode = str(value.get("ownership_mode") or "").strip() or GRAPH_SOURCE_OWNERSHIP_SOURCE_OWNED
        detached_from = dict(value.get("detached_from") or {})
        normalized = {
            "schema_version": str(value.get("schema_version") or "").strip() or GRAPH_SOURCE_OWNERSHIP_SCHEMA_VERSION,
            "ownership_mode": ownership_mode,
            "can_write_from_gui": bool(value.get("can_write_from_gui"))
            if ownership_mode != GRAPH_SOURCE_OWNERSHIP_SOURCE_OWNED
            else False,
            "owner_kind": str(value.get("owner_kind") or "").strip() or "canonical_graph_file",
            "source_format": str(value.get("source_format") or "").strip() or AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT,
            "source_file": {
                "path": path,
                "sha256": sha256,
                "symbol": str(source_file.get("symbol") or "").strip() or None,
                "line_start": int(source_file.get("line_start") or 1),
                "line_end": int(source_file.get("line_end") or source_file.get("line_start") or 1),
            },
            "symbol_refs": [
                {
                    "target_kind": str(dict(item).get("target_kind") or "").strip() or None,
                    "target_id": str(dict(item).get("target_id") or "").strip() or None,
                    "symbol": str(dict(item).get("symbol") or "").strip() or None,
                    "source_path": str(dict(item).get("source_path") or path).strip() or path,
                    "sha256": str(dict(item).get("sha256") or sha256).strip() or sha256,
                    "line_start": int(dict(item).get("line_start") or 1),
                    "line_end": int(dict(item).get("line_end") or dict(item).get("line_start") or 1),
                }
                for item in list(value.get("symbol_refs") or [])
                if isinstance(item, dict)
            ],
            "detached_from": {
                "path": str(detached_from.get("path") or "").strip() or None,
                "sha256": str(detached_from.get("sha256") or "").strip() or None,
                "symbol": str(detached_from.get("symbol") or "").strip() or None,
                "line_start": int(detached_from.get("line_start") or 1),
                "line_end": int(detached_from.get("line_end") or detached_from.get("line_start") or 1),
            }
            if detached_from
            else None,
            "detached_at": str(value.get("detached_at") or "").strip() or None,
            "detached_reason": str(value.get("detached_reason") or "").strip() or None,
        }
        if not normalized["symbol_refs"]:
            normalized["symbol_refs"] = [
                {
                    "target_kind": "graph",
                    "target_id": str(source_file.get("symbol") or "").strip() or None,
                    "symbol": str(source_file.get("symbol") or "").strip() or None,
                    "source_path": path,
                    "sha256": sha256,
                    "line_start": int(source_file.get("line_start") or 1),
                    "line_end": int(source_file.get("line_end") or source_file.get("line_start") or 1),
                }
            ]
        return normalized

    def _build_graph_source_ownership(
        self,
        *,
        canonical_graph: dict[str, Any],
        source_path: str,
        source_text: str,
        source_format: str,
    ) -> dict[str, Any]:
        clean_path = str(source_path or "").strip()
        digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        graph_id = str(canonical_graph.get("graph_id") or "").strip()
        symbol_refs = [
            {
                "target_kind": "graph",
                "target_id": graph_id,
                "symbol": graph_id or "graph",
                "source_path": clean_path,
                "sha256": digest,
                "line_start": 1,
                "line_end": 1,
            }
        ]
        for node in list(canonical_graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or "").strip()
            if not node_id:
                continue
            symbol_refs.append(
                {
                    "target_kind": "node",
                    "target_id": node_id,
                    "symbol": node_id,
                    "source_path": clean_path,
                    "sha256": digest,
                    "line_start": 1,
                    "line_end": 1,
                }
            )
        for edge in list(canonical_graph.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            edge_id = str(edge.get("edge_id") or "").strip()
            if not edge_id:
                continue
            symbol_refs.append(
                {
                    "target_kind": "edge",
                    "target_id": edge_id,
                    "symbol": edge_id,
                    "source_path": clean_path,
                    "sha256": digest,
                    "line_start": 1,
                    "line_end": 1,
                }
            )
        return {
            "schema_version": GRAPH_SOURCE_OWNERSHIP_SCHEMA_VERSION,
            "ownership_mode": GRAPH_SOURCE_OWNERSHIP_SOURCE_OWNED,
            "can_write_from_gui": False,
            "owner_kind": "canonical_graph_file",
            "source_format": str(source_format or "").strip() or AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT,
            "source_file": {
                "path": clean_path,
                "sha256": digest,
                "symbol": graph_id or "graph",
                "line_start": 1,
                "line_end": 1,
            },
            "symbol_refs": symbol_refs,
            "detached_from": None,
            "detached_at": None,
            "detached_reason": None,
        }

    def _graph_source_ownership(
        self,
        *,
        canonical_graph: dict[str, Any] | None = None,
        document: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        metadata = dict(dict(canonical_graph or {}).get("metadata") or {})
        ownership = self._normalize_graph_source_ownership(metadata.get("source_ownership"))
        if ownership:
            return ownership
        return self._normalize_graph_source_ownership(dict(document or {}).get("source_ownership"))

    def _apply_graph_source_ownership(
        self,
        canonical_graph: dict[str, Any],
        ownership: dict[str, Any] | None,
    ) -> dict[str, Any]:
        updated = deepcopy(canonical_graph)
        metadata = dict(updated.get("metadata") or {})
        if ownership:
            metadata["source_ownership"] = deepcopy(ownership)
        else:
            metadata.pop("source_ownership", None)
        updated["metadata"] = metadata
        return updated

    def _detach_graph_source_ownership(self, value: Any) -> dict[str, Any] | None:
        ownership = self._normalize_graph_source_ownership(value)
        if not ownership:
            return None
        detached_from = dict(ownership.get("detached_from") or {}) or deepcopy(dict(ownership.get("source_file") or {}))
        ownership["ownership_mode"] = GRAPH_SOURCE_OWNERSHIP_DETACHED
        ownership["can_write_from_gui"] = True
        ownership["detached_from"] = detached_from
        ownership["detached_at"] = now_iso()
        ownership["detached_reason"] = "gui_detach_requested"
        return ownership

    def _compact_graph_document(self, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        revision = dict(value.get("current_revision") or {})
        migration = dict(value.get("migration") or {})
        compatibility = dict(value.get("compatibility_projection") or {})
        source_ownership = self._graph_source_ownership(document=value)
        compact = {
            "schema_version": str(value.get("schema_version") or "").strip() or GRAPH_DOCUMENT_SCHEMA_VERSION,
            "graph_id": str(value.get("graph_id") or "").strip(),
            "task_id": str(value.get("task_id") or "").strip(),
            "created_at": str(value.get("created_at") or "").strip(),
            "updated_at": str(value.get("updated_at") or "").strip(),
            "current_revision": {
                "revision_id": str(revision.get("revision_id") or "").strip() or None,
                "revision_index": int(revision.get("revision_index") or 0),
                "etag": str(revision.get("etag") or "").strip() or None,
                "created_at": str(revision.get("created_at") or "").strip() or None,
                "graph_schema_version": str(revision.get("graph_schema_version") or "").strip() or None,
                "task_graph_schema_version": str(revision.get("task_graph_schema_version") or "").strip() or None,
            },
            "migration": {
                "document_schema_version": str(migration.get("document_schema_version") or "").strip() or GRAPH_DOCUMENT_SCHEMA_VERSION,
                "upgraded_from": str(migration.get("upgraded_from") or "").strip() or None,
                "chain": [
                    deepcopy(dict(item))
                    for item in list(migration.get("chain") or [])
                    if isinstance(item, dict)
                ][:8],
                "compatibility_ranges": self._normalize_graph_document_compatibility_ranges(
                    migration.get("compatibility_ranges")
                ),
                "rollback_support": str(migration.get("rollback_support") or "").strip() or None,
            },
            "compatibility_projection": {
                "source_kind": str(compatibility.get("source_kind") or "").strip() or "canonical_orchestration_graph",
                "writable_source": str(compatibility.get("writable_source") or "").strip() or "canonical_orchestration_graph",
                "task_graph_schema_version": str(compatibility.get("task_graph_schema_version") or "").strip() or None,
                "lowering_mode": str(compatibility.get("lowering_mode") or "").strip() or None,
                "generated_at": str(compatibility.get("generated_at") or "").strip() or None,
            },
            "source_ownership": {
                "ownership_mode": str(source_ownership.get("ownership_mode") or "").strip() or None,
                "can_write_from_gui": bool(source_ownership.get("can_write_from_gui")),
                "source_path": str(dict(source_ownership.get("source_file") or {}).get("path") or "").strip() or None,
                "source_sha256": str(dict(source_ownership.get("source_file") or {}).get("sha256") or "").strip() or None,
                "detached_at": str(source_ownership.get("detached_at") or "").strip() or None,
                "detached_from_path": str(dict(source_ownership.get("detached_from") or {}).get("path") or "").strip() or None,
                "symbol_ref_count": len(list(source_ownership.get("symbol_refs") or [])),
            }
            if source_ownership
            else None,
        }
        return compact

    @staticmethod
    def _graph_document_schema_list(*groups: Any) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for item in list(group or []):
                text = str(item or "").strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                ordered.append(text)
        return ordered

    def _normalize_graph_document_compatibility_ranges(
        self,
        value: Any,
        *,
        task_graph_schema_version: str | None = None,
        orchestration_schema_version: str | None = None,
    ) -> dict[str, Any]:
        raw = dict(value or {}) if isinstance(value, dict) else {}
        raw_document = raw.get("document_schema_versions")
        raw_task_consumers = dict(raw.get("task_graph_consumers") or {})
        raw_orchestration_consumers = dict(raw.get("orchestration_consumers") or {})

        document_read = self._graph_document_schema_list(
            list(dict(raw_document).get("read") or []) if isinstance(raw_document, dict) else [],
            raw_document if isinstance(raw_document, list) else [],
            [GRAPH_DOCUMENT_LEGACY_SCHEMA_V2, GRAPH_DOCUMENT_SCHEMA_VERSION],
        )
        document_write = (
            str(dict(raw_document).get("write") or "").strip()
            if isinstance(raw_document, dict)
            else ""
        ) or GRAPH_DOCUMENT_SCHEMA_VERSION
        task_graph_read = self._graph_document_schema_list(
            list(raw.get("task_graph_schema_versions") or []),
            list(raw_task_consumers.get("read") or []),
            [task_graph_schema_version] if task_graph_schema_version else [],
        )
        orchestration_read = self._graph_document_schema_list(
            list(raw.get("orchestration_schema_versions") or []),
            list(raw_orchestration_consumers.get("read") or []),
            [orchestration_schema_version] if orchestration_schema_version else [],
        )
        task_graph_write = (
            str(raw_task_consumers.get("write") or "").strip()
            or task_graph_schema_version
            or (task_graph_read[0] if task_graph_read else TASK_GRAPH_SCHEMA_VERSION)
        )
        orchestration_write = (
            str(raw_orchestration_consumers.get("write") or "").strip()
            or orchestration_schema_version
            or (orchestration_read[0] if orchestration_read else AGENT_ORCHESTRATION_SCHEMA_VERSION)
        )
        if not task_graph_read:
            task_graph_read = [task_graph_write]
        if not orchestration_read:
            orchestration_read = [orchestration_write]
        return {
            "document_schema_versions": {
                "read": document_read,
                "write": document_write,
                "rollback_read": self._graph_document_schema_list(
                    list(dict(raw_document).get("rollback_read") or []) if isinstance(raw_document, dict) else [],
                    document_read,
                ),
            },
            "task_graph_schema_versions": task_graph_read,
            "orchestration_schema_versions": orchestration_read,
            "task_graph_consumers": {
                "read": task_graph_read,
                "write": task_graph_write,
                "source_kind": "task_graph_definition",
                "lowering_mode": "generated_compatibility_projection",
            },
            "orchestration_consumers": {
                "read": orchestration_read,
                "write": orchestration_write,
                "source_kind": "canonical_orchestration_graph",
                "writable_source": "canonical_orchestration_graph",
            },
        }

    def _graph_document_evidence(self, source: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(source, dict):
            return None
        candidate = dict(source)
        if (
            str(candidate.get("schema_version") or "").strip() == GRAPH_DOCUMENT_SCHEMA_VERSION
            and isinstance(candidate.get("canonical_graph"), dict)
        ):
            document = candidate
            revision = dict(document.get("current_revision") or {})
        else:
            document = dict(candidate.get("graph_document") or {})
            revision = dict(candidate.get("graph_revision") or document.get("current_revision") or {})
        if not document:
            return None
        migration = dict(document.get("migration") or {})
        compatibility = dict(document.get("compatibility_projection") or {})
        current_canonical = dict(document.get("canonical_graph") or {})
        source_ownership = self._graph_source_ownership(canonical_graph=current_canonical, document=document)
        compatibility_ranges = self._normalize_graph_document_compatibility_ranges(
            migration.get("compatibility_ranges"),
            task_graph_schema_version=str(
                compatibility.get("task_graph_schema_version")
                or revision.get("task_graph_schema_version")
                or candidate.get("schema_version")
                or TASK_GRAPH_SCHEMA_VERSION
            ).strip()
            or TASK_GRAPH_SCHEMA_VERSION,
            orchestration_schema_version=str(
                revision.get("graph_schema_version")
                or current_canonical.get("schema_version")
                or AGENT_ORCHESTRATION_SCHEMA_VERSION
            ).strip()
            or AGENT_ORCHESTRATION_SCHEMA_VERSION,
        )
        return {
            "document_schema_version": str(document.get("schema_version") or "").strip() or GRAPH_DOCUMENT_SCHEMA_VERSION,
            "migration_origin": str(migration.get("upgraded_from") or "").strip() or None,
            "migration_chain_length": len(
                [item for item in list(migration.get("chain") or []) if isinstance(item, dict)]
            ),
            "migration_source_kind": str(compatibility.get("migration_source_kind") or "").strip()
            or str(dict(current_canonical.get("migration") or {}).get("source_kind") or "").strip()
            or None,
            "compatibility_mode": str(compatibility.get("lowering_mode") or "").strip()
            or str(compatibility.get("source_kind") or "").strip()
            or "generated_compatibility_projection",
            "reviewed_for_live_execution": bool(compatibility.get("reviewed_for_live_execution")),
            "rollback_support": str(migration.get("rollback_support") or "").strip() or None,
            "revision_id": str(revision.get("revision_id") or "").strip() or None,
            "revision_index": int(revision.get("revision_index") or 0),
            "etag": str(revision.get("etag") or "").strip() or None,
            "task_graph_schema_version": str(
                compatibility.get("task_graph_schema_version")
                or revision.get("task_graph_schema_version")
                or candidate.get("schema_version")
                or TASK_GRAPH_SCHEMA_VERSION
            ).strip()
            or TASK_GRAPH_SCHEMA_VERSION,
            "orchestration_schema_version": str(
                revision.get("graph_schema_version")
                or current_canonical.get("schema_version")
                or AGENT_ORCHESTRATION_SCHEMA_VERSION
            ).strip()
            or AGENT_ORCHESTRATION_SCHEMA_VERSION,
            "compatibility_ranges": compatibility_ranges,
            "source_ownership_mode": str(source_ownership.get("ownership_mode") or "").strip() or None if source_ownership else None,
            "source_ownership_can_write_from_gui": bool(source_ownership.get("can_write_from_gui")) if source_ownership else None,
            "source_ownership_path": str(dict(source_ownership.get("source_file") or {}).get("path") or "").strip() or None if source_ownership else None,
            "source_ownership_detached_at": str(source_ownership.get("detached_at") or "").strip() or None if source_ownership else None,
            "source_ownership_symbol_ref_count": len(list(source_ownership.get("symbol_refs") or [])) if source_ownership else 0,
        }

    def _graph_document_rollback_preview(
        self,
        *,
        snapshot_id: str,
        snapshot_graph: dict[str, Any],
        current_graph: dict[str, Any],
        comparison_mode: str,
    ) -> dict[str, Any]:
        return {
            "snapshot_id": str(snapshot_id or "").strip(),
            "comparison_mode": str(comparison_mode or "").strip() or "snapshot_to_current",
            "restored_document": self._graph_document_evidence(snapshot_graph),
            "current_document": self._graph_document_evidence(current_graph),
        }

    def _graph_document_from_task_graph(
        self,
        task_graph: dict[str, Any],
        *,
        canonical_graph: dict[str, Any] | None = None,
        existing_document: dict[str, Any] | None = None,
        upgraded_from: str | None = None,
        preserve_existing_revision: bool = False,
    ) -> dict[str, Any]:
        validated_graph = validate_graph_definition(deepcopy(task_graph))
        resolved_canonical = validate_agent_orchestration_graph(
            deepcopy(canonical_graph)
            if isinstance(canonical_graph, dict) and canonical_graph
            else self._sync_orchestration_graph_with_task_graph(
                dict(dict(existing_document or {}).get("canonical_graph") or validated_graph.get("orchestration_graph") or {}),
                task_graph=validated_graph,
            )
        )
        existing_revision = dict(dict(existing_document or {}).get("current_revision") or {})
        existing_migration = dict(dict(existing_document or {}).get("migration") or {})
        existing_compatibility = dict(dict(existing_document or {}).get("compatibility_projection") or {})
        source_ownership = self._graph_source_ownership(canonical_graph=resolved_canonical, document=existing_document)
        etag = self._graph_document_etag(resolved_canonical)
        revision_created_at = str(validated_graph.get("updated_at") or now_iso()).strip() or now_iso()
        task_graph_schema_version = str(validated_graph.get("schema_version") or "").strip() or TASK_GRAPH_SCHEMA_VERSION
        orchestration_schema_version = str(resolved_canonical.get("schema_version") or "").strip() or AGENT_ORCHESTRATION_SCHEMA_VERSION
        existing_revision_index = int(existing_revision.get("revision_index") or 0)
        preserve_revision = (
            preserve_existing_revision
            and str(dict(existing_document or {}).get("schema_version") or "").strip() == GRAPH_DOCUMENT_SCHEMA_VERSION
            and str(existing_revision.get("etag") or "").strip() == etag
            and existing_revision_index >= int(validated_graph.get("state_version") or 0)
        )
        if preserve_revision:
            revision = {
                "revision_id": str(existing_revision.get("revision_id") or "").strip() or self._legacy_graph_revision_id(
                    str(validated_graph.get("graph_id") or ""),
                    etag,
                ),
                "revision_index": max(existing_revision_index, 1),
                "etag": etag,
                "created_at": str(existing_revision.get("created_at") or revision_created_at).strip() or revision_created_at,
                "updated_at": str(existing_revision.get("updated_at") or existing_revision.get("created_at") or revision_created_at).strip() or revision_created_at,
                "graph_schema_version": str(resolved_canonical.get("schema_version") or "").strip() or None,
                "task_graph_schema_version": str(validated_graph.get("schema_version") or "").strip() or None,
            }
        else:
            revision_index = max(
                existing_revision_index + 1,
                int(validated_graph.get("state_version") or 0),
                1,
            )
            revision = {
                "revision_id": new_id("graph-revision"),
                "revision_index": revision_index,
                "etag": etag,
                "created_at": revision_created_at,
                "updated_at": revision_created_at,
                "graph_schema_version": str(resolved_canonical.get("schema_version") or "").strip() or None,
                "task_graph_schema_version": str(validated_graph.get("schema_version") or "").strip() or None,
            }
        migration_chain = [
            deepcopy(dict(item))
            for item in list(existing_migration.get("chain") or [])
            if isinstance(item, dict)
        ]
        upgrade_origin = str(
            existing_migration.get("upgraded_from")
            or upgraded_from
            or GRAPH_DOCUMENT_SCHEMA_VERSION
        ).strip() or GRAPH_DOCUMENT_SCHEMA_VERSION
        existing_compatibility_ranges = self._normalize_graph_document_compatibility_ranges(
            existing_migration.get("compatibility_ranges")
        )
        compatibility_ranges = self._normalize_graph_document_compatibility_ranges(
            existing_migration.get("compatibility_ranges"),
            task_graph_schema_version=task_graph_schema_version,
            orchestration_schema_version=orchestration_schema_version,
        )
        preserve_migration_state = (
            str(dict(existing_document or {}).get("schema_version") or "").strip() == GRAPH_DOCUMENT_SCHEMA_VERSION
            and str(existing_migration.get("document_schema_version") or GRAPH_DOCUMENT_SCHEMA_VERSION).strip() == GRAPH_DOCUMENT_SCHEMA_VERSION
            and str(existing_migration.get("upgraded_from") or upgrade_origin).strip() == upgrade_origin
            and existing_compatibility_ranges == compatibility_ranges
        )
        current_step = {
            "from": upgrade_origin,
            "to": GRAPH_DOCUMENT_SCHEMA_VERSION,
            "status": "applied",
            "applied_at": revision_created_at,
            "preserves_extensions": True,
            "rollback_mode": "snapshot_based",
        }
        route_already_recorded = any(
            isinstance(item, dict)
            and str(item.get("from") or "").strip() == str(current_step.get("from") or "").strip()
            and str(item.get("to") or "").strip() == str(current_step.get("to") or "").strip()
            and str(item.get("status") or "").strip() == str(current_step.get("status") or "").strip()
            and str(item.get("rollback_mode") or "").strip() == str(current_step.get("rollback_mode") or "").strip()
            and bool(item.get("preserves_extensions")) == bool(current_step.get("preserves_extensions"))
            for item in migration_chain
        )
        if not route_already_recorded:
            migration_chain.append(current_step)
        compatibility_generated_at = (
            str(existing_compatibility.get("generated_at") or "").strip()
            if preserve_migration_state
            else ""
        ) or revision_created_at
        canonical_migration = dict(resolved_canonical.get("migration") or {})
        canonical_compatibility = dict(canonical_migration.get("compatibility") or {})
        writable_source = "canonical_orchestration_graph"
        source_kind = "canonical_orchestration_graph"
        if source_ownership:
            source_kind = "canonical_orchestration_graph_file"
            writable_source = (
                GRAPH_SOURCE_OWNERSHIP_DETACHED_WRITABLE_SOURCE
                if str(source_ownership.get("ownership_mode") or "").strip() == GRAPH_SOURCE_OWNERSHIP_DETACHED
                else GRAPH_SOURCE_OWNERSHIP_WRITABLE_SOURCE
            )
        return {
            "schema_version": GRAPH_DOCUMENT_SCHEMA_VERSION,
            "graph_id": str(validated_graph.get("graph_id") or "").strip(),
            "task_id": str(validated_graph.get("task_id") or "").strip(),
            "title": str(validated_graph.get("title") or "").strip(),
            "template_id": str(validated_graph.get("template_id") or "").strip(),
            "status": str(validated_graph.get("status") or "").strip(),
            "created_at": str(dict(existing_document or {}).get("created_at") or validated_graph.get("created_at") or revision_created_at).strip() or revision_created_at,
            "updated_at": revision_created_at,
            "canonical_graph": deepcopy(resolved_canonical),
            "current_revision": revision,
            "migration": {
                "document_schema_version": GRAPH_DOCUMENT_SCHEMA_VERSION,
                "upgraded_from": upgrade_origin,
                "chain": migration_chain,
                "compatibility_ranges": compatibility_ranges,
                "rollback_support": "graph_snapshot_refs",
            },
            "compatibility_projection": {
                "source_kind": source_kind,
                "migration_source_kind": str(canonical_migration.get("source_kind") or "").strip() or None,
                "writable_source": writable_source,
                "task_graph_schema_version": task_graph_schema_version,
                "lowering_mode": "generated_compatibility_projection",
                "preserves_unknown_fields": bool(
                    canonical_compatibility.get("preserves_unknown_fields")
                ),
                "reviewed_for_live_execution": bool(canonical_compatibility.get("reviewed_for_live_execution")),
                "generated_at": compatibility_generated_at,
            },
            "source_ownership": deepcopy(source_ownership) if source_ownership else None,
        }

    @staticmethod
    def _graph_import_execution_guard(
        orchestration_graph: dict[str, Any],
        *,
        require_live_contract: bool,
    ) -> dict[str, Any]:
        migration = dict(orchestration_graph.get("migration") or {})
        compatibility = dict(migration.get("compatibility") or {})
        source_kind = str(migration.get("source_kind") or "").strip() or "native_authoring"
        reviewed_for_live_execution = bool(compatibility.get("reviewed_for_live_execution"))
        graph_status = "pass"
        graph_reasons: list[str] = []
        if source_kind == "imported_file" and not reviewed_for_live_execution:
            graph_status = "blocked" if require_live_contract else "warning"
            graph_reasons.append(
                "Imported compatibility graph is quarantined from live execution until migration.compatibility.reviewed_for_live_execution is set to true."
                if require_live_contract
                else "Imported compatibility graph should be reviewed before execution because migration.compatibility.reviewed_for_live_execution is not set."
            )
        node_results: dict[str, dict[str, Any]] = {}
        for node in list(orchestration_graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or "").strip()
            if not node_id:
                continue
            diagnostics = [
                str(dict(item).get("message") or dict(item).get("code") or "").strip()
                for item in list(node.get("node_type_diagnostics") or [])
                if isinstance(item, dict)
                and str(dict(item).get("message") or dict(item).get("code") or "").strip()
            ]
            if str(node.get("status") or "").strip() != "disabled" and not diagnostics:
                continue
            reasons = (
                [
                    f"Imported compatibility node `{node_id}` is disabled until its type mapping is reviewed: {message}"
                    for message in diagnostics
                ]
                if diagnostics
                else [f"Imported compatibility node `{node_id}` is disabled until its type mapping is reviewed."]
            )
            node_results[node_id] = {
                "status": "blocked",
                "reasons": reasons,
            }
        return {
            "source_kind": source_kind,
            "reviewed_for_live_execution": reviewed_for_live_execution,
            "graph_status": graph_status,
            "graph_reasons": graph_reasons,
            "node_results": node_results,
        }

    def _migrate_graph_record_to_current_document(self, value: dict[str, Any], *, task_id: str) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        graph_document = dict(value.get("graph_document") or {})
        if graph_document:
            canonical_graph = dict(graph_document.get("canonical_graph") or value.get("orchestration_graph") or {})
            if not canonical_graph:
                canonical_graph = self._sync_orchestration_graph_with_task_graph({}, task_graph=value)
            document = self._graph_document_from_task_graph(
                value,
                canonical_graph=canonical_graph,
                existing_document=graph_document,
                upgraded_from=str(
                    dict(graph_document.get("migration") or {}).get("upgraded_from")
                    or graph_document.get("schema_version")
                    or GRAPH_DOCUMENT_LEGACY_SCHEMA_V2
                ),
                preserve_existing_revision=True,
            )
        else:
            document = self._graph_document_from_task_graph(
                value,
                canonical_graph=dict(value.get("orchestration_graph") or {}),
                existing_document=None,
                upgraded_from="legacy_task_graph_definition",
            )
            document["current_revision"]["revision_id"] = self._legacy_graph_revision_id(
                str(document.get("graph_id") or ""),
                str(dict(document.get("current_revision") or {}).get("etag") or ""),
            )
        projected = validate_graph_definition(deepcopy(value))
        projected["orchestration_graph"] = deepcopy(dict(document.get("canonical_graph") or {}))
        projected["graph_document"] = deepcopy(document)
        projected["graph_revision"] = deepcopy(dict(document.get("current_revision") or {}))
        projected["state_version"] = max(
            int(projected.get("state_version") or 0),
            int(dict(document.get("current_revision") or {}).get("revision_index") or 0),
            1,
        )
        if task_id and str(projected.get("task_id") or "").strip() != task_id:
            return None
        return projected

    @staticmethod
    def _graph_revision_payload(graph: dict[str, Any] | None) -> dict[str, Any]:
        revision = dict(dict(graph or {}).get("graph_revision") or {})
        if not revision and isinstance(dict(graph or {}).get("graph_document"), dict):
            revision = dict(dict(dict(graph or {}).get("graph_document") or {}).get("current_revision") or {})
        return {
            "revision_id": str(revision.get("revision_id") or "").strip() or None,
            "revision_index": int(revision.get("revision_index") or 0),
            "etag": str(revision.get("etag") or "").strip() or None,
        }

    @staticmethod
    def _payload_source_owner_action(payload: dict[str, Any] | None) -> str:
        return str(dict(payload or {}).get("source_owner_action") or "").strip().lower()

    def _raise_graph_source_ownership_error(
        self,
        *,
        action: str,
        current_graph: dict[str, Any],
        source_ownership: dict[str, Any],
    ) -> None:
        source_path = str(dict(source_ownership.get("source_file") or {}).get("path") or "").strip()
        raise GraphSourceOwnershipError(
            "This graph is source-owned and cannot be overwritten from the GUI until it is detached.",
            payload={
                "error": "graph_source_owned",
                "action": action,
                "message": "This graph is source-owned and cannot be overwritten from the GUI until it is detached.",
                "source_ownership": deepcopy(source_ownership),
                "graph_document": self._graph_document_evidence(current_graph),
                "graph": deepcopy(current_graph),
                "task": self.task_view(self.current_task()),
                "allow_detach_action": True,
                "source_path": source_path or None,
            },
        )

    def _require_graph_source_ownership_write_allowed(
        self,
        *,
        action: str,
        payload: dict[str, Any],
        current_graph: dict[str, Any],
    ) -> dict[str, Any] | None:
        source_ownership = self._graph_source_ownership(
            canonical_graph=dict(dict(current_graph.get("graph_document") or {}).get("canonical_graph") or current_graph.get("orchestration_graph") or {}),
            document=dict(current_graph.get("graph_document") or {}),
        )
        if not source_ownership:
            return None
        if str(source_ownership.get("ownership_mode") or "").strip() != GRAPH_SOURCE_OWNERSHIP_SOURCE_OWNED:
            return source_ownership
        if self._payload_source_owner_action(payload) == "detach":
            return self._detach_graph_source_ownership(source_ownership)
        self._raise_graph_source_ownership_error(
            action=action,
            current_graph=current_graph,
            source_ownership=source_ownership,
        )
        return None

    def _graph_snapshot_for_revision(
        self,
        *,
        graph_id: str,
        expected_revision: str | None,
        expected_etag: str | None,
    ) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        clean_graph_id = str(graph_id or "").strip()
        clean_expected_revision = str(expected_revision or "").strip()
        clean_expected_etag = str(expected_etag or "").strip()
        for item in list(task.get("graph_snapshot_refs") or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("graph_id") or "").strip() != clean_graph_id:
                continue
            evidence = dict(item.get("graph_document_evidence") or {})
            revision_id = str(evidence.get("revision_id") or "").strip()
            etag = str(evidence.get("etag") or "").strip()
            if clean_expected_revision and revision_id == clean_expected_revision:
                return dict(item)
            if clean_expected_etag and etag == clean_expected_etag:
                return dict(item)
        return None

    def _graph_from_snapshot_ref(
        self,
        snapshot: dict[str, Any],
        *,
        task: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(snapshot, dict):
            return None
        effective_task = task or self.current_task()
        if not effective_task:
            return None
        stored_graph = read_json(
            self._resolve_snapshot_artifact_path(snapshot, key="task_graph_json", task=effective_task),
            {},
        )
        if not isinstance(stored_graph, dict):
            return None
        return self._migrate_graph_record_to_current_document(
            stored_graph,
            task_id=str(effective_task.get("task_id") or ""),
        )

    @staticmethod
    def _graph_conflict_orchestration_surface(graph: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(dict(graph or {}))
        normalized["nodes"] = {
            str(item.get("node_id") or "").strip(): deepcopy(dict(item))
            for item in list(normalized.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        normalized["edges"] = {
            str(item.get("edge_id") or "").strip(): deepcopy(dict(item))
            for item in list(normalized.get("edges") or [])
            if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
        }
        return normalized

    @staticmethod
    def _graph_conflict_surface(graph: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": str(graph.get("title") or "").strip(),
            "template_id": str(graph.get("template_id") or "").strip(),
            "status": str(graph.get("status") or "").strip(),
            "graph_policy": deepcopy(dict(graph.get("graph_policy") or {})),
            "orchestration_graph": TaskService._graph_conflict_orchestration_surface(
                dict(graph.get("orchestration_graph") or {})
            ),
            "nodes": {
                str(item.get("node_id") or "").strip(): deepcopy(dict(item))
                for item in list(graph.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip()
            },
            "edges": {
                str(item.get("edge_id") or "").strip(): deepcopy(dict(item))
                for item in list(graph.get("edges") or [])
                if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
            },
        }

    @staticmethod
    def _graph_conflict_ordered_union_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
        keys = [str(key) for key in before.keys()]
        keys.extend(str(key) for key in after.keys() if str(key) not in before)
        return keys

    def _graph_conflict_changes(
        self,
        before: Any,
        after: Any,
        *,
        path: tuple[str, ...] = (),
    ) -> dict[tuple[str, ...], dict[str, Any]]:
        changes: dict[tuple[str, ...], dict[str, Any]] = {}
        if isinstance(before, dict) and isinstance(after, dict):
            for key in self._graph_conflict_ordered_union_keys(before, after):
                in_before = key in before
                in_after = key in after
                next_path = (*path, key)
                if in_before and in_after:
                    changes.update(self._graph_conflict_changes(before[key], after[key], path=next_path))
                elif in_before:
                    changes[next_path] = {"before": deepcopy(before[key]), "after": _GRAPH_CONFLICT_DELETE}
                elif in_after:
                    changes[next_path] = {"before": _GRAPH_CONFLICT_DELETE, "after": deepcopy(after[key])}
            return changes
        if before != after and not self._graph_conflict_ignore_path(path):
            changes[path] = {"before": deepcopy(before), "after": deepcopy(after)}
        return changes

    @staticmethod
    def _graph_conflict_ignore_path(path: tuple[str, ...]) -> bool:
        if path == ("orchestration_graph", "state_version"):
            return True
        if path == ("orchestration_graph", "metadata", "updated_at"):
            return True
        return False

    @staticmethod
    def _graph_conflict_paths_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
        shorter = left if len(left) <= len(right) else right
        longer = right if shorter is left else left
        return longer[: len(shorter)] == shorter

    @staticmethod
    def _graph_conflict_path_text(path: tuple[str, ...]) -> str:
        return ".".join(path)

    @staticmethod
    def _graph_conflict_apply_change(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
        cursor: dict[str, Any] = target
        for key in path[:-1]:
            next_value = cursor.get(key)
            if not isinstance(next_value, dict):
                next_value = {}
                cursor[key] = next_value
            cursor = next_value
        leaf = path[-1]
        if value is _GRAPH_CONFLICT_DELETE:
            cursor.pop(leaf, None)
        else:
            cursor[leaf] = deepcopy(value)

    @staticmethod
    def _graph_conflict_value_at_path(value: Any, path: tuple[str, ...]) -> Any:
        cursor = value
        for key in path:
            if not isinstance(cursor, dict) or key not in cursor:
                return _GRAPH_CONFLICT_DELETE
            cursor = cursor[key]
        return deepcopy(cursor)

    @staticmethod
    def _graph_conflict_payload_value(value: Any) -> Any:
        if value is _GRAPH_CONFLICT_DELETE:
            return {"deleted": True}
        return redact_sensitive(deepcopy(value))

    def _materialize_graph_from_conflict_surface(
        self,
        *,
        current_graph: dict[str, Any],
        surface: dict[str, Any],
    ) -> dict[str, Any]:
        merged = deepcopy(current_graph)
        merged["title"] = str(surface.get("title") or "").strip()
        merged["template_id"] = str(surface.get("template_id") or "").strip()
        merged["status"] = str(surface.get("status") or "").strip()
        merged["graph_policy"] = deepcopy(dict(surface.get("graph_policy") or {}))
        orchestration_graph = deepcopy(dict(surface.get("orchestration_graph") or {}))
        orchestration_graph["nodes"] = [
            deepcopy(node)
            for node in dict(orchestration_graph.get("nodes") or {}).values()
            if isinstance(node, dict) and str(node.get("node_id") or "").strip()
        ]
        orchestration_graph["edges"] = [
            deepcopy(edge)
            for edge in dict(orchestration_graph.get("edges") or {}).values()
            if isinstance(edge, dict) and str(edge.get("edge_id") or "").strip()
        ]
        merged["orchestration_graph"] = orchestration_graph
        merged["nodes"] = [
            deepcopy(node)
            for node in dict(surface.get("nodes") or {}).values()
            if isinstance(node, dict) and str(node.get("node_id") or "").strip()
        ]
        merged["edges"] = [
            deepcopy(edge)
            for edge in dict(surface.get("edges") or {}).values()
            if isinstance(edge, dict) and str(edge.get("edge_id") or "").strip()
        ]
        return validate_graph_definition(merged)

    def _merge_non_conflicting_graph_changes(
        self,
        *,
        base_graph: dict[str, Any],
        current_graph: dict[str, Any],
        incoming_graph: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        base_surface = self._graph_conflict_surface(base_graph)
        current_surface = self._graph_conflict_surface(current_graph)
        incoming_surface = self._graph_conflict_surface(incoming_graph)
        current_changes = self._graph_conflict_changes(base_surface, current_surface)
        incoming_changes = self._graph_conflict_changes(base_surface, incoming_surface)
        merged_surface = deepcopy(current_surface)
        overlapping: list[dict[str, Any]] = []
        for incoming_path, incoming_change in incoming_changes.items():
            current_overlaps = [
                (current_path, current_change)
                for current_path, current_change in current_changes.items()
                if self._graph_conflict_paths_overlap(current_path, incoming_path)
            ]
            conflicting_overlaps = [
                (current_path, current_change)
                for current_path, current_change in current_overlaps
                if not (
                    current_path == incoming_path
                    and current_change.get("after") == incoming_change.get("after")
                )
            ]
            if conflicting_overlaps:
                overlapping.append(
                    {
                        "path": self._graph_conflict_path_text(incoming_path),
                        "base": self._graph_conflict_payload_value(
                            self._graph_conflict_value_at_path(base_surface, incoming_path)
                        ),
                        "current": self._graph_conflict_payload_value(
                            self._graph_conflict_value_at_path(current_surface, incoming_path)
                        ),
                        "incoming": self._graph_conflict_payload_value(
                            self._graph_conflict_value_at_path(incoming_surface, incoming_path)
                        ),
                        "current_paths": [
                            self._graph_conflict_path_text(current_path)
                            for current_path, _current_change in conflicting_overlaps
                        ],
                    }
                )
                continue
            self._graph_conflict_apply_change(merged_surface, incoming_path, incoming_change.get("after"))
        report = {
            "status": "merged" if not overlapping else "overlap_rejected",
            "current_changed_paths": [
                self._graph_conflict_path_text(path)
                for path in list(current_changes.keys())[:80]
            ],
            "incoming_changed_paths": [
                self._graph_conflict_path_text(path)
                for path in list(incoming_changes.keys())[:80]
            ],
            "overlapping_edits": overlapping[:40],
        }
        if overlapping:
            return None, report
        return self._materialize_graph_from_conflict_surface(current_graph=current_graph, surface=merged_surface), report

    def _attempt_non_conflicting_graph_merge(
        self,
        *,
        action: str,
        current_graph: dict[str, Any],
        incoming_graph: dict[str, Any],
        expected_revision: str | None,
        expected_etag: str | None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        graph_id = str(current_graph.get("graph_id") or "").strip()
        base_snapshot = self._graph_snapshot_for_revision(
            graph_id=graph_id,
            expected_revision=expected_revision,
            expected_etag=expected_etag,
        )
        if not isinstance(base_snapshot, dict):
            raise self._graph_revision_conflict(
                action=action,
                graph=current_graph,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
                incoming_graph=incoming_graph,
                merge_status="base_revision_unavailable",
            )
        base_graph = self._graph_from_snapshot_ref(base_snapshot, task=task)
        if not isinstance(base_graph, dict):
            raise self._graph_revision_conflict(
                action=action,
                graph=current_graph,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
                incoming_graph=incoming_graph,
                base_snapshot_id=str(base_snapshot.get("snapshot_id") or "").strip() or None,
                merge_status="base_revision_unavailable",
            )
        merged_graph, merge_report = self._merge_non_conflicting_graph_changes(
            base_graph=base_graph,
            current_graph=current_graph,
            incoming_graph=incoming_graph,
        )
        if not isinstance(merged_graph, dict):
            raise self._graph_revision_conflict(
                action=action,
                graph=current_graph,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
                base_graph=base_graph,
                incoming_graph=incoming_graph,
                base_snapshot_id=str(base_snapshot.get("snapshot_id") or "").strip() or None,
                merge_status="overlap_rejected",
                merge_report=merge_report,
            )
        return merged_graph

    def _graph_revision_conflict(
        self,
        *,
        action: str,
        graph: dict[str, Any],
        expected_revision: str | None,
        expected_etag: str | None,
        base_graph: dict[str, Any] | None = None,
        incoming_graph: dict[str, Any] | None = None,
        base_snapshot_id: str | None = None,
        merge_status: str | None = None,
        merge_report: dict[str, Any] | None = None,
    ) -> GraphRevisionConflictError:
        current_revision = self._graph_revision_payload(graph)
        payload = {
            "error": "graph_revision_conflict",
            "action": action,
            "graph_id": str(graph.get("graph_id") or "").strip(),
            "current_revision": current_revision,
            "expected_revision": str(expected_revision or "").strip() or None,
            "expected_etag": str(expected_etag or "").strip() or None,
        }
        if merge_status:
            payload["merge_status"] = str(merge_status or "").strip() or None
        if base_snapshot_id:
            payload["base_snapshot_id"] = str(base_snapshot_id or "").strip() or None
        if isinstance(base_graph, dict) or isinstance(incoming_graph, dict) or isinstance(merge_report, dict):
            payload["edits"] = {
                "base": {
                    "snapshot_id": str(base_snapshot_id or "").strip() or None,
                    "revision": self._graph_revision_payload(base_graph),
                    "graph_document": self._graph_document_evidence(base_graph),
                },
                "current": {
                    "revision": current_revision,
                    "graph_document": self._graph_document_evidence(graph),
                    "changed_paths": list(dict(merge_report or {}).get("current_changed_paths") or []),
                },
                "incoming": {
                    "revision": self._graph_revision_payload(incoming_graph),
                    "graph_document": self._graph_document_evidence(incoming_graph),
                    "changed_paths": list(dict(merge_report or {}).get("incoming_changed_paths") or []),
                },
            }
        if isinstance(merge_report, dict):
            payload["overlapping_edits"] = [
                deepcopy(dict(item))
                for item in list(merge_report.get("overlapping_edits") or [])
                if isinstance(item, dict)
            ][:40]
        return GraphRevisionConflictError(
            f"{action} revision conflict for graph {str(graph.get('graph_id') or '')}.",
            payload=payload,
        )

    def _require_graph_revision_match(
        self,
        *,
        action: str,
        current_graph: dict[str, Any],
        expected_revision: str | None,
        expected_etag: str | None,
        require_token: bool = True,
    ) -> None:
        current_revision = self._graph_revision_payload(current_graph)
        clean_expected_revision = str(expected_revision or "").strip()
        clean_expected_etag = str(expected_etag or "").strip()
        if require_token and not clean_expected_revision and not clean_expected_etag:
            raise ValueError(f"{action} requires expected_revision or expected_etag.")
        if clean_expected_revision and clean_expected_revision != str(current_revision.get("revision_id") or "").strip():
            raise self._graph_revision_conflict(
                action=action,
                graph=current_graph,
                expected_revision=clean_expected_revision,
                expected_etag=clean_expected_etag or None,
            )
        if clean_expected_etag and clean_expected_etag != str(current_revision.get("etag") or "").strip():
            raise self._graph_revision_conflict(
                action=action,
                graph=current_graph,
                expected_revision=clean_expected_revision or None,
                expected_etag=clean_expected_etag,
            )

    @staticmethod
    def _payload_expected_graph_revision(
        payload: dict[str, Any] | None = None,
        *,
        graph: dict[str, Any] | None = None,
    ) -> tuple[str | None, str | None]:
        body = dict(payload or {})
        if isinstance(graph, dict):
            revision = dict(graph.get("graph_revision") or {})
            if not revision and isinstance(graph.get("graph_document"), dict):
                revision = dict(dict(graph.get("graph_document") or {}).get("current_revision") or {})
            expected_revision = str(
                body.get("expected_revision")
                or revision.get("revision_id")
                or ""
            ).strip() or None
            expected_etag = str(
                body.get("expected_etag")
                or revision.get("etag")
                or ""
            ).strip() or None
            return expected_revision, expected_etag
        expected_revision = str(body.get("expected_revision") or "").strip() or None
        expected_etag = str(body.get("expected_etag") or "").strip() or None
        return expected_revision, expected_etag

    def graph_definition(self, graph_id: str | None = None) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        graph_definitions = self._prune_graph_definitions(
            list(task.get("graph_definitions") or []),
            task_id=str(task.get("task_id") or ""),
        )
        if graph_id:
            for item in graph_definitions:
                if str(item.get("graph_id") or "").strip() == str(graph_id or "").strip():
                    return item
            return None
        return graph_definitions[0] if graph_definitions else None

    def graph_snapshot_ref(self, snapshot_id: str | None = None) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        snapshot_refs = [dict(item) for item in list(task.get("graph_snapshot_refs") or []) if isinstance(item, dict)]
        if snapshot_id:
            clean_snapshot_id = str(snapshot_id or "").strip()
            for item in snapshot_refs:
                if str(item.get("snapshot_id") or "").strip() == clean_snapshot_id:
                    return item
            return None
        return snapshot_refs[0] if snapshot_refs else None

    def _snapshot_workspace_root(self) -> Path:
        return self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME / "task-graph" / "snapshots"

    def _snapshot_root_for(self, *, task_id: str, graph_id: str, snapshot_id: str) -> Path:
        return self._snapshot_workspace_root() / str(task_id or "").strip() / str(graph_id or "").strip() / str(snapshot_id or "").strip()

    def _compact_graph_snapshot_ref(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        compact = {
            "snapshot_id": str(snapshot.get("snapshot_id") or "").strip(),
            "task_id": str(snapshot.get("task_id") or "").strip(),
            "graph_id": str(snapshot.get("graph_id") or "").strip(),
            "project_id": str(snapshot.get("project_id") or "").strip() or None,
            "label": str(snapshot.get("label") or "").strip() or None,
            "reason": str(snapshot.get("reason") or "").strip() or None,
            "source_action": str(snapshot.get("source_action") or "").strip() or None,
            "state_version": int(snapshot.get("state_version") or 0),
            "based_on_snapshot_id": str(snapshot.get("based_on_snapshot_id") or "").strip() or None,
            "rollback_source_snapshot_id": str(snapshot.get("rollback_source_snapshot_id") or "").strip() or None,
            "created_at": str(snapshot.get("created_at") or "").strip(),
            "updated_at": str(snapshot.get("updated_at") or "").strip(),
            "artifact_paths": redact_sensitive(dict(snapshot.get("artifact_paths") or {})),
            "summary": redact_sensitive(dict(snapshot.get("summary") or {})),
            "graph_document_evidence": redact_sensitive(dict(snapshot.get("graph_document_evidence") or {})),
        }
        comparison = snapshot.get("comparison")
        if isinstance(comparison, dict):
            compact["comparison"] = redact_sensitive(dict(comparison))
        return compact

    def _prune_graph_snapshot_refs(self, records: list[Any], *, task_id: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        pruned: list[dict[str, Any]] = []
        workspace_root = self._projects.require_workspace_root().resolve()
        for item in records:
            if not isinstance(item, dict):
                continue
            snapshot_id = str(item.get("snapshot_id") or "").strip()
            graph_id = str(item.get("graph_id") or "").strip()
            item_task_id = str(item.get("task_id") or "").strip()
            if not snapshot_id or not graph_id or not item_task_id:
                continue
            if task_id and item_task_id != task_id:
                continue
            if snapshot_id in seen:
                continue
            artifact_paths = item.get("artifact_paths")
            if not isinstance(artifact_paths, dict):
                continue
            try:
                normalized_artifact_paths = {
                    key: str(resolve_under(workspace_root, value).relative_to(workspace_root).as_posix())
                    for key, value in artifact_paths.items()
                    if isinstance(value, str) and str(value).strip()
                }
            except SecurityError:
                continue
            compact = {
                "snapshot_id": snapshot_id,
                "task_id": item_task_id,
                "graph_id": graph_id,
                "project_id": str(item.get("project_id") or "").strip() or None,
                "label": str(item.get("label") or "").strip() or None,
                "reason": str(item.get("reason") or "").strip() or None,
                "source_action": str(item.get("source_action") or "").strip() or None,
                "state_version": int(item.get("state_version") or 0),
                "based_on_snapshot_id": str(item.get("based_on_snapshot_id") or "").strip() or None,
                "rollback_source_snapshot_id": str(item.get("rollback_source_snapshot_id") or "").strip() or None,
                "created_at": str(item.get("created_at") or "").strip(),
                "updated_at": str(item.get("updated_at") or "").strip(),
                "artifact_paths": normalized_artifact_paths,
                "summary": dict(item.get("summary") or {}),
                "graph_document_evidence": dict(item.get("graph_document_evidence") or {}),
            }
            comparison = item.get("comparison")
            if isinstance(comparison, dict):
                compact["comparison"] = dict(comparison)
            seen.add(snapshot_id)
            pruned.append(compact)
        return pruned[:GRAPH_SNAPSHOT_REF_LIMIT]

    def _persist_graph_snapshot_ref(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        compact_ref = self._compact_graph_snapshot_ref(snapshot)
        existing = [
            dict(item)
            for item in list(task.get("graph_snapshot_refs") or [])
            if isinstance(item, dict) and str(item.get("snapshot_id") or "").strip() != str(compact_ref.get("snapshot_id") or "").strip()
        ]
        task["graph_snapshot_refs"] = [compact_ref, *existing][:GRAPH_SNAPSHOT_REF_LIMIT]
        task["updated_at"] = now_iso()
        self._save_task(task)
        return compact_ref

    def _snapshot_workspace_root_candidates(
        self,
        *,
        task: dict[str, Any] | None,
        snapshot: dict[str, Any] | None = None,
    ) -> list[Path]:
        candidates: list[Path] = []
        seen: set[str] = set()

        def add(raw_root: Any) -> None:
            text = str(raw_root or "").strip()
            if not text:
                return
            resolved = Path(text).expanduser().resolve()
            key = str(resolved).lower()
            if key in seen:
                return
            seen.add(key)
            candidates.append(resolved)

        current_project = self._projects.current_project or {}
        add(current_project.get("workspace_root"))
        if isinstance(snapshot, dict):
            add(snapshot.get("workspace_root"))
        if isinstance(task, dict):
            add(task.get("workspace_root"))

        desired_project_ids = {
            str(source.get("project_id") or "").strip()
            for source in (snapshot or {}, task or {})
            if isinstance(source, dict) and str(source.get("project_id") or "").strip()
        }
        for item in list(self._projects.list_recent().get("projects") or []):
            if not isinstance(item, dict):
                continue
            project_id = str(item.get("project_id") or "").strip()
            if desired_project_ids and project_id not in desired_project_ids:
                continue
            add(item.get("workspace_root"))
        return candidates

    def _resolve_snapshot_artifact_path(
        self,
        snapshot: dict[str, Any],
        *,
        key: str,
        task: dict[str, Any] | None,
    ) -> Path:
        artifact_paths = dict(snapshot.get("artifact_paths") or {})
        relative_path = str(artifact_paths.get(key) or "").strip()
        if not relative_path:
            raise ValueError(f"Snapshot artifact path is missing for {key}.")
        fallback: Path | None = None
        for workspace_root in self._snapshot_workspace_root_candidates(task=task, snapshot=snapshot):
            try:
                candidate = resolve_under(workspace_root, relative_path)
            except SecurityError:
                continue
            if fallback is None:
                fallback = candidate
            if candidate.exists():
                return candidate
        if fallback is not None:
            return fallback
        raise ValueError(f"Snapshot artifact path is invalid for {key}.")

    def _snapshot_migration_report(self, *, task_graph: dict[str, Any], orchestration_graph: dict[str, Any]) -> dict[str, Any]:
        migration = dict(orchestration_graph.get("migration") or {})
        return {
            "schema_version": "astrabridge-task-graph-migration-report-v1",
            "generated_at": now_iso(),
            "task_id": str(task_graph.get("task_id") or "").strip(),
            "graph_id": str(task_graph.get("graph_id") or "").strip(),
            "task_graph_schema_version": str(task_graph.get("schema_version") or "").strip(),
            "task_graph_state_version": int(task_graph.get("state_version") or 0),
            "orchestration_graph_schema_version": str(orchestration_graph.get("schema_version") or "").strip(),
            "compiled_task_graph_version": str(migration.get("compiled_task_graph_version") or "").strip() or None,
            "source_kind": str(migration.get("source_kind") or "").strip() or "task_graph_definition",
            "warnings": [str(item) for item in list(migration.get("warnings") or []) if str(item).strip()],
            "node_count": len(list(task_graph.get("nodes") or [])),
            "edge_count": len(list(task_graph.get("edges") or [])),
            "graph_document_evidence": self._graph_document_evidence(task_graph),
        }

    def _record_graph_snapshot(
        self,
        graph_definition: dict[str, Any],
        *,
        label: str | None = None,
        reason: str,
        source_action: str,
        based_on_snapshot_id: str | None = None,
        rollback_source_snapshot_id: str | None = None,
        comparison_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        validated_graph = validate_graph_definition(deepcopy(graph_definition))
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        if not isinstance(validated_graph.get("graph_document"), dict):
            validated_graph["graph_document"] = self._graph_document_from_task_graph(
                validated_graph,
                canonical_graph=orchestration_graph,
            )
        validated_graph["graph_revision"] = deepcopy(
            dict(dict(validated_graph.get("graph_document") or {}).get("current_revision") or {})
        )
        payload_text = serialize_agent_orchestration_graph(orchestration_graph)
        if SECRET_RE.search(payload_text) or DESKTOP_KEY_PATH_RE.search(payload_text):
            raise SecurityError("Secret-like content detected in orchestration graph snapshot payload.")
        task_graph_text = json.dumps(validated_graph, ensure_ascii=False, sort_keys=True)
        if SECRET_RE.search(task_graph_text) or DESKTOP_KEY_PATH_RE.search(task_graph_text):
            raise SecurityError("Secret-like content detected in task graph snapshot payload.")
        snapshot_id = new_id("graph-snapshot")
        created_at = now_iso()
        snapshot_root = self._snapshot_root_for(
            task_id=str(validated_graph.get("task_id") or ""),
            graph_id=str(validated_graph.get("graph_id") or ""),
            snapshot_id=snapshot_id,
        )
        task_graph_path = snapshot_root / "tg.json"
        orchestration_graph_path = snapshot_root / "og.json"
        graph_document_path = snapshot_root / "gd.json"
        migration_report_path = snapshot_root / "mr.json"
        manifest_path = snapshot_root / "manifest.json"
        write_json(task_graph_path, validated_graph)
        write_json(orchestration_graph_path, orchestration_graph)
        write_json(graph_document_path, dict(validated_graph.get("graph_document") or {}))
        write_json(migration_report_path, self._snapshot_migration_report(task_graph=validated_graph, orchestration_graph=orchestration_graph))
        artifact_paths: dict[str, str | None] = {
            "snapshot_dir": snapshot_root.relative_to(self._projects.require_workspace_root()).as_posix(),
            "task_graph_json": task_graph_path.relative_to(self._projects.require_workspace_root()).as_posix(),
            "orchestration_graph_json": orchestration_graph_path.relative_to(self._projects.require_workspace_root()).as_posix(),
            "graph_document_json": graph_document_path.relative_to(self._projects.require_workspace_root()).as_posix(),
            "migration_report_json": migration_report_path.relative_to(self._projects.require_workspace_root()).as_posix(),
            "manifest_json": manifest_path.relative_to(self._projects.require_workspace_root()).as_posix(),
        }
        graph_document_evidence = self._graph_document_evidence(validated_graph)
        comparison_summary: dict[str, Any] | None = None
        if isinstance(comparison_report, dict):
            diff_json_path = snapshot_root / "diff.json"
            diff_md_path = snapshot_root / "diff.md"
            write_json(diff_json_path, redact_sensitive(comparison_report))
            diff_markdown = render_agent_orchestration_report_markdown(comparison_report)
            diff_md_path.write_text(diff_markdown, encoding="utf-8")
            artifact_paths["comparison_diff_json"] = diff_json_path.relative_to(self._projects.require_workspace_root()).as_posix()
            artifact_paths["comparison_diff_md"] = diff_md_path.relative_to(self._projects.require_workspace_root()).as_posix()
            comparison_summary = {
                "status": str(comparison_report.get("status") or "").strip() or "no_change",
                "change_count": int(dict(comparison_report.get("summary") or {}).get("change_count") or 0),
                "change_types": [str(item) for item in list(dict(comparison_report.get("summary") or {}).get("change_types") or []) if str(item).strip()],
            }
        snapshot = {
            "snapshot_id": snapshot_id,
            "task_id": str(validated_graph.get("task_id") or "").strip(),
            "graph_id": str(validated_graph.get("graph_id") or "").strip(),
            "project_id": str(task.get("project_id") or (self._projects.current_project or {}).get("project_id") or "").strip() or None,
            "label": str(label or "").strip() or f"{reason.replace('_', ' ')} @ v{int(validated_graph.get('state_version') or 0)}",
            "reason": reason,
            "source_action": source_action,
            "state_version": int(validated_graph.get("state_version") or 0),
            "based_on_snapshot_id": str(based_on_snapshot_id or "").strip() or None,
            "rollback_source_snapshot_id": str(rollback_source_snapshot_id or "").strip() or None,
            "created_at": created_at,
            "updated_at": created_at,
            "artifact_paths": artifact_paths,
            "summary": {
                "node_count": len(list(validated_graph.get("nodes") or [])),
                "edge_count": len(list(validated_graph.get("edges") or [])),
                "change_count": int((comparison_summary or {}).get("change_count") or 0),
                "change_types": list((comparison_summary or {}).get("change_types") or []),
            },
            "graph_document_evidence": graph_document_evidence,
        }
        if comparison_summary:
            snapshot["comparison"] = comparison_summary
        write_json(manifest_path, redact_sensitive(snapshot))
        return self._persist_graph_snapshot_ref(snapshot)

    def create_graph_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph snapshot payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        snapshot = self._record_graph_snapshot(
            graph,
            label=str(payload.get("label") or "").strip() or None,
            reason=str(payload.get("reason") or "").strip() or "manual_snapshot",
            source_action=str(payload.get("source_action") or "").strip() or "manual_snapshot",
        )
        return {
            "schema_version": "astrabridge-task-graph-snapshot-v1",
            "graph": validate_graph_definition(graph),
            "snapshot": snapshot,
            "task": self.task_view(self.current_task(), compact_graph_runs=True),
        }

    def diff_graph_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph snapshot diff payload must be a dict.")
        snapshot_id = str(payload.get("snapshot_id") or "").strip()
        if not snapshot_id:
            raise ValueError("snapshot_id is required.")
        snapshot = self.graph_snapshot_ref(snapshot_id)
        if not snapshot:
            raise ValueError("Snapshot not found.")
        snapshot_graph_path = self._resolve_snapshot_artifact_path(
            snapshot,
            key="orchestration_graph_json",
            task=task,
        )
        snapshot_task_graph = read_json(
            self._resolve_snapshot_artifact_path(
                snapshot,
                key="task_graph_json",
                task=task,
            ),
            {},
        )
        old_graph = read_json(snapshot_graph_path, {})
        if not isinstance(old_graph, dict):
            raise ValueError("Snapshot orchestration graph is missing.")
        compare_to_snapshot_id = str(payload.get("compare_to_snapshot_id") or "").strip()
        comparison_target_snapshot = self.graph_snapshot_ref(compare_to_snapshot_id) if compare_to_snapshot_id else None
        if compare_to_snapshot_id and not comparison_target_snapshot:
            raise ValueError("Comparison snapshot not found.")
        if comparison_target_snapshot:
            comparison_graph_path = self._resolve_snapshot_artifact_path(
                comparison_target_snapshot,
                key="orchestration_graph_json",
                task=task,
            )
            new_graph = read_json(comparison_graph_path, {})
            comparison_task_graph = read_json(
                self._resolve_snapshot_artifact_path(
                    comparison_target_snapshot,
                    key="task_graph_json",
                    task=task,
                ),
                {},
            )
            compared_label = str(comparison_target_snapshot.get("label") or comparison_target_snapshot.get("snapshot_id") or "").strip() or None
            comparison_mode = "snapshot_to_snapshot"
        else:
            current_graph = self.graph_definition(str(snapshot.get("graph_id") or ""))
            if not current_graph:
                raise ValueError("Current graph not found for snapshot diff.")
            new_graph = self._orchestration_graph_for_task_graph(current_graph)
            comparison_task_graph = current_graph
            compared_label = "current graph"
            comparison_mode = "snapshot_to_current"
        if not isinstance(new_graph, dict):
            raise ValueError("Comparison graph is missing.")
        report = diff_agent_orchestration_graphs(old_graph, new_graph)
        markdown = render_agent_orchestration_report_markdown(report)
        return {
            "schema_version": "astrabridge-task-graph-snapshot-diff-v1",
            "snapshot": snapshot,
            "compared_snapshot": comparison_target_snapshot,
            "compared_label": compared_label,
            "diff_report": report,
            "diff_markdown": markdown,
            "rollback_preview": self._graph_document_rollback_preview(
                snapshot_id=snapshot_id,
                snapshot_graph=snapshot_task_graph if isinstance(snapshot_task_graph, dict) else {},
                current_graph=comparison_task_graph if isinstance(comparison_task_graph, dict) else {},
                comparison_mode=comparison_mode,
            ),
            "task": self.task_view(task, compact_graph_runs=True),
        }

    def rollback_graph_to_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph rollback payload must be a dict.")
        snapshot_id = str(payload.get("snapshot_id") or "").strip()
        if not snapshot_id:
            raise ValueError("snapshot_id is required.")
        snapshot = self.graph_snapshot_ref(snapshot_id)
        if not snapshot:
            raise ValueError("Snapshot not found.")
        task_graph_path = self._resolve_snapshot_artifact_path(
            snapshot,
            key="task_graph_json",
            task=task,
        )
        stored_graph = read_json(task_graph_path, {})
        if not isinstance(stored_graph, dict):
            raise ValueError("Snapshot task graph is missing.")
        current_graph = self.graph_definition(str(snapshot.get("graph_id") or ""))
        if not current_graph:
            raise ValueError("Current graph not found for rollback.")
        ownership_override = self._require_graph_source_ownership_write_allowed(
            action="rollback_graph_to_snapshot",
            payload=payload,
            current_graph=current_graph,
        )
        expected_revision, expected_etag = self._payload_expected_graph_revision(payload)
        try:
            self._require_graph_revision_match(
                action="rollback_graph_to_snapshot",
                current_graph=current_graph,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
                require_token=True,
            )
        except GraphRevisionConflictError:
            stored_graph = self._attempt_non_conflicting_graph_merge(
                action="rollback_graph_to_snapshot",
                current_graph=current_graph,
                incoming_graph=validate_graph_definition(deepcopy(stored_graph)),
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
        current_orchestration = self._orchestration_graph_for_task_graph(current_graph)
        snapshot_orchestration = read_json(
            self._resolve_snapshot_artifact_path(
                snapshot,
                key="orchestration_graph_json",
                task=task,
            ),
            {},
        )
        comparison_report = (
            diff_agent_orchestration_graphs(current_orchestration, snapshot_orchestration)
            if isinstance(snapshot_orchestration, dict)
            else None
        )
        rollback_preview = self._graph_document_rollback_preview(
            snapshot_id=snapshot_id,
            snapshot_graph=stored_graph,
            current_graph=current_graph,
            comparison_mode="snapshot_to_current",
        )
        restored_graph = validate_graph_definition(deepcopy(stored_graph))
        restored_graph["updated_at"] = now_iso()
        restored_graph["state_version"] = max(int(restored_graph.get("state_version") or 0), int(current_graph.get("state_version") or 0) + 1)
        restored_graph["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(
            dict(snapshot_orchestration) if isinstance(snapshot_orchestration, dict) else self._orchestration_graph_for_task_graph(restored_graph),
            task_graph=restored_graph,
        )
        if ownership_override:
            restored_graph["orchestration_graph"] = self._apply_graph_source_ownership(
                dict(restored_graph.get("orchestration_graph") or {}),
                ownership_override,
            )
        saved = self.upsert_graph_definition(restored_graph)
        rollback_snapshot = self._record_graph_snapshot(
            saved,
            reason="rollback_applied",
            source_action="rollback",
            label=str(payload.get("label") or "").strip() or f"Rollback to {str(snapshot.get('label') or snapshot_id)}",
            based_on_snapshot_id=str(snapshot.get("based_on_snapshot_id") or "").strip() or None,
            rollback_source_snapshot_id=snapshot_id,
            comparison_report=comparison_report,
        )
        return {
            "schema_version": "astrabridge-task-graph-rollback-v1",
            "graph": saved,
            "snapshot": rollback_snapshot,
            "rolled_back_to_snapshot": snapshot,
            "rollback_preview": rollback_preview,
            "task": self.task_view(self.current_task()),
        }

    def record_graph_run(self, run: dict[str, Any], *, graph_definition: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        graph = graph_definition
        if graph is None:
            graph = self.graph_definition(str(run.get("graph_id") or ""))
        validated_run = validate_task_graph_run(run, graph_definition=graph, workspace_root=self._projects.require_workspace_root())
        compact_ref = self._compact_graph_run_ref(validated_run)
        compact_ref = self._refresh_graph_run_export_report(compact_ref)
        self.durable_run_store().sync_legacy_run(validated_run)
        existing = [
            dict(item)
            for item in list(task.get("graph_run_refs") or [])
            if isinstance(item, dict) and str(item.get("run_id") or "").strip() != str(compact_ref.get("run_id") or "").strip()
        ]
        task["graph_run_refs"] = [compact_ref, *existing][:GRAPH_RUN_REF_LIMIT]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return compact_ref

    def _refresh_graph_run_export_report(self, run_ref: dict[str, Any]) -> dict[str, Any]:
        return self._graph_run_refs.refresh_graph_run_export_report(run_ref)

    def _graph_run_export_report_path(self, run_ref: dict[str, Any]) -> Path | None:
        return self._graph_run_refs._graph_run_export_report_path(run_ref)

    def _refresh_compact_graph_run_observability(self, run_ref: dict[str, Any]) -> dict[str, Any]:
        return self._graph_run_refs.refresh_compact_graph_run_observability(run_ref)

    def _merge_graph_run_export_ref(self, current: Any, export_ref: dict[str, Any]) -> list[dict[str, Any]]:
        refs = [dict(item) for item in list(current or []) if isinstance(item, dict)]
        filtered = [
            item
            for item in refs
            if str(item.get("artifact_id") or "").strip() != str(export_ref.get("artifact_id") or "").strip()
            and str(item.get("path") or "").strip() != str(export_ref.get("path") or "").strip()
        ]
        filtered.append(export_ref)
        return filtered[:24]

    def graph_run_ref(self, run_id: str | None = None) -> dict[str, Any] | None:
        return self._graph_run_refs.graph_run_ref(run_id)

    def persist_graph_run_ref(self, run_ref: dict[str, Any]) -> dict[str, Any]:
        return self._graph_run_refs.persist_graph_run_ref(run_ref)

    def record_graph_worker(
        self,
        payload: dict[str, Any],
        *,
        graph_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph worker payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        run_id = str(payload.get("run_id") or "").strip()
        node_id = str(payload.get("node_id") or "").strip()
        if not graph_id or not run_id or not node_id:
            raise ValueError("graph_id, run_id, and node_id are required.")
        graph = graph_definition or self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Unknown graph_id for graph worker record.")
        if str(graph.get("task_id") or "") != str(task.get("task_id") or ""):
            raise ValueError("graph worker task_id must match the current task.")
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        if node_id not in node_map:
            raise ValueError(f"Unknown graph worker node_id: {node_id}")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        target_run = None
        for item in graph_run_refs:
            if str(item.get("run_id") or "").strip() == run_id:
                target_run = item
                break
        if target_run is None:
            raise ValueError("Unknown run_id for graph worker record.")

        binding = self._normalize_graph_worker_binding(
            {
                "binding_id": payload.get("binding_id") or new_id("graph-worker"),
                "graph_id": graph_id,
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": payload.get("worker_thread_id"),
                "parent_thread_id": payload.get("parent_thread_id"),
                "spawn_mode": payload.get("spawn_mode"),
                "worker_origin": payload.get("worker_origin"),
                "agent_role": payload.get("agent_role"),
                "agent_nickname": payload.get("agent_nickname"),
                "status": payload.get("status"),
                "execution_backend": payload.get("execution_backend"),
                "artifact_refs": payload.get("artifact_refs"),
                "runtime_contract": payload.get("runtime_contract"),
                "created_at": payload.get("created_at") or now_iso(),
                "updated_at": payload.get("updated_at") or now_iso(),
            },
            graph_id=graph_id,
            run_id=run_id,
            node_ids=set(node_map),
        )
        updated_bindings = [
            dict(item)
            for item in list(target_run.get("worker_bindings") or [])
            if isinstance(item, dict)
            and str(item.get("binding_id") or "").strip() != str(binding.get("binding_id") or "").strip()
            and not (
                str(item.get("node_id") or "").strip() == node_id
                and str(item.get("worker_thread_id") or "").strip() == str(binding.get("worker_thread_id") or "").strip()
            )
        ]
        updated_bindings.insert(0, binding)
        target_run["worker_bindings"] = updated_bindings[:80]
        target_run["worker_count"] = len(target_run["worker_bindings"])
        target_run["updated_at"] = str(binding.get("updated_at") or now_iso())

        task["graph_run_refs"] = [
            target_run if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return {"worker_binding": binding, "run_ref": target_run, "task": self.task_view(task, compact_graph_runs=True)}

    def record_graph_worker_output(
        self,
        payload: dict[str, Any],
        *,
        graph_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph worker output payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        run_id = str(payload.get("run_id") or "").strip()
        node_id = str(payload.get("node_id") or "").strip()
        worker_thread_id = str(payload.get("worker_thread_id") or "").strip()
        if not graph_id or not run_id or not node_id or not worker_thread_id:
            raise ValueError("graph_id, run_id, node_id, and worker_thread_id are required.")

        graph = graph_definition or self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Unknown graph_id for graph worker output.")
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        source_node = node_map.get(node_id)
        if not source_node:
            raise ValueError(f"Unknown graph worker node_id: {node_id}")
        orchestration_graph = self._orchestration_graph_for_task_graph(graph)

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            raise ValueError("Unknown run_id for graph worker output.")
        worker_bindings = [dict(item) for item in list(run_ref.get("worker_bindings") or []) if isinstance(item, dict)]
        binding = next(
            (
                dict(item)
                for item in worker_bindings
                if str(item.get("worker_thread_id") or "").strip() == worker_thread_id
                and str(item.get("node_id") or "").strip() == node_id
            ),
            None,
        )
        if binding is None:
            self.record_graph_worker(
                {
                    "graph_id": graph_id,
                    "run_id": run_id,
                    "node_id": node_id,
                    "worker_thread_id": worker_thread_id,
                    "parent_thread_id": payload.get("parent_thread_id"),
                    "spawn_mode": payload.get("spawn_mode"),
                    "worker_origin": payload.get("worker_origin"),
                    "agent_role": payload.get("agent_role"),
                    "agent_nickname": payload.get("agent_nickname"),
                    "status": "ready",
                    "execution_backend": payload.get("execution_backend"),
                    "runtime_contract": payload.get("runtime_contract"),
                    "created_at": payload.get("created_at") or now_iso(),
                    "updated_at": payload.get("updated_at") or now_iso(),
                },
                graph_definition=graph,
            )
            task = self.current_task() or task
            graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
            run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
            if run_ref is None:
                raise ValueError("Unknown run_id for graph worker output.")
            worker_bindings = [dict(item) for item in list(run_ref.get("worker_bindings") or []) if isinstance(item, dict)]
            binding = next(
                (
                    dict(item)
                    for item in worker_bindings
                    if str(item.get("worker_thread_id") or "").strip() == worker_thread_id
                    and str(item.get("node_id") or "").strip() == node_id
                ),
                None,
            )
        if binding is None:
            raise ValueError("Unknown worker binding for graph worker output.")

        created_at = str(payload.get("created_at") or now_iso()).strip() or now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_root = Path("PRIVATE") / "task-graph" / "workers" / run_id / node_id
        artifact_root = Path(workspace_root) / relative_root
        output_json_path = artifact_root / "output.json"
        summary_md_path = artifact_root / "summary.md"
        output_envelope_json_path = artifact_root / "output-envelope.json"
        handoff_json_path = artifact_root / "handoff.json"
        selected_edge_ids = {
            str(item).strip()
            for item in list(payload.get("selected_edge_ids") or [])
            if str(item or "").strip()
        }
        extra_generated_artifact_refs = [
            deepcopy(dict(item))
            for item in list(payload.get("generated_artifact_refs") or [])
            if isinstance(item, dict)
            and str(item.get("artifact_id") or "").strip()
            and str(item.get("artifact_kind") or "").strip()
            and str(item.get("path") or "").strip()
        ]

        human_summary = _compact_text(redact_sensitive(payload.get("human_summary") or ""), limit=1200)
        machine_result = _sanitize_graph_machine_result(redact_sensitive(payload.get("machine_result") or {}))
        typed_output_values = {}
        for port_id, value in dict(payload.get("typed_output_values") or {}).items():
            clean_port_id = str(port_id or "").strip()
            if not clean_port_id:
                continue
            typed_output_values[clean_port_id] = redact_sensitive(deepcopy(value))
        confidence = payload.get("confidence")
        next_action_hints = [
            _compact_text(redact_sensitive(item), limit=240)
            for item in list(payload.get("next_action_hints") or [])
            if str(item or "").strip()
        ][:8]
        provenance = {
            "worker_thread_id": worker_thread_id,
            "parent_thread_id": str(binding.get("parent_thread_id") or "").strip(),
            "worker_origin": str(binding.get("worker_origin") or "").strip(),
            "spawn_mode": str(binding.get("spawn_mode") or "").strip(),
            "agent_role": str(binding.get("agent_role") or "").strip(),
            "agent_nickname": str(binding.get("agent_nickname") or "").strip(),
        }
        output_contract = dict(source_node.get("output_contract") or {})
        runtime_contract = dict(binding.get("runtime_contract") or {})
        policy_snapshot = dict(run_ref.get("policy_snapshot") or {})
        pricing = dict(policy_snapshot.get("pricing") or {})
        provider_id = str(
            payload.get("provider_id")
            or runtime_contract.get("provider_id")
            or runtime_contract.get("provider")
            or ""
        ).strip()
        model = str(
            payload.get("model")
            or runtime_contract.get("model")
            or runtime_contract.get("model_id")
            or ""
        ).strip()
        raw_usage_signal = payload.get("usage_signal")
        usage_signal = None
        if isinstance(raw_usage_signal, dict):
            if str(raw_usage_signal.get("schema_version") or "").strip() == "astrabridge-usage-signal-v1":
                usage_signal = redact_sensitive(dict(raw_usage_signal))
            else:
                usage_signal = normalize_usage_signal(
                    source="graph_worker_output",
                    provider_id=provider_id or None,
                    model=model or None,
                    usage=raw_usage_signal,
                    pricing=pricing,
                    request_kind="graph_worker_output",
                )
        provider_call_count = _optional_int(payload.get("provider_call_count"))
        tool_call_count = _optional_int(payload.get("tool_call_count"))
        elapsed_ms = _optional_int(payload.get("elapsed_ms"))
        attempt_count = _optional_int(payload.get("attempt_count"))
        retry_count = _optional_int(payload.get("retry_count"))
        if retry_count is None and attempt_count is not None:
            retry_count = max(0, attempt_count - 1)
        durable_run = self.durable_run_store().load_run(run_id, include_events=False)
        trace_id = str(
            dict(durable_run or {}).get("trace_id")
            or run_ref.get("trace_id")
            or f"trace-{run_id}"
        ).strip() or f"trace-{run_id}"
        context_id = str(
            dict(durable_run or {}).get("context_id")
            or run_ref.get("context_id")
            or f"context-{run_id}"
        ).strip() or f"context-{run_id}"

        output_bundle = {
            "schema_version": "astrabridge-task-graph-worker-output-v1",
            "graph_id": graph_id,
            "run_id": run_id,
            "task_id": str(task.get("task_id") or ""),
            "trace_id": trace_id,
            "context_id": context_id,
            "node_id": node_id,
            "worker_thread_id": worker_thread_id,
            "human_summary": human_summary,
            "machine_result": machine_result,
            "typed_output_values": deepcopy(typed_output_values),
            "artifact_refs": self._merge_graph_worker_artifact_refs(
                list(binding.get("artifact_refs") or []),
                extra_generated_artifact_refs,
            ),
            "provenance": provenance,
            "confidence": confidence,
            "next_action_hints": next_action_hints,
            "output_contract": {
                "artifact_only": bool(output_contract.get("artifact_only")),
                "human_summary_required": bool(output_contract.get("human_summary_required")),
                "artifact_outputs": list(output_contract.get("artifact_outputs") or []),
            },
            "provider_id": provider_id or None,
            "model": model or None,
            "status": str(payload.get("status") or "completed").strip() or "completed",
            "attempt_count": attempt_count or 1,
            "retry_count": retry_count or 0,
            "budget": deepcopy(dict(policy_snapshot.get("budget") or {})),
            "created_at": created_at,
        }
        write_json(output_json_path, output_bundle)
        summary_md_path.parent.mkdir(parents=True, exist_ok=True)
        summary_md_path.write_text(self._graph_worker_summary_markdown(output_bundle), encoding="utf-8")

        generated_output_artifact_refs = [
            {
                "artifact_id": f"{worker_thread_id}-output-json",
                "artifact_kind": "structured_json",
                "path": output_json_path.relative_to(workspace_root).as_posix(),
                "status": "ready",
            },
            {
                "artifact_id": f"{worker_thread_id}-summary-md",
                "artifact_kind": "text_report",
                "path": summary_md_path.relative_to(workspace_root).as_posix(),
                "status": "ready",
            },
            *extra_generated_artifact_refs,
        ]
        output_envelope = self._build_graph_worker_output_envelope(
            graph=graph,
            source_node=source_node,
            output_bundle=output_bundle,
            output_contract=output_contract,
            bundle_paths={
                "output_json": output_json_path.relative_to(workspace_root).as_posix(),
                "summary_md": summary_md_path.relative_to(workspace_root).as_posix(),
                "output_envelope_json": output_envelope_json_path.relative_to(workspace_root).as_posix(),
            },
            generated_artifact_refs=generated_output_artifact_refs,
        )
        write_json(output_envelope_json_path, output_envelope)

        downstream_handoffs: list[dict[str, Any]] = []
        if str(output_bundle.get("status") or "").strip() == "completed":
            downstream_handoffs = self._build_graph_worker_handoffs(
                graph=orchestration_graph,
                node_id=node_id,
                run_id=run_id,
                output_bundle=output_bundle,
                output_envelope=output_envelope,
                bundle_paths={
                    "output_json": output_json_path.relative_to(workspace_root).as_posix(),
                    "summary_md": summary_md_path.relative_to(workspace_root).as_posix(),
                    "output_envelope_json": output_envelope_json_path.relative_to(workspace_root).as_posix(),
                },
                generated_artifact_refs=generated_output_artifact_refs,
                selected_edge_ids=selected_edge_ids or None,
            )
        write_json(
            handoff_json_path,
            {
                "schema_version": "astrabridge-task-graph-worker-handoff-v1",
                "graph_id": graph_id,
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "output_envelope_path": output_envelope_json_path.relative_to(workspace_root).as_posix(),
                "downstream_handoffs": downstream_handoffs,
                "created_at": created_at,
            },
        )
        handoff_envelope_artifact_refs = [
            dict(dict(item.get("agent_envelope") or {}).get("artifact_ref") or {})
            for item in downstream_handoffs
            if isinstance(dict(item.get("agent_envelope") or {}).get("artifact_ref"), dict)
        ]

        new_artifact_refs = [
            *generated_output_artifact_refs,
            {
                "artifact_id": f"{worker_thread_id}-output-envelope-json",
                "artifact_kind": "structured_json",
                "path": output_envelope_json_path.relative_to(workspace_root).as_posix(),
                "status": "ready",
            },
            {
                "artifact_id": f"{worker_thread_id}-handoff-json",
                "artifact_kind": "structured_json",
                "path": handoff_json_path.relative_to(workspace_root).as_posix(),
                "status": "ready",
            },
            *handoff_envelope_artifact_refs,
        ]
        compact_output = {
            "human_summary": _compact_text(human_summary, limit=240),
            "machine_result_preview": _compact_text(redact_sensitive(machine_result), limit=240),
            "confidence": confidence,
            "next_action_hints": next_action_hints,
            "artifact_bundle_path": output_json_path.relative_to(workspace_root).as_posix(),
            "output_envelope_path": output_envelope_json_path.relative_to(workspace_root).as_posix(),
        }

        binding["artifact_refs"] = self._merge_graph_worker_artifact_refs(
            list(binding.get("artifact_refs") or []),
            new_artifact_refs,
        )
        binding["output_summary"] = compact_output
        binding["downstream_handoffs"] = downstream_handoffs
        binding["status"] = str(payload.get("status") or "completed")
        binding["updated_at"] = str(payload.get("updated_at") or created_at)
        if usage_signal is not None:
            binding["usage_signal"] = usage_signal
        if provider_call_count is not None:
            binding["provider_call_count"] = provider_call_count
        if tool_call_count is not None:
            binding["tool_call_count"] = tool_call_count
        if elapsed_ms is not None:
            binding["elapsed_ms"] = elapsed_ms
        if attempt_count is not None:
            binding["attempt_count"] = attempt_count
        if retry_count is not None:
            binding["retry_count"] = retry_count

        updated_bindings = [
            binding if str(item.get("binding_id") or "").strip() == str(binding.get("binding_id") or "").strip() else item
            for item in worker_bindings
        ]
        run_ref["worker_bindings"] = updated_bindings[:80]
        run_ref["worker_count"] = len(run_ref["worker_bindings"])
        run_ref["artifact_count"] = int(run_ref.get("artifact_count") or 0) + len(new_artifact_refs)
        run_ref["latest_event_type"] = "node_completed"
        run_ref["latest_event_at"] = binding["updated_at"]
        run_ref["updated_at"] = binding["updated_at"]
        run_ref = self._refresh_compact_graph_run_observability(run_ref)
        run_ref = self._refresh_graph_run_export_report(run_ref)

        task["graph_run_refs"] = [
            run_ref if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return {
            "worker_binding": binding,
            "run_ref": run_ref,
            "task": self.task_view(task, compact_graph_runs=True),
            "artifact_bundle": output_bundle,
        }

    def list_graph_templates(
        self,
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        templates: list[dict[str, Any]] = []
        for template_id in GRAPH_TEMPLATE_IDS:
            graph = validate_graph_definition(load_task_graph_fixture(template_id))
            metadata = dict(GRAPH_TEMPLATE_PRODUCT_METADATA.get(template_id) or {})
            recommended_provider_ids, recommended_model_ids = self._resolve_template_recommended_routes(
                template_id,
                metadata,
                configured_models=configured_models,
            )
            templates.append(
                {
                    "template_id": template_id,
                    "title": str(graph.get("title") or template_id),
                    "summary": GRAPH_TEMPLATE_SUMMARIES.get(template_id, ""),
                    "node_count": len(list(graph.get("nodes") or [])),
                    "edge_count": len(list(graph.get("edges") or [])),
                    "entry_node_ids": list(dict(graph.get("graph_policy") or {}).get("entry_node_ids") or []),
                    "node_kinds": [
                        str(item.get("kind") or "")
                        for item in list(graph.get("nodes") or [])
                        if isinstance(item, dict)
                    ],
                    "preview_graph": {
                        "title": graph.get("title"),
                        "nodes": [
                            {
                                "node_id": item.get("node_id"),
                                "kind": item.get("kind"),
                                "label": item.get("label"),
                                "position": dict(item.get("position") or {}),
                            }
                            for item in list(graph.get("nodes") or [])
                            if isinstance(item, dict)
                        ],
                        "edges": [
                            {
                                "edge_id": item.get("edge_id"),
                                "from_node_id": item.get("from_node_id"),
                                "to_node_id": item.get("to_node_id"),
                                "edge_type": item.get("edge_type"),
                            }
                            for item in list(graph.get("edges") or [])
                            if isinstance(item, dict)
                        ],
                    },
                    "recommended_provider_ids": recommended_provider_ids,
                    "recommended_model_ids": recommended_model_ids,
                    "artifact_expectations": list(metadata.get("artifact_expectations") or []),
                    "validation_hints": list(metadata.get("validation_hints") or []),
                    "constraints": list(metadata.get("constraints") or []),
                }
            )
        return {"schema_version": "astrabridge-task-graph-template-list-v1", "templates": templates}

    def node_type_registry_snapshot(self) -> dict[str, Any]:
        return node_type_registry_snapshot()

    @staticmethod
    def _resolve_template_recommended_model_ids(
        metadata: dict[str, Any],
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        return TaskService._resolve_template_recommended_routes(
            "",
            metadata,
            configured_models=configured_models,
        )[1]

    @staticmethod
    def _safe_provider_model_records(
        provider_id: str,
        configured_models: list[dict[str, Any]] | None = None,
        *,
        require_image_input_verified: bool = False,
    ) -> list[dict[str, Any]]:
        records = provider_model_records(
            provider_id,
            configured_models,
            include_disabled=False,
            include_deprecated=False,
        )
        return [
            dict(item)
            for item in records
            if assess_default_route_verification(
                item,
                require_image_input_verified=require_image_input_verified,
            ).get("verified", False)
        ]

    @staticmethod
    def _resolve_template_recommended_routes(
        template_id: str,
        metadata: dict[str, Any],
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Keep template guidance aligned with the effective model catalog."""
        require_image_input_verified = str(template_id or "").strip() == "multimodal_capability_adapter"
        providers = [
            str(item or "").strip()
            for item in list(metadata.get("recommended_provider_ids") or [])
            if str(item or "").strip()
        ]
        model_ids = [
            str(item or "").strip()
            for item in list(metadata.get("recommended_model_ids") or [])
            if str(item or "").strip()
        ]
        resolved_providers: list[str] = []
        resolved_models: list[str] = []
        for index, provider_id in enumerate(providers):
            candidate = model_ids[index] if index < len(model_ids) else ""
            available = TaskService._safe_provider_model_records(
                provider_id,
                configured_models,
                require_image_input_verified=require_image_input_verified,
            )
            available_native = {
                str(item.get("native_model") or "").strip()
                for item in available
                if str(item.get("native_model") or "").strip()
            }
            if candidate in available_native:
                selected = candidate
            elif available:
                selected = str(available[0].get("native_model") or "").strip()
            else:
                selected = ""
            if provider_id and selected and selected not in resolved_models:
                resolved_providers.append(provider_id)
                resolved_models.append(selected)
        return resolved_providers, resolved_models

    def instantiate_graph_template(
        self,
        template_id: str,
        *,
        title: str | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        graph = deepcopy(load_task_graph_fixture(str(template_id or "").strip()))
        new_graph_id = new_id("graph")
        graph["graph_id"] = new_graph_id
        graph["task_id"] = str(task.get("task_id") or "")
        graph["created_at"] = now_iso()
        graph["updated_at"] = graph["created_at"]
        graph["state_version"] = 1
        if str(title or "").strip():
            graph["title"] = str(title or "").strip()
        for node in list(graph.get("nodes") or []):
            if isinstance(node, dict):
                node["graph_id"] = new_graph_id
        for edge in list(graph.get("edges") or []):
            if isinstance(edge, dict):
                edge["graph_id"] = new_graph_id
        self._apply_template_node_defaults(graph, configured_models=configured_models)
        debug_path = str(os.environ.get("ASTRABRIDGE_DEBUG_TEMPLATE_INSTANTIATE") or "").strip()
        if debug_path:
            write_json(
                Path(debug_path),
                {
                    "template_id": template_id,
                    "configured_models": [
                        {
                            "id": item.get("id"),
                            "provider": item.get("provider"),
                            "native_model": item.get("native_model"),
                        }
                        for item in list(configured_models or [])
                        if isinstance(item, dict)
                    ],
                    "post_apply_nodes": [
                        {
                            "node_id": node.get("node_id"),
                            "provider_id": node.get("provider_id"),
                            "model_id": node.get("model_id"),
                            "reasoning_effort": node.get("reasoning_effort"),
                        }
                        for node in list(graph.get("nodes") or [])
                        if isinstance(node, dict)
                    ],
                },
            )
        graph["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(
            lift_task_graph_to_agent_orchestration_graph(graph),
            task_graph=graph,
        )
        validated = self.upsert_graph_definition(graph)
        return {"graph": validated, "task": self.task_view(self.current_task())}

    def export_graph_for_orchestration_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._graph_mutation.export_graph_for_orchestration_file(payload)

    def _known_model_capabilities_for_graph(
        self,
        orchestration_graph: dict[str, Any],
        *,
        profiles_snapshot: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        profile_records = [dict(item) for item in list((profiles_snapshot or {}).get("profiles") or []) if isinstance(item, dict)]
        return build_known_model_capabilities(
            graph=orchestration_graph,
            configured_models=configured_models,
            profile_records=profile_records,
        )

    def save_graph_definition(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._graph_mutation.save_graph_definition(payload)

    def import_graph_from_orchestration_file(
        self,
        payload: dict[str, Any],
        *,
        profiles_snapshot: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self._graph_mutation.import_graph_from_orchestration_file(
            payload,
            profiles_snapshot=profiles_snapshot,
            configured_models=configured_models,
        )

    def _graph_interop_source_format(self, task_graph: dict[str, Any] | None) -> str:
        return self._graph_mutation._graph_interop_source_format(task_graph)

    def _apply_task_graph_overlays(
        self,
        task_graph: dict[str, Any],
        node_overlays: dict[str, dict[str, Any]] | None,
    ) -> None:
        self._graph_mutation._apply_task_graph_overlays(task_graph, node_overlays)

    def _prepare_graph_for_persist(
        self,
        graph: dict[str, Any],
        *,
        prior_graph: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return self._graph_mutation._prepare_graph_for_persist(graph, prior_graph=prior_graph)

    def _apply_graph_node_payload_to_graph(
        self,
        graph: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        return self._graph_mutation._apply_graph_node_payload_to_graph(graph, payload)

    def _apply_graph_edge_payload_to_graph(
        self,
        graph: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        return self._graph_mutation._apply_graph_edge_payload_to_graph(graph, payload)

    def update_graph_node(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._graph_mutation.update_graph_node(payload)

    def _build_graph_node(
        self,
        graph: dict[str, Any],
        *,
        requested_node_id: str,
        kind: str,
        label: str,
        position: Any,
        configuration: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return self._graph_mutation._build_graph_node(
            graph,
            requested_node_id=requested_node_id,
            kind=kind,
            label=label,
            position=position,
            configuration=configuration,
        )

    def _next_graph_node_id(self, graph: dict[str, Any], kind: str) -> str:
        return self._graph_mutation._next_graph_node_id(graph, kind)

    def _next_graph_node_position(self, graph: dict[str, Any]) -> dict[str, int]:
        return self._graph_mutation._next_graph_node_position(graph)

    def _default_graph_node_label(self, kind: str) -> str:
        return self._graph_mutation._default_graph_node_label(kind)

    @staticmethod
    def _sanitize_graph_token(value: str) -> str:
        return TaskGraphMutationService._sanitize_graph_token(value)

    def update_graph_edge(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._graph_mutation.update_graph_edge(payload)

    def dry_run_graph(
        self,
        payload: dict[str, Any],
        *,
        profiles_snapshot: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph dry-run payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        repaired_graph, repaired = self._repair_stale_template_node_routes(
            graph,
            configured_models=configured_models,
        )
        if repaired:
            graph = self.upsert_graph_definition(repaired_graph)
        validated_graph = validate_graph_definition(graph)
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        known_model_capabilities = self._known_model_capabilities_for_graph(
            orchestration_graph,
            profiles_snapshot=profiles_snapshot,
            configured_models=configured_models,
        )
        compiled_plan = compile_agent_orchestration_graph(orchestration_graph, known_model_capabilities=known_model_capabilities)
        validation_mode = str(payload.get("validation_mode") or "default").strip().lower() or "default"
        require_live_contract = validation_mode == "live"
        import_guard = self._graph_import_execution_guard(
            orchestration_graph,
            require_live_contract=require_live_contract,
        )
        executor_mode = "live_run" if require_live_contract else "fixture_run"
        executor_report = journaled_compiled_plan_executor_capability_report(
            compiled_plan,
            execution_mode=executor_mode,
            workspace_root=self._projects.require_workspace_root(),
            activation_scope=f"task_graph_dry_run:{str(validated_graph.get('graph_id') or '') or 'graph'}:{executor_mode}",
        )
        budget_snapshot = self._graph_run_budget_snapshot(
            graph=validated_graph,
            compiled_plan=compiled_plan,
            run_budget=dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else None,
        )
        workspace_root = self._projects.require_workspace_root()
        run_id = new_id("graph-dry-run")
        created_at = now_iso()
        entry_node_ids = list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or [])
        node_map = {
            str(node.get("node_id") or "").strip(): dict(node)
            for node in list(validated_graph.get("nodes") or [])
            if isinstance(node, dict)
        }
        incoming_edges: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in node_map}
        outgoing_edges: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in node_map}
        for edge in list(validated_graph.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            incoming_edges.setdefault(str(edge.get("to_node_id") or "").strip(), []).append(edge)
            outgoing_edges.setdefault(str(edge.get("from_node_id") or "").strip(), []).append(edge)
        profile_records = [dict(item) for item in list((profiles_snapshot or {}).get("profiles") or []) if isinstance(item, dict)]
        known_routes = {
            (str(item.get("provider_id") or "").strip(), str(item.get("model") or "").strip())
            for item in profile_records
            if str(item.get("provider_id") or "").strip() and str(item.get("model") or "").strip()
        }
        known_providers = {
            str(item.get("provider_id") or "").strip()
            for item in profile_records
            if str(item.get("provider_id") or "").strip()
        }
        node_results: list[dict[str, Any]] = []
        edge_results: list[dict[str, Any]] = []
        node_run_states: list[dict[str, Any]] = []
        warnings: list[str] = []
        blockers: list[str] = []

        for node_id, node in node_map.items():
            result = self._dry_run_node_result(
                node=node,
                entry_node_ids=entry_node_ids,
                incoming_edges=incoming_edges.get(node_id) or [],
                known_routes=known_routes,
                known_providers=known_providers,
                profile_records_present=bool(profile_records),
                require_live_contract=require_live_contract,
            )
            guarded = dict(import_guard.get("node_results") or {}).get(node_id)
            if isinstance(guarded, dict):
                guarded_status = str(guarded.get("status") or "").strip()
                guarded_reasons = [
                    str(item).strip()
                    for item in list(guarded.get("reasons") or [])
                    if str(item or "").strip()
                ]
                if guarded_status == "blocked":
                    result["status"] = "blocked"
                elif guarded_status == "warning":
                    result["status"] = _promote_dry_run_status(str(result.get("status") or "").strip(), "warning")
                merged_node_reasons = [
                    str(item).strip()
                    for item in list(result.get("reasons") or [])
                    if str(item or "").strip()
                ]
                for reason in guarded_reasons:
                    if reason not in merged_node_reasons:
                        merged_node_reasons.append(reason)
                result["reasons"] = merged_node_reasons
            node_results.append(result)
            if result["status"] == "blocked":
                blockers.extend(result["reasons"])
            elif result["status"] == "warning":
                warnings.extend(result["reasons"])
            node_run_states.append(
                {
                    "node_id": node_id,
                    "run_id": run_id,
                    "status": "dry_run_blocked" if result["status"] == "blocked" else "dry_run_passed",
                    "attempt_count": 0,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                    "warnings": list(result["reasons"]) if result["status"] == "warning" else [],
                }
            )

        for edge in list(validated_graph.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            result = self._dry_run_edge_result(edge=edge, node_map=node_map)
            edge_results.append(result)
        node_results_by_id = {
            str(item.get("node_id") or "").strip(): item
            for item in node_results
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        for entry in list(executor_report.get("entries") or []):
            if not isinstance(entry, dict):
                continue
            target = node_results_by_id.get(str(entry.get("node_id") or "").strip())
            if not target:
                continue
            blocking_reasons = [
                str(item).strip()
                for item in list(entry.get("blocking_reasons") or [])
                if str(item or "").strip()
            ]
            if not blocking_reasons:
                continue
            target["status"] = "blocked"
            merged_reasons = [
                str(item).strip()
                for item in list(target.get("reasons") or [])
                if str(item or "").strip()
            ]
            for reason in blocking_reasons:
                if reason not in merged_reasons:
                    merged_reasons.append(reason)
            target["reasons"] = merged_reasons
        node_run_states = [
            {
                **dict(item),
                "status": "dry_run_blocked"
                if str(dict(node_results_by_id.get(str(item.get("node_id") or "").strip()) or {}).get("status") or "").strip()
                == "blocked"
                else "dry_run_passed",
                "warnings": list(
                    dict(node_results_by_id.get(str(item.get("node_id") or "").strip()) or {}).get("reasons")
                    or []
                )
                if str(dict(node_results_by_id.get(str(item.get("node_id") or "").strip()) or {}).get("status") or "").strip()
                == "warning"
                else [],
            }
            for item in node_run_states
        ]
        warnings = []
        blockers = []
        for item in [*node_results, *edge_results]:
            reasons = [
                str(reason).strip()
                for reason in list(dict(item).get("reasons") or [])
                if str(reason or "").strip()
            ]
            if str(dict(item).get("status") or "").strip() == "blocked":
                blockers.extend(reasons)
            elif str(dict(item).get("status") or "").strip() == "warning":
                warnings.extend(reasons)
        guarded_graph_reasons = [
            str(item).strip()
            for item in list(import_guard.get("graph_reasons") or [])
            if str(item or "").strip()
        ]
        if str(import_guard.get("graph_status") or "").strip() == "blocked":
            blockers.extend(guarded_graph_reasons)
        elif str(import_guard.get("graph_status") or "").strip() == "warning":
            warnings.extend(guarded_graph_reasons)
        blockers.extend(
            [
                str(item).strip()
                for item in list(budget_snapshot.get("static_blockers") or [])
                if str(item or "").strip()
            ]
        )

        overall_status = "blocked" if blockers else "warning" if warnings else "pass"
        graph_reasons = blockers if blockers else warnings
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "dry-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        compiled_plan_path = artifact_root / "compiled-plan.json"
        report_payload = {
            "schema_version": TASK_GRAPH_DRY_RUN_SCHEMA_VERSION,
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "overall_status": overall_status,
            "status_counts": _dry_run_status_counts(node_results=node_results, edge_results=edge_results),
            "graph_result": {
                "status": overall_status,
                "reasons": graph_reasons,
            },
            "node_results": node_results,
            "edge_results": edge_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
                "compiled_plan_json": compiled_plan_path.relative_to(workspace_root).as_posix(),
            },
            "compiled_plan_summary": dict(compiled_plan.get("topology") or {}),
            "executor_contract": {
                "execution_mode": executor_mode,
                "registry_fingerprint": str(executor_report.get("current_registry_fingerprint") or ""),
                "compiled_plan_registry_fingerprint": executor_report.get("compiled_plan_registry_fingerprint"),
                "blocker_count": int(executor_report.get("blocker_count") or 0),
            },
            "compatibility_gate": import_guard,
            "budget": budget_snapshot,
        }
        write_json(summary_json_path, report_payload)
        write_json(compiled_plan_path, compiled_plan)
        report_md_path.parent.mkdir(parents=True, exist_ok=True)
        report_md_path.write_text(self._dry_run_report_markdown(report_payload), encoding="utf-8")
        source_node_id = entry_node_ids[0] if entry_node_ids else next(iter(node_map), "graph")
        artifact_refs = [
            {
                "artifact_id": f"{run_id}-summary-json",
                "artifact_kind": "structured_json",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": source_node_id,
                "path": summary_json_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-report-md",
                "artifact_kind": "validation_report",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": source_node_id,
                "path": report_md_path.relative_to(workspace_root).as_posix(),
                "media_type": "text/markdown",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-compiled-plan-json",
                "artifact_kind": "graph_definition",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": source_node_id,
                "path": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
        ]
        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "dry_run_blocked" if overall_status == "blocked" else "dry_run_passed",
            "entry_node_ids": entry_node_ids,
            "node_run_states": node_run_states,
            "artifact_refs": artifact_refs,
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": "Dry-run created.",
                },
                {
                    "event_id": f"{run_id}-started",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_dry_run_started",
                    "created_at": created_at,
                    "summary": "Dry-run validation started.",
                },
                {
                    "event_id": f"{run_id}-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_dry_run_completed",
                    "created_at": created_at,
                    "summary": f"Dry-run completed with overall status {overall_status}.",
                },
            ],
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "dry_run",
                "overall_status": overall_status,
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "max_parallelism": int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or 1),
                "budget": budget_snapshot,
                "executor_contract": {
                    "execution_mode": executor_mode,
                    "registry_fingerprint": str(executor_report.get("current_registry_fingerprint") or ""),
                    "compiled_plan_registry_fingerprint": executor_report.get("compiled_plan_registry_fingerprint"),
                    "blocker_count": int(executor_report.get("blocker_count") or 0),
                },
                "node_mcp_tool_policies": self._compiled_node_mcp_tool_policies(compiled_plan),
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        compact_ref = self.record_graph_run(validated_run, graph_definition=validated_graph)
        return {
            "schema_version": TASK_GRAPH_DRY_RUN_SCHEMA_VERSION,
            "dry_run": {
                **report_payload,
                "run_status": validated_run["status"],
                "artifact_refs": artifact_refs,
                "run_ref": compact_ref,
                "compiled_plan": compiled_plan,
            },
            "graph": validated_graph,
            "task": self.task_view(self.current_task()),
        }

    def execute_fixture_graph(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph fixture-run payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        validated_graph = validate_graph_definition(graph)
        template_id = str(validated_graph.get("template_id") or "").strip()
        execution_mode = str(payload.get("execution_mode") or "default").strip().lower() or "default"
        if execution_mode not in {"default", "cancellable"}:
            raise ValueError("execution_mode must be default or cancellable.")
        if template_id == "fanout_fanin_research":
            if execution_mode == "cancellable":
                return self._start_cancellable_fanout_fixture_graph(payload=payload, task=task, validated_graph=validated_graph)
        return self._execute_compiled_fixture_graph(payload=payload, task=task, validated_graph=validated_graph)

    def _execute_compiled_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
        recovery_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "fixture-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        compiled_plan_path = artifact_root / "compiled-plan.json"
        run_manifest_path = artifact_root / "run-manifest.json"

        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
        )
        executor_report = journaled_compiled_plan_executor_capability_report(
            compiled_plan,
            execution_mode="fixture_run",
            workspace_root=self._projects.require_workspace_root(),
            activation_scope=f"task_graph_fixture_run:{str(validated_graph.get('graph_id') or '') or 'graph'}",
        )
        if not bool(executor_report.get("ok")):
            blockers = [
                str(item).strip()
                for item in list(executor_report.get("blockers") or [])
                if str(item or "").strip()
            ]
            raise ValueError(
                "Fixture task-graph execution is blocked until executor compatibility passes. "
                + (blockers[0] if blockers else "Resolve the executor availability findings first.")
            )
        write_json(compiled_plan_path, compiled_plan)
        budget_snapshot = self._graph_run_budget_snapshot(
            graph=validated_graph,
            compiled_plan=compiled_plan,
            run_budget=dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else None,
        )

        node_behavior_overrides = self._fixture_node_behavior_overrides(payload)
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(validated_graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        compiled_nodes = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(compiled_plan.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        incoming_by_node: dict[str, list[dict[str, Any]]] = {}
        for edge in list(compiled_plan.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            to_node_id = str(edge.get("to_node_id") or "").strip()
            incoming_by_node.setdefault(to_node_id, []).append(dict(edge))

        recovery_context = dict(recovery_context or {})
        preloaded_node_states = {
            str(node_id).strip(): dict(state)
            for node_id, state in dict(recovery_context.get("preloaded_node_states") or {}).items()
            if str(node_id).strip() and isinstance(state, dict)
        }
        node_states: dict[str, dict[str, Any]] = dict(preloaded_node_states)
        node_results: list[dict[str, Any]] = []
        event_refs: list[dict[str, Any]] = [
            {
                "event_id": f"{run_id}-created",
                "run_id": run_id,
                "task_id": validated_graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": "run_created",
                "created_at": created_at,
                "summary": f"{validated_graph['title']} compiled fixture run created.",
            }
        ]
        for node_id in [str(item).strip() for item in list(recovery_context.get("reused_node_ids") or []) if str(item or "").strip()]:
            if node_id not in node_states:
                continue
            node_state = dict(node_states.get(node_id) or {})
            node_results.append(
                {
                    "node_id": node_id,
                    "label": self._graph_node_label(validated_graph, node_id),
                    "outcome": str(node_state.get("outcome") or ""),
                    "status": str(node_state.get("status") or ""),
                    "reasons": list(node_state.get("reasons") or []),
                }
            )
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-reused",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_progress",
                    "created_at": created_at,
                    "summary": f"{self._graph_node_label(validated_graph, node_id)} reused preserved output from source run {str(recovery_context.get('source_run_id') or '').strip()}.",
                    "node_id": node_id,
                    "status": "completed",
                }
            )
        approval_state: dict[str, Any] = {"status": "not_required"}
        terminal_stop = False
        parallel_groups = [dict(group) for group in list(compiled_plan.get("parallel_groups") or []) if isinstance(group, dict)]
        for group_index, group in enumerate(parallel_groups):
            if terminal_stop:
                break
            group_id = str(group.get("group_id") or "").strip() or f"group_{group_index}"
            group_node_ids = [
                str(item).strip()
                for item in list(group.get("node_ids") or [])
                if str(item or "").strip() and str(item).strip() not in node_states
            ]
            group_started_at = self._fixture_offset_iso(created_at, milliseconds=group_index * 1000)
            pending_group_states: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
            for node_index, node_id in enumerate(group_node_ids):
                compiled_node = dict(compiled_nodes.get(str(node_id) or "") or {})
                graph_node = dict(node_map.get(str(node_id) or "") or {})
                label = self._graph_node_label(validated_graph, str(node_id))
                dependency_node_ids = [str(item).strip() for item in list(compiled_node.get("dependency_node_ids") or []) if str(item or "").strip()]
                dependency_states = [dict(node_states.get(dep_id) or {}) for dep_id in dependency_node_ids if isinstance(node_states.get(dep_id), dict)]
                node_state = self._compiled_fixture_node_state(
                    graph_node=graph_node,
                    compiled_node=compiled_node,
                    node_behavior_overrides=node_behavior_overrides,
                    dependency_states=dependency_states,
                    created_at=created_at,
                )
                elapsed_ms = self._compiled_fixture_elapsed_ms(node_state=node_state, node_index=node_index)
                node_state["started_at"] = group_started_at
                node_state["updated_at"] = self._fixture_offset_iso(group_started_at, milliseconds=elapsed_ms)
                node_state["elapsed_ms"] = elapsed_ms
                node_state["parallel_group_id"] = group_id
                node_state["join_mode"] = str(compiled_node.get("join_mode") or "").strip() or None
                node_states[str(node_id)] = node_state
                pending_group_states.append((str(node_id), compiled_node, graph_node, node_state))
            for node_id, compiled_node, graph_node, node_state in pending_group_states:
                label = self._graph_node_label(validated_graph, str(node_id))
                node_results.append(
                    {
                        "node_id": str(node_id),
                        "label": label,
                        "outcome": str(node_state.get("outcome") or ""),
                        "status": str(node_state.get("status") or ""),
                        "reasons": list(node_state.get("reasons") or []),
                    }
                )
                if str(node_state.get("status") or "") == "waiting_on_approval":
                    event_refs.append(
                        {
                            "event_id": f"{run_id}-{node_id}-approval-requested",
                            "run_id": run_id,
                            "task_id": validated_graph["task_id"],
                            "trace_id": f"trace-{run_id}",
                            "event_type": "approval_requested",
                            "created_at": str(node_state.get("updated_at") or group_started_at),
                            "summary": str(node_state.get("summary") or f"{label} is waiting on approval."),
                            "node_id": str(node_id),
                            "parallel_group_id": group_id,
                            "elapsed_ms": int(node_state.get("elapsed_ms") or 0),
                        }
                    )
                    approval_state = self._compiled_fixture_approval_state(
                        graph_node=graph_node,
                        node_id=str(node_id),
                        run_id=run_id,
                        created_at=str(node_state.get("updated_at") or group_started_at),
                    )
                    terminal_stop = True
                    break
                dependency_node_ids = [str(item).strip() for item in list(compiled_node.get("dependency_node_ids") or []) if str(item or "").strip()]
                if dependency_node_ids:
                    dependency_outcomes = [
                        str(dict(node_states.get(dep_id) or {}).get("outcome") or "").strip() or "unknown"
                        for dep_id in dependency_node_ids
                    ]
                    event_refs.append(
                        {
                            "event_id": f"{run_id}-{node_id}-join-ready",
                            "run_id": run_id,
                            "task_id": validated_graph["task_id"],
                            "trace_id": f"trace-{run_id}",
                            "event_type": "node_progress",
                            "created_at": self._fixture_offset_iso(str(node_state.get("started_at") or group_started_at), milliseconds=-50),
                            "summary": (
                                f"{label} satisfied join `{str(compiled_node.get('join_mode') or 'all_required')}` "
                                f"after dependencies {', '.join(dependency_node_ids)} resolved as {', '.join(dependency_outcomes)}."
                            ),
                            "node_id": str(node_id),
                            "parallel_group_id": group_id,
                        }
                    )
                event_refs.append(
                    {
                        "event_id": f"{run_id}-{node_id}-started",
                        "run_id": run_id,
                        "task_id": validated_graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_started",
                        "created_at": str(node_state.get("started_at") or group_started_at),
                        "summary": f"{label} fixture execution started.",
                        "node_id": str(node_id),
                        "parallel_group_id": group_id,
                    }
                )
                event_refs.append(
                    {
                        "event_id": f"{run_id}-{node_id}-{self._compiled_fixture_event_suffix(str(node_state.get('status') or 'completed'))}",
                        "run_id": run_id,
                        "task_id": validated_graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": self._compiled_fixture_event_type(str(node_state.get("status") or "")),
                        "created_at": str(node_state.get("updated_at") or group_started_at),
                        "summary": str(node_state.get("summary") or f"{label} fixture execution finished."),
                        "node_id": str(node_id),
                        "parallel_group_id": group_id,
                        "elapsed_ms": int(node_state.get("elapsed_ms") or 0),
                    }
                )

        unresolved_nodes = [
            node_id
            for node_id in compiled_nodes
            if node_id not in node_states
        ]
        for node_id in unresolved_nodes:
            label = self._graph_node_label(validated_graph, node_id)
            node_states[node_id] = {
                "status": "blocked",
                "outcome": "blocked",
                "reasons": ["Node could not start because upstream dependencies did not produce a runnable handoff."],
                "worker_origin": "fixture_runner",
                "attempt_count": 0,
                "started_at": self._fixture_offset_iso(created_at, milliseconds=len(parallel_groups) * 1000),
                "updated_at": self._fixture_offset_iso(created_at, milliseconds=len(parallel_groups) * 1000),
                "elapsed_ms": 0,
                "summary": f"{label} did not run because upstream dependencies never produced a runnable handoff.",
                "machine_result": {
                    "node_id": node_id,
                    "status": "blocked",
                    "reason": "unrunnable_dependencies",
                },
                "next_action_hints": ["Fix upstream node outcomes or handoff contracts before rerunning this graph."],
            }
            node_results.append(
                {
                    "node_id": node_id,
                    "label": label,
                    "outcome": "blocked",
                    "status": "blocked",
                    "reasons": ["Node could not start because upstream dependencies did not produce a runnable handoff."],
                }
            )
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-blocked-unstarted",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_blocked",
                    "created_at": self._fixture_offset_iso(created_at, milliseconds=len(parallel_groups) * 1000),
                    "summary": f"{label} remained blocked because no runnable upstream dependency set was available.",
                    "node_id": node_id,
                }
            )

        final_updated_at = max(
            [created_at, *[str(dict(state).get("updated_at") or created_at) for state in node_states.values() if isinstance(state, dict)]]
        )
        run_status = self._compiled_fixture_run_status(node_states=node_states, approval_state=approval_state)
        if run_status == "completed":
            event_refs.append(
                {
                    "event_id": f"{run_id}-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_completed",
                    "created_at": final_updated_at,
                    "summary": f"{validated_graph['title']} compiled fixture run completed.",
                }
            )
        elif run_status in {"failed", "partial"}:
            event_refs.append(
                {
                    "event_id": f"{run_id}-terminal",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_failed" if run_status == "failed" else "run_completed",
                    "created_at": final_updated_at,
                    "summary": f"{validated_graph['title']} compiled fixture run finished with status {run_status}.",
                }
            )

        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": run_status,
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
                "compiled_plan_json": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "run_manifest_json": run_manifest_path.relative_to(workspace_root).as_posix(),
            },
            "compiled_plan_summary": dict(compiled_plan.get("topology") or {}),
        }
        if recovery_context:
            report_payload["recovery"] = {
                "recovery_id": str(recovery_context.get("recovery_id") or "").strip(),
                "source_run_id": str(recovery_context.get("source_run_id") or "").strip(),
                "strategy": str(recovery_context.get("strategy") or "").strip(),
                "selected_node_ids": [str(item).strip() for item in list(recovery_context.get("selected_node_ids") or []) if str(item or "").strip()],
                "rerun_node_ids": [str(item).strip() for item in list(recovery_context.get("rerun_node_ids") or []) if str(item or "").strip()],
                "reused_node_ids": [str(item).strip() for item in list(recovery_context.get("reused_node_ids") or []) if str(item or "").strip()],
            }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        node_run_states = [
            {
                "node_id": node_id,
                "run_id": run_id,
                "status": str(state.get("status") or ""),
                "outcome": str(state.get("outcome") or ""),
                "attempt_count": int(state.get("attempt_count") or 0),
                "started_at": str(state.get("started_at") or created_at),
                "updated_at": str(state.get("updated_at") or created_at),
                "worker_origin": state.get("worker_origin"),
                "warnings": list(state.get("reasons") or []),
                "parallel_group_id": state.get("parallel_group_id"),
                "join_mode": state.get("join_mode"),
                "elapsed_ms": int(state.get("elapsed_ms") or 0),
                "reused_from_run_id": str(state.get("reused_from_run_id") or "").strip() or None,
                "worker_thread_id": f"fixture-{node_id}-{run_id}" if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) or str(state.get("status") or "") == "waiting_on_approval" else None,
                "parent_thread_id": str(task.get("active_provider_thread_id") or "") if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) or str(state.get("status") or "") == "waiting_on_approval" else None,
                "spawn_mode": "manual_only" if str(state.get("status") or "") == "waiting_on_approval" else ("isolated_lane" if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) else None),
                "agent_role": str(dict(node_map.get(node_id) or {}).get("kind") or "worker") if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) or str(state.get("status") or "") == "waiting_on_approval" else None,
                "agent_nickname": self._graph_node_label(validated_graph, node_id) if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) or str(state.get("status") or "") == "waiting_on_approval" else None,
                "execution_backend": "human_review" if str(state.get("status") or "") == "waiting_on_approval" else ("fixture_runner" if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) else None),
            }
            for node_id, state in node_states.items()
        ]
        entry_node_ids = [str(item).strip() for item in list(compiled_plan.get("entry_node_ids") or []) if str(item or "").strip()]
        first_entry_node_id = entry_node_ids[0] if entry_node_ids else next(iter(node_map), "")
        last_entry_node_id = entry_node_ids[-1] if entry_node_ids else first_entry_node_id
        artifact_refs = [
            {
                "artifact_id": f"{run_id}-summary-json",
                "artifact_kind": "structured_json",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": first_entry_node_id,
                "path": summary_json_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-report-md",
                "artifact_kind": "run_summary",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": last_entry_node_id,
                "path": report_md_path.relative_to(workspace_root).as_posix(),
                "media_type": "text/markdown",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-compiled-plan-json",
                "artifact_kind": "graph_definition",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": first_entry_node_id,
                "path": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-run-manifest-json",
                "artifact_kind": "structured_json",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": first_entry_node_id,
                "path": run_manifest_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
        ]
        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": run_status,
            "entry_node_ids": list(compiled_plan.get("entry_node_ids") or []),
            "node_run_states": node_run_states,
            "artifact_refs": artifact_refs,
            "event_refs": event_refs,
            "approval_state": approval_state,
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "scheduler": "compiled_graph_mvp",
                "template_id": str(validated_graph.get("template_id") or ""),
                "parallel_group_count": int(dict(compiled_plan.get("topology") or {}).get("parallel_group_count") or 0),
                "max_parallelism": max((len(list(dict(group).get("node_ids") or [])) for group in list(compiled_plan.get("parallel_groups") or [])), default=1),
                "execution_mode": "default",
                "compatibility_shim": False,
                "parallel_group_ids": [str(dict(group).get("group_id") or "").strip() for group in parallel_groups if str(dict(group).get("group_id") or "").strip()],
                "budget": budget_snapshot,
                "executor_contract": {
                    "execution_mode": "fixture_run",
                    "registry_fingerprint": str(executor_report.get("current_registry_fingerprint") or ""),
                    "compiled_plan_registry_fingerprint": executor_report.get("compiled_plan_registry_fingerprint"),
                    "blocker_count": int(executor_report.get("blocker_count") or 0),
                },
                "node_mcp_tool_policies": self._compiled_node_mcp_tool_policies(compiled_plan),
                "skill_ref": deepcopy(dict(payload.get("skill_ref") or {})),
                "resolution_ref": deepcopy(dict(payload.get("resolution_ref") or {})),
                "dry_run_receipt": deepcopy(dict(payload.get("dry_run_receipt") or {})),
                "approval": deepcopy(dict(payload.get("approval") or {})),
                "recovery": (
                    {
                        "recovery_id": str(recovery_context.get("recovery_id") or "").strip(),
                        "source_run_id": str(recovery_context.get("source_run_id") or "").strip(),
                        "strategy": str(recovery_context.get("strategy") or "").strip(),
                        "selected_node_ids": [str(item).strip() for item in list(recovery_context.get("selected_node_ids") or []) if str(item or "").strip()],
                        "rerun_node_ids": [str(item).strip() for item in list(recovery_context.get("rerun_node_ids") or []) if str(item or "").strip()],
                        "reused_node_ids": [str(item).strip() for item in list(recovery_context.get("reused_node_ids") or []) if str(item or "").strip()],
                    }
                    if recovery_context
                    else None
                ),
            },
            "compiled_plan": deepcopy(compiled_plan),
            "created_at": created_at,
            "updated_at": final_updated_at,
            "state_version": 1,
        }
        write_json(run_manifest_path, run)
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        compact_ref = self.record_graph_run(validated_run, graph_definition=validated_graph)

        persisted_worker_bindings: list[dict[str, Any]] = []
        for binding in list(recovery_context.get("preloaded_worker_bindings") or []):
            if not isinstance(binding, dict):
                continue
            cloned = dict(binding)
            cloned["binding_id"] = new_id("graph-worker")
            cloned["run_id"] = run_id
            cloned["reused_from_run_id"] = str(recovery_context.get("source_run_id") or "").strip() or None
            persisted_worker_bindings.append(cloned)
        for node_id, state in node_states.items():
            compiled_node = dict(compiled_nodes.get(node_id) or {})
            status = str(state.get("status") or "")
            if bool(state.get("reused_existing_output")):
                continue
            if status == "waiting_on_approval":
                self.record_graph_worker(
                    {
                        "graph_id": str(validated_graph.get("graph_id") or ""),
                        "run_id": run_id,
                        "node_id": node_id,
                        "worker_thread_id": f"fixture-{node_id}-{run_id}",
                        "parent_thread_id": str(task.get("active_provider_thread_id") or ""),
                        "spawn_mode": "manual_only",
                        "worker_origin": "manual",
                        "agent_role": str(dict(node_map.get(node_id) or {}).get("kind") or "gate"),
                        "agent_nickname": self._graph_node_label(validated_graph, node_id),
                        "status": "waiting_on_approval",
                        "execution_backend": "human_review",
                        "created_at": created_at,
                        "updated_at": created_at,
                    },
                    graph_definition=validated_graph,
                )
                continue
            if not self._compiled_fixture_should_persist_worker_output(compiled_node=compiled_node):
                continue
            output_record = self._record_fixture_worker_output(
                graph=validated_graph,
                run_id=run_id,
                node_id=node_id,
                parent_thread_id=str(task.get("active_provider_thread_id") or ""),
                created_at=str(state.get("started_at") or created_at),
                updated_at=str(state.get("updated_at") or created_at),
                behavior=status if status in {"completed", "blocked", "failed", "partial"} else str(state.get("outcome") or "failed"),
                summary=str(state.get("summary") or ""),
                machine_result=dict(state.get("machine_result") or {}),
                next_action_hints=[str(item).strip() for item in list(state.get("next_action_hints") or []) if str(item or "").strip()],
                status=status,
            )
            if isinstance(output_record, dict) and isinstance(output_record.get("worker_binding"), dict):
                persisted_worker_bindings.append(dict(output_record.get("worker_binding") or {}))

        refreshed_task = self.current_task()
        refreshed_task = self._reconcile_fixture_worker_bindings(
            refreshed_task,
            run_id=run_id,
            preferred_bindings=persisted_worker_bindings,
        ) or refreshed_task
        refreshed_run = self.graph_run_ref(run_id)
        report_payload["run_ref"] = refreshed_run or compact_ref
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": refreshed_run or compact_ref,
                "compiled_plan": compiled_plan,
            },
            "graph": validated_graph,
            "task": self.task_view(refreshed_task, compact_graph_runs=True),
        }

    def _fixture_node_behavior_overrides(self, payload: dict[str, Any]) -> dict[str, str]:
        merged: dict[str, str] = {}
        for key in ("node_behaviors", "branch_behaviors"):
            value = payload.get(key)
            if not isinstance(value, dict):
                continue
            for node_id, behavior in value.items():
                clean_node_id = str(node_id or "").strip()
                clean_behavior = str(behavior or "").strip().lower()
                if not clean_node_id:
                    continue
                if clean_behavior not in {"completed", "blocked", "failed"}:
                    raise ValueError("Fixture node behavior must be completed, blocked, or failed.")
                merged[clean_node_id] = clean_behavior
        return merged

    def _compiled_fixture_node_state(
        self,
        *,
        graph_node: dict[str, Any],
        compiled_node: dict[str, Any],
        node_behavior_overrides: dict[str, str],
        dependency_states: list[dict[str, Any]],
        created_at: str,
    ) -> dict[str, Any]:
        del created_at
        node_id = str(compiled_node.get("node_id") or "")
        label = str(compiled_node.get("label") or node_id)
        approval_gate = dict(graph_node.get("approval_gate") or {})
        review_kind = str(approval_gate.get("review_kind") or approval_gate.get("approval_kind") or compiled_node.get("approval_kind") or "").strip()
        explicit_gate = (
            str(dict(compiled_node.get("execution") or {}).get("spawn_mode") or "").strip() == "manual_only"
            or str(graph_node.get("kind") or "").strip() == "gate"
            or review_kind in {"provider_call_gate", "promotion_gate", "human_gate"}
        )
        if explicit_gate:
            review_kind = review_kind or "human_gate"
            return {
                "status": "waiting_on_approval",
                "outcome": "pending",
                "reasons": [f"{label} requires human approval before execution can continue."],
                "worker_origin": "manual",
                "attempt_count": 1,
                "summary": f"{label} requested human approval for `{review_kind}` before continuing the fixture run.",
                "machine_result": {
                    "node_id": node_id,
                    "status": "waiting_on_approval",
                    "review_kind": review_kind,
                },
                "next_action_hints": ["Resolve the approval request before rerunning or continuing this graph."],
            }

        dependency_outcomes = [str(item.get("outcome") or "").strip() for item in dependency_states]
        successful_dependencies = [
            dict(item)
            for item in dependency_states
            if str(item.get("outcome") or "").strip() in {"passed", "partial"}
        ]
        blocked_dependencies = [
            dict(item)
            for item in dependency_states
            if str(item.get("outcome") or "").strip() in {"blocked", "failed", "skipped"}
        ]

        explicit_behavior = node_behavior_overrides.get(node_id)
        if explicit_behavior:
            behavior = explicit_behavior
        elif dependency_states and not successful_dependencies:
            behavior = "blocked"
        elif dependency_states and blocked_dependencies:
            behavior = "partial"
        else:
            behavior = "completed"

        status = self._fixture_behavior_to_node_status(behavior)
        outcome = "passed" if behavior == "completed" else behavior
        if behavior == "partial":
            outcome = "partial"
        reasons: list[str] = []
        if behavior == "blocked" and dependency_states and not successful_dependencies:
            reasons.append("No upstream dependency produced a runnable artifact handoff for this node.")
        elif behavior in {"blocked", "failed"}:
            reasons.append(f"Fixture execution marked {label} as {behavior}.")
        elif behavior == "partial":
            reasons.append("One or more upstream dependencies did not complete successfully; this node merged the remaining declared artifacts only.")

        consumed_worker_artifacts = [
            str(dict(item.get("machine_result") or {}).get("artifact_bundle_path") or "")
            for item in successful_dependencies
            if str(dict(item.get("machine_result") or {}).get("artifact_bundle_path") or "").strip()
        ]
        if successful_dependencies and not consumed_worker_artifacts:
            consumed_worker_artifacts = [
                f"fixture://{str(dict(item.get('machine_result') or {}).get('node_id') or 'upstream')}"
                for item in successful_dependencies
            ]
        summary = self._compiled_fixture_summary(
            label=label,
            behavior=behavior,
            successful_dependencies=successful_dependencies,
            blocked_dependencies=blocked_dependencies,
        )
        machine_result = {
            "node_id": node_id,
            "status": status,
            "outcome": outcome,
            "dependency_outcomes": dependency_outcomes,
            "dependency_node_ids": list(compiled_node.get("dependency_node_ids") or []),
            "parallel_group_id": compiled_node.get("parallel_group_id"),
        }
        if consumed_worker_artifacts:
            machine_result["consumed_worker_artifacts"] = consumed_worker_artifacts
        machine_result = self._compiled_fixture_machine_result_with_schema_defaults(
            graph_node=graph_node,
            machine_result=machine_result,
            behavior=behavior,
            successful_dependencies=successful_dependencies,
            blocked_dependencies=blocked_dependencies,
        )

        next_action_hints = (
            ["Deliver the declared artifact bundle to downstream nodes according to edge policy."]
            if str(compiled_node.get("outgoing_edge_ids") or "")
            else ["Inspect the latest artifact bundle from the run view."]
        )
        return {
            "status": status,
            "outcome": outcome,
            "reasons": reasons,
            "worker_origin": "fixture_runner",
            "attempt_count": 1 if status not in {"skipped"} else 0,
            "summary": summary,
            "machine_result": machine_result,
            "next_action_hints": next_action_hints,
        }

    def _compiled_fixture_machine_result_with_schema_defaults(
        self,
        *,
        graph_node: dict[str, Any],
        machine_result: dict[str, Any],
        behavior: str,
        successful_dependencies: list[dict[str, Any]],
        blocked_dependencies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        schema = dict(dict(graph_node.get("output_contract") or {}).get("machine_result_schema") or {})
        required_fields = [
            str(item).strip()
            for item in list(schema.get("required") or [])
            if str(item or "").strip()
        ]
        if not required_fields:
            return machine_result
        completed = behavior == "completed"
        defaults: dict[str, Any] = {
            "goal": "Fixture goal",
            "next_nodes": [],
            "plan": ["Inspect task input", "Delegate execution", "Synthesize result"],
            "next_workers": [],
            "questions": ["Fixture question 1"],
            "branches": [],
            "findings": ["Fixture finding"] if completed else [],
            "sources": ["https://example.com/fixture-source"] if completed else [],
            "synthesis": "Fixture synthesis completed." if completed else "Fixture synthesis is partial.",
            "gaps": [] if completed else ["One or more dependencies did not complete successfully."],
            "summary": "Fixture summary completed." if completed else "Fixture summary is partial.",
            "decision": "deliver_summary" if completed else behavior,
            "matrix": ["fixture-provider"],
            "blocked_cases": [] if behavior not in {"blocked", "failed"} else ["Fixture blocked case"],
            "provider_changes": ["fixture-provider-change"],
            "candidate_models": ["fixture-model"],
            "files": ["apps/example.ts"],
            "approach": "Fixture bounded approach.",
            "changed_files": ["apps/example.ts"],
            "failures": [],
            "analysis": "Fixture analysis.",
            "confidence": "fixture",
            "report": "Fixture report completed.",
            "recommendations": ["Review the fixture output bundle."],
            "sections": ["Overview"],
            "entities": ["Fixture entity"],
            "status": str(machine_result.get("status") or behavior),
            "result": "Fixture completed the requested bounded execution path." if completed else f"Fixture ended as {behavior}.",
            "notes": "Fixture review note.",
            "open_questions": [] if completed else ["Dependency gap remains."],
            "consumed_worker_artifacts": [
                str(dict(item.get("machine_result") or {}).get("artifact_bundle_path") or "")
                for item in successful_dependencies
                if str(dict(item.get("machine_result") or {}).get("artifact_bundle_path") or "").strip()
            ],
        }
        if not defaults["consumed_worker_artifacts"]:
            defaults["consumed_worker_artifacts"] = [
                f"fixture://{str(dict(item.get('machine_result') or {}).get('node_id') or 'upstream')}"
                for item in successful_dependencies
            ]
        if blocked_dependencies and not completed and "blocked_cases" in required_fields:
            defaults["blocked_cases"] = [
                str(dict(item.get("machine_result") or {}).get("node_id") or "blocked_dependency")
                for item in blocked_dependencies
            ]
        enriched = dict(machine_result)
        for field in required_fields:
            current = enriched.get(field)
            if current not in (None, "", [], {}):
                continue
            if field in defaults:
                enriched[field] = deepcopy(defaults[field])
                continue
            enriched[field] = [] if field.endswith("s") else f"fixture-{field}"
        return enriched

    @staticmethod
    def _compiled_fixture_summary(
        *,
        label: str,
        behavior: str,
        successful_dependencies: list[dict[str, Any]],
        blocked_dependencies: list[dict[str, Any]],
    ) -> str:
        if behavior == "completed":
            if successful_dependencies:
                return f"{label} consumed the declared upstream artifacts and completed its bounded fixture execution."
            return f"{label} completed its bounded fixture execution."
        if behavior == "partial":
            return f"{label} merged the available declared upstream artifacts after one dependency did not complete successfully."
        if behavior == "blocked" and blocked_dependencies and not successful_dependencies:
            return f"{label} did not run because upstream dependencies never produced a runnable handoff."
        if behavior == "failed":
            return f"{label} failed its bounded fixture execution."
        return f"{label} was marked {behavior} during fixture execution."

    @staticmethod
    def _compiled_fixture_should_persist_worker_output(*, compiled_node: dict[str, Any]) -> bool:
        kind = str(compiled_node.get("kind") or "").strip()
        dependency_node_ids = [str(item).strip() for item in list(compiled_node.get("dependency_node_ids") or []) if str(item or "").strip()]
        outgoing_edge_ids = [str(item).strip() for item in list(compiled_node.get("outgoing_edge_ids") or []) if str(item or "").strip()]
        if kind == "supervisor" and not dependency_node_ids and len(outgoing_edge_ids) > 1:
            return False
        return True

    @staticmethod
    def _compiled_fixture_event_type(status: str) -> str:
        mapping = {
            "completed": "node_completed",
            "partial": "node_completed",
            "blocked": "node_blocked",
            "failed": "node_failed",
            "skipped": "node_blocked",
        }
        return mapping.get(status, "node_completed")

    @staticmethod
    def _compiled_fixture_event_suffix(status: str) -> str:
        mapping = {
            "completed": "completed",
            "partial": "partial",
            "blocked": "blocked",
            "failed": "failed",
            "skipped": "skipped",
        }
        return mapping.get(status, "completed")

    @staticmethod
    def _compiled_fixture_elapsed_ms(*, node_state: dict[str, Any], node_index: int) -> int:
        status = str(node_state.get("status") or "").strip()
        if status == "waiting_on_approval":
            return 40 + (node_index * 10)
        if status == "failed":
            return 160 + (node_index * 20)
        if status == "blocked":
            return 90 + (node_index * 10)
        if status == "partial":
            return 260 + (node_index * 20)
        return 220 + (node_index * 20)

    @staticmethod
    def _fixture_offset_iso(base: str, *, milliseconds: int) -> str:
        try:
            anchor = dt.datetime.fromisoformat(str(base))
        except Exception:
            anchor = dt.datetime.fromisoformat(now_iso())
        return (anchor + dt.timedelta(milliseconds=milliseconds)).isoformat()

    @staticmethod
    def _later_iso(*values: str, plus_ms: int = 0) -> str:
        anchors: list[dt.datetime] = []
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            try:
                anchors.append(dt.datetime.fromisoformat(text))
            except Exception:
                continue
        anchor = max(anchors) if anchors else dt.datetime.fromisoformat(now_iso())
        if plus_ms:
            anchor = anchor + dt.timedelta(milliseconds=plus_ms)
        return anchor.isoformat()

    def _compiled_fixture_approval_state(
        self,
        *,
        graph_node: dict[str, Any],
        node_id: str,
        run_id: str,
        created_at: str,
    ) -> dict[str, Any]:
        approval_gate = dict(graph_node.get("approval_gate") or {})
        review_kind = str(approval_gate.get("review_kind") or approval_gate.get("approval_kind") or "human_gate").strip() or "human_gate"
        reason = str(approval_gate.get("reason") or approval_gate.get("description") or f"{self._graph_node_label({'nodes': [graph_node]}, node_id)} requires human approval before continuing.").strip()
        return {
            "status": "pending",
            "review_kind": review_kind,
            "node_id": node_id,
            "reason": reason,
            "requested_at": created_at,
            "worker_thread_id": f"fixture-{node_id}-{run_id}",
            "allowed_actions": [str(item).strip() for item in list(approval_gate.get("allowed_actions") or []) if str(item or "").strip()] or ["provider_call"],
            "blocked_actions": [str(item).strip() for item in list(approval_gate.get("blocked_actions") or []) if str(item or "").strip()] or ["silent_high_risk_execution"],
        }

    @staticmethod
    def _compiled_fixture_run_status(
        *,
        node_states: dict[str, dict[str, Any]],
        approval_state: dict[str, Any],
    ) -> str:
        if str(approval_state.get("status") or "").strip() == "pending":
            return "paused_for_review"
        statuses = [str(item.get("status") or "").strip() for item in node_states.values()]
        outcomes = [str(item.get("outcome") or "").strip() for item in node_states.values()]
        if "needs_review" in statuses or "needs_review" in outcomes:
            return "needs_review"
        if "failed" in statuses:
            if any(item == "passed" for item in outcomes):
                return "partial"
            return "failed"
        if "cancelled" in statuses or "cancelled" in outcomes:
            if any(item in {"failed", "blocked"} for item in outcomes):
                return "failed"
            return "cancelled"
        if "partial" in statuses or "partial" in outcomes:
            return "partial"
        if all(item == "passed" for item in outcomes if item):
            return "completed"
        if any(item in {"blocked", "failed"} for item in outcomes):
            if any(item == "passed" for item in outcomes):
                return "partial"
            return "failed"
        return "completed"

    def _apply_template_node_defaults(self, graph: dict[str, Any], *, configured_models: list[dict[str, Any]] | None = None) -> None:
        template_id = str(graph.get("template_id") or "").strip()
        raw_template_defaults = self._raw_template_node_defaults(template_id)
        template_defaults = self._resolve_template_node_defaults(
            raw_template_defaults,
            configured_models=configured_models,
        )
        node_ui_hints = {
            "supervisor_worker_synthesizer": {
                "node_supervisor": {"context_policy_preset": "task_digest", "artifact_expectation": "Structured plan", "validation_hint": "Define the worker scope before execution."},
                "node_worker": {"context_policy_preset": "artifact_first", "artifact_expectation": "Bounded worker report", "validation_hint": "Check the worker route before dry-run."},
                "node_synth": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Final run summary", "validation_hint": "Synthesize only declared worker artifacts."},
            },
            "fanout_fanin_research": {
                "node_supervisor": {"context_policy_preset": "task_digest", "artifact_expectation": "Branch brief", "validation_hint": "Keep fan-out branch scopes explicit."},
                "node_research_a": {"context_policy_preset": "artifact_first", "artifact_expectation": "Branch A research note", "validation_hint": "Branch outputs should stay attributable."},
                "node_research_b": {"context_policy_preset": "artifact_first", "artifact_expectation": "Branch B research note", "validation_hint": "Branch outputs should stay attributable."},
                "node_merge": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Merged synthesis", "validation_hint": "Consume only declared branch artifacts."},
            },
            "code_fix_test_review": {
                "node_plan_fix": {"context_policy_preset": "task_digest", "artifact_expectation": "Fix plan", "validation_hint": "List target files before code change."},
                "node_code_fix": {"context_policy_preset": "artifact_first", "artifact_expectation": "Code diff", "validation_hint": "Keep writes bounded to approved files."},
                "node_test": {"context_policy_preset": "artifact_first", "artifact_expectation": "Test report", "validation_hint": "Run tests against the declared diff only."},
                "node_review": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Review report", "validation_hint": "Review outcome should reference test evidence."},
            },
            "provider_update_smoke_gate": {
                "node_discover": {"context_policy_preset": "task_digest", "artifact_expectation": "Provider diff bundle", "validation_hint": "Capture only bounded provider changes."},
                "node_smoke": {"context_policy_preset": "artifact_first", "artifact_expectation": "Smoke matrix", "validation_hint": "Dry-run should surface blocked provider cases."},
                "node_gate": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Promotion decision record", "validation_hint": "Promotion remains gated until review."},
            },
            "document_extract_analyze_report": {
                "node_extract": {"context_policy_preset": "artifact_first", "artifact_expectation": "Document extract", "validation_hint": "Keep source extraction bounded to the declared input."},
                "node_analyze": {"context_policy_preset": "artifact_first", "artifact_expectation": "Structured analysis", "validation_hint": "Analysis must consume only declared extract artifacts."},
                "node_report": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Final report", "validation_hint": "Report output should cite the extract and analysis."},
            },
            "multimodal_capability_adapter": {
                "node_probe_input": {"context_policy_preset": "task_digest", "artifact_expectation": "Capability probe", "validation_hint": "Capture the model's supported input modes before adaptation."},
                "node_adapt_contract": {"context_policy_preset": "artifact_first", "artifact_expectation": "Adapted multimodal contract", "validation_hint": "Keep the fallback contract explicit and bounded."},
                "node_verify_output": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Fallback validation report", "validation_hint": "Verify declared output modes and fallback paths before live use."},
            },
            "custom_blank_graph": {
                "node_start_here": {"context_policy_preset": "task_digest", "artifact_expectation": "Starter graph manifest", "validation_hint": "Rename the seed node and add downstream roles before dry-run."},
            },
        }.get(template_id, {})
        available_by_provider: dict[str, set[str]] = {}
        preferred_by_provider: dict[str, str] = {}
        recommended_provider_ids, recommended_model_ids = self._resolve_template_recommended_routes(
            template_id,
            GRAPH_TEMPLATE_PRODUCT_METADATA.get(template_id) or {},
            configured_models=configured_models,
        )

        def available_models_for(provider_id: str) -> set[str]:
            cached = available_by_provider.get(provider_id)
            if cached is not None:
                return cached
            cached = {
                str(item.get("native_model") or "").strip()
                for item in self._safe_provider_model_records(
                    provider_id,
                    configured_models,
                )
                if str(item.get("native_model") or "").strip()
            }
            available_by_provider[provider_id] = cached
            return cached

        def preferred_model_for(provider_id: str) -> str:
            cached = preferred_by_provider.get(provider_id)
            if cached is not None:
                return cached
            preferred_records = self._safe_provider_model_records(provider_id, configured_models)
            cached = str((preferred_records[0] if preferred_records else {}).get("native_model") or "").strip()
            preferred_by_provider[provider_id] = cached
            return cached

        for node in list(graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or "").strip()
            defaults = dict(template_defaults.get(node_id) or {})
            raw_defaults = dict(raw_template_defaults.get(node_id) or {})
            for key, value in defaults.items():
                if value is not None and not str(node.get(key) or "").strip():
                    node[key] = value
            provider_id = str(node.get("provider_id") or defaults.get("provider_id") or "").strip()
            model_id = str(node.get("model_id") or "").strip()
            if configured_models is not None and provider_id:
                available_models = available_models_for(provider_id)
                preferred_model = preferred_model_for(provider_id)
                if model_id and model_id not in available_models:
                    if preferred_model:
                        node["provider_id"] = provider_id
                        node["model_id"] = preferred_model
                        if not str(node.get("reasoning_effort") or "").strip():
                            node["reasoning_effort"] = str(defaults.get("reasoning_effort") or raw_defaults.get("reasoning_effort") or "").strip() or None
                    else:
                        node["provider_id"] = ""
                        node["model_id"] = ""
            if "permission_mode" not in node:
                node["permission_mode"] = "ask"
            if "collaboration_mode" not in node:
                node["collaboration_mode"] = "default"
            if "execution_backend" not in node:
                node["execution_backend"] = "app_server"
            merged_ui_hints = dict(node.get("ui_hints") or {})
            merged_ui_hints.update(node_ui_hints.get(node_id) or {})
            merged_ui_hints.setdefault("recommended_provider_ids", list(recommended_provider_ids))
            merged_ui_hints.setdefault("recommended_model_ids", list(recommended_model_ids))
            node["ui_hints"] = merged_ui_hints

    def _resolve_template_node_defaults(
        self,
        template_defaults: dict[str, dict[str, Any]],
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        if configured_models is None:
            return {node_id: dict(defaults or {}) for node_id, defaults in template_defaults.items()}
        resolved: dict[str, dict[str, Any]] = {}
        available_by_provider: dict[str, set[str]] = {}
        for node_id, defaults in template_defaults.items():
            normalized = dict(defaults or {})
            provider_id = str(normalized.get("provider_id") or "").strip()
            model_id = str(normalized.get("model_id") or "").strip()
            if provider_id and model_id:
                available_models = available_by_provider.get(provider_id)
                if available_models is None:
                    available_models = {
                        str(item.get("native_model") or "").strip()
                        for item in self._safe_provider_model_records(
                            provider_id,
                            configured_models,
                        )
                        if str(item.get("native_model") or "").strip()
                    }
                    available_by_provider[provider_id] = available_models
                if available_models and model_id not in available_models:
                    preferred_records = self._safe_provider_model_records(provider_id, configured_models)
                    preferred_model = str((preferred_records[0] if preferred_records else {}).get("native_model") or "").strip()
                    if preferred_model:
                        normalized["model_id"] = preferred_model
                    else:
                        normalized.pop("provider_id", None)
                        normalized.pop("model_id", None)
            resolved[node_id] = normalized
        return resolved

    @staticmethod
    def _raw_template_node_defaults(template_id: str) -> dict[str, dict[str, Any]]:
        return {
            "supervisor_worker_synthesizer": {
                "node_supervisor": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_worker": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "high"},
                "node_synth": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "fanout_fanin_research": {
                "node_supervisor": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_research_a": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "high"},
                "node_research_b": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "high"},
                "node_merge": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "code_fix_test_review": {
                "node_plan_fix": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_code_fix": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "high"},
                "node_test": {"provider_id": "deepseek", "model_id": "deepseek-coder", "reasoning_effort": "medium"},
                "node_review": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "provider_update_smoke_gate": {
                "node_discover": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_smoke": {"provider_id": "glm", "model_id": "glm-4.5", "reasoning_effort": "medium"},
            },
            "document_extract_analyze_report": {
                "node_extract": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_analyze": {"provider_id": "glm", "model_id": "glm-4.5", "reasoning_effort": "high"},
                "node_report": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "multimodal_capability_adapter": {
                "node_probe_input": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_adapt_contract": {"provider_id": "glm", "model_id": "glm-4.5", "reasoning_effort": "high"},
                "node_verify_output": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "custom_blank_graph": {
                "node_start_here": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
            },
        }.get(str(template_id or "").strip(), {})

    def _repair_stale_template_node_routes(
        self,
        graph: dict[str, Any],
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        template_id = str(graph.get("template_id") or "").strip()
        raw_defaults = self._raw_template_node_defaults(template_id)
        if not raw_defaults or configured_models is None:
            return dict(graph), False
        resolved_defaults = self._resolve_template_node_defaults(raw_defaults, configured_models=configured_models)
        if not resolved_defaults:
            return dict(graph), False
        repaired = deepcopy(graph)
        changed = False
        for node in list(repaired.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or "").strip()
            raw_default = dict(raw_defaults.get(node_id) or {})
            resolved_default = dict(resolved_defaults.get(node_id) or {})
            if not raw_default or not resolved_default:
                continue
            current_provider = str(node.get("provider_id") or "").strip()
            current_model = str(node.get("model_id") or "").strip()
            if (
                current_provider == str(raw_default.get("provider_id") or "").strip()
                and current_model == str(raw_default.get("model_id") or "").strip()
            ):
                next_provider = str(resolved_default.get("provider_id") or "").strip()
                next_model = str(resolved_default.get("model_id") or "").strip()
                next_effort = str(resolved_default.get("reasoning_effort") or node.get("reasoning_effort") or "").strip()
                if next_provider != current_provider or next_model != current_model:
                    node["provider_id"] = next_provider
                    node["model_id"] = next_model
                    if next_effort:
                        node["reasoning_effort"] = next_effort
                    changed = True
        if changed:
            repaired["updated_at"] = now_iso()
            repaired["state_version"] = int(repaired.get("state_version") or 0) + 1
            repaired["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(
                repaired.get("orchestration_graph"),
                task_graph=repaired,
            )
        return repaired, changed


    def cancel_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph cancel payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        notes = _compact_text(redact_sensitive(payload.get("notes") or ""), limit=600)
        if not run_id:
            raise ValueError("run_id is required.")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            raise ValueError("Unknown run_id for task graph cancellation.")
        if str(run_ref.get("status") or "").strip() not in {"queued", "running", "paused_for_review"}:
            raise ValueError("Only queued, running, or paused_for_review task graph runs can be cancelled.")

        graph_id = str(run_ref.get("graph_id") or "").strip()
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found for the requested cancellation.")

        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        artifact_root = Path(workspace_root) / "PRIVATE" / "task-graph" / "cancelled" / run_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        report_payload = {
            "schema_version": "astrabridge-task-graph-cancelled-run-v1",
            "run_id": run_id,
            "graph_id": graph_id,
            "task_id": str(run_ref.get("task_id") or ""),
            "cancelled_at": created_at,
            "previous_status": str(run_ref.get("status") or ""),
            "notes": notes or None,
            "summary": "Fixture run cancelled before terminal completion.",
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._cancelled_run_report_markdown(report_payload), encoding="utf-8")

        previous_status_counts = dict(run_ref.get("node_status_counts") or {})
        node_status_counts = dict(previous_status_counts)
        cancelled_count = 0
        for active_status in ("running", "waiting_on_dependencies", "waiting_on_artifact", "waiting_on_approval", "ready", "queued"):
            active_count = int(node_status_counts.pop(active_status, 0) or 0)
            if active_count > 0:
                cancelled_count += active_count
        if cancelled_count:
            node_status_counts["cancelled"] = int(node_status_counts.get("cancelled") or 0) + cancelled_count

        timeline_events = [dict(item) for item in list(run_ref.get("timeline_events") or []) if isinstance(item, dict)]
        timeline_events.extend(
            [
                {
                    "event_id": f"{run_id}-cancel-requested",
                    "event_type": "run_cancel_requested",
                    "created_at": created_at,
                    "summary": "Run cancellation was requested from the task graph workspace.",
                    "status": "cancelled",
                },
                {
                    "event_id": f"{run_id}-cancelled",
                    "event_type": "run_cancelled",
                    "created_at": created_at,
                    "summary": "Fixture run was cancelled and preserved a diagnostic report.",
                    "status": "cancelled",
                },
            ]
        )

        diagnostic_refs = [dict(item) for item in list(run_ref.get("diagnostic_refs") or []) if isinstance(item, dict)]
        diagnostic_refs.extend(
            [
                {
                    "artifact_id": f"{run_id}-cancel-summary-json",
                    "artifact_kind": "diagnostic_bundle",
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "status": "ready",
                    "label": "Cancellation summary",
                },
                {
                    "artifact_id": f"{run_id}-cancel-report-md",
                    "artifact_kind": "validation_report",
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "status": "ready",
                    "label": "Cancellation report",
                },
            ]
        )

        updated_bindings: list[dict[str, Any]] = []
        for binding in list(run_ref.get("worker_bindings") or []):
            if not isinstance(binding, dict):
                continue
            normalized_binding = dict(binding)
            if str(normalized_binding.get("status") or "").strip() in {
                "queued",
                "ready",
                "running",
                "waiting_on_dependencies",
                "waiting_on_artifact",
                "waiting_on_approval",
            }:
                normalized_binding["status"] = "cancelled"
                normalized_binding["updated_at"] = created_at
            updated_bindings.append(normalized_binding)

        run_ref["status"] = "cancelled"
        run_ref["updated_at"] = created_at
        run_ref["latest_event_type"] = "run_cancelled"
        run_ref["latest_event_at"] = created_at
        run_ref["event_count"] = len(timeline_events)
        run_ref["node_status_counts"] = node_status_counts
        if updated_bindings:
            run_ref["worker_bindings"] = updated_bindings[:80]
            run_ref["worker_count"] = len(run_ref["worker_bindings"])
        run_ref["timeline_events"] = timeline_events[-24:]
        run_ref["diagnostic_refs"] = self._merge_graph_run_diagnostic_refs(diagnostic_refs)
        if run_ref.get("approval_details") and str((run_ref.get("approval_details") or {}).get("status") or "").strip() == "pending":
            run_ref["approval_state"] = "expired"
            run_ref["approval_details"] = self._compact_graph_run_approval_state(
                {
                    **dict(run_ref.get("approval_details") or {}),
                    "status": "expired",
                    "resolved_at": created_at,
                    "resolution_summary": "Run was cancelled before the pending approval was resolved.",
                    "notes": notes,
                }
            )
        run_ref = self._refresh_compact_graph_run_observability(run_ref)
        run_ref = self._refresh_graph_run_export_report(run_ref)

        full_run = self._load_full_graph_run(run_ref)
        if isinstance(full_run, dict):
            full_run["status"] = "cancelled"
            full_run["updated_at"] = created_at
            full_run["event_refs"] = [
                *[dict(item) for item in list(full_run.get("event_refs") or []) if isinstance(item, dict)],
                {
                    "event_id": f"{run_id}-cancel-requested",
                    "run_id": run_id,
                    "task_id": str(run_ref.get("task_id") or ""),
                    "trace_id": str(full_run.get("trace_id") or run_ref.get("trace_id") or f"trace-{run_id}"),
                    "event_type": "run_cancel_requested",
                    "created_at": created_at,
                    "summary": "Run cancellation was requested from the task graph workspace.",
                },
                {
                    "event_id": f"{run_id}-cancelled",
                    "run_id": run_id,
                    "task_id": str(run_ref.get("task_id") or ""),
                    "trace_id": str(full_run.get("trace_id") or run_ref.get("trace_id") or f"trace-{run_id}"),
                    "event_type": "run_cancelled",
                    "created_at": created_at,
                    "summary": "Fixture run was cancelled and preserved a diagnostic report.",
                },
            ]
            source_node_id = str(list(full_run.get("entry_node_ids") or [""])[0] or "")
            merged_artifact_refs = [
                dict(item)
                for item in list(full_run.get("artifact_refs") or [])
                if isinstance(item, dict)
            ]
            for extra_artifact in (
                {
                    "artifact_id": f"{run_id}-cancel-summary-json",
                    "artifact_kind": "diagnostic_bundle",
                    "task_id": str(run_ref.get("task_id") or ""),
                    "run_id": run_id,
                    "source_node_id": source_node_id,
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-cancel-report-md",
                    "artifact_kind": "validation_report",
                    "task_id": str(run_ref.get("task_id") or ""),
                    "run_id": run_id,
                    "source_node_id": source_node_id,
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
            ):
                merged_artifact_refs = [
                    item
                    for item in merged_artifact_refs
                    if str(item.get("artifact_id") or "").strip() != str(extra_artifact.get("artifact_id") or "").strip()
                    and str(item.get("path") or "").strip() != str(extra_artifact.get("path") or "").strip()
                ]
                merged_artifact_refs.append(extra_artifact)
            full_run["artifact_refs"] = merged_artifact_refs
            node_run_states = []
            for item in list(full_run.get("node_run_states") or []):
                if not isinstance(item, dict):
                    continue
                current = dict(item)
                if str(current.get("status") or "").strip() in {
                    "queued",
                    "ready",
                    "running",
                    "waiting_on_dependencies",
                    "waiting_on_artifact",
                    "waiting_on_approval",
                }:
                    current["status"] = "cancelled"
                    current["outcome"] = "cancelled"
                    current["updated_at"] = created_at
                node_run_states.append(current)
            full_run["node_run_states"] = node_run_states
            if str(dict(full_run.get("approval_state") or {}).get("status") or "").strip() == "pending":
                full_run["approval_state"] = {
                    **dict(full_run.get("approval_state") or {}),
                    "status": "expired",
                    "resolved_at": created_at,
                    "resolution_summary": "Run was cancelled before the pending approval was resolved.",
                    "notes": notes,
                }
            self._persist_full_graph_run(run_ref, full_run)

        task["graph_run_refs"] = [
            run_ref if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        self.durable_run_store().sync_compact_run_ref(run_ref)
        return {
            "cancellation": {
                "run_id": run_id,
                "cancelled_at": created_at,
                "artifact_paths": report_payload["artifact_paths"],
            },
            "run_ref": run_ref,
            "graph": graph,
            "task": self.task_view(task, compact_graph_runs=True),
        }

    def recover_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph recovery payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        strategy = str(payload.get("strategy") or "").strip().lower()
        if not run_id:
            raise ValueError("run_id is required.")
        if strategy not in {"resume_run", "retry_failed_nodes", "rerun_selected_nodes", "partial_execution"}:
            raise ValueError("strategy must be resume_run, retry_failed_nodes, rerun_selected_nodes, or partial_execution.")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        source_run = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if source_run is None:
            raise ValueError("Unknown run_id for task graph recovery.")
        if str(dict(source_run.get("policy_snapshot") or {}).get("mode") or "").strip() != "fixture_run":
            raise ValueError("Only fixture runs currently support recovery.")

        graph_id = str(source_run.get("graph_id") or "").strip()
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found for the requested recovery.")
        validated_graph = validate_graph_definition(graph)
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
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

        full_source_run = self._load_full_graph_run(source_run) or source_run
        prior_node_states = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(full_source_run.get("node_run_states") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        if not prior_node_states:
            raise ValueError("Source run does not expose node_run_states for recovery.")

        selected_node_ids = [str(item).strip() for item in list(payload.get("selected_node_ids") or []) if str(item or "").strip()]
        for node_id in selected_node_ids:
            if node_id not in compiled_nodes:
                raise ValueError(f"Unknown selected_node_id for recovery: {node_id}")

        initial_targets: list[str]
        if strategy == "resume_run":
            initial_targets = [
                node_id
                for node_id, state in prior_node_states.items()
                if str(state.get("status") or "").strip()
                in {"queued", "ready", "running", "waiting_on_dependencies", "waiting_on_artifact", "waiting_on_approval", "cancelled"}
            ]
            if not initial_targets:
                raise ValueError("No resumable node state exists on the source run.")
        elif strategy == "retry_failed_nodes":
            initial_targets = [
                node_id
                for node_id, state in prior_node_states.items()
                if str(state.get("status") or "").strip() in {"failed", "blocked"}
                or str(state.get("outcome") or "").strip() in {"failed", "blocked"}
            ]
            if not initial_targets:
                raise ValueError("No failed or blocked node exists on the source run.")
        else:
            if not selected_node_ids:
                raise ValueError("selected_node_ids are required for rerun_selected_nodes and partial_execution.")
            initial_targets = selected_node_ids

        rerun_node_ids = self._graph_recovery_closure(initial_targets=initial_targets, downstream_by_node=downstream_by_node)
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

        behavior_overrides = self._fixture_node_behavior_overrides(payload)
        for node_id in ordered_rerun_node_ids:
            behavior_overrides.setdefault(node_id, "completed")

        preloaded_node_states: dict[str, dict[str, Any]] = {}
        preloaded_worker_bindings: list[dict[str, Any]] = []
        previous_bindings = [
            dict(item)
            for item in list(source_run.get("worker_bindings") or [])
            if isinstance(item, dict)
        ]
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
                preloaded_worker_bindings.append(binding)

        created_at = now_iso()
        recovery_id = new_id("graph-recovery")
        workspace_root = self._projects.require_workspace_root()
        artifact_root = Path(workspace_root) / "PRIVATE" / "task-graph" / "recovery" / recovery_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        manifest_path = artifact_root / "manifest.json"
        report_md_path = artifact_root / "report.md"
        recovery_manifest = {
            "schema_version": "astrabridge-task-graph-recovery-v1",
            "recovery_id": recovery_id,
            "source_run_id": run_id,
            "graph_id": graph_id,
            "task_id": str(source_run.get("task_id") or ""),
            "strategy": strategy,
            "requested_at": created_at,
            "selected_node_ids": selected_node_ids,
            "initial_target_node_ids": initial_targets,
            "rerun_node_ids": ordered_rerun_node_ids,
            "reused_node_ids": reusable_node_ids,
            "effective_node_behaviors": behavior_overrides,
            "source_run_status": str(source_run.get("status") or ""),
            "artifact_paths": {
                "manifest_json": manifest_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(manifest_path, recovery_manifest)
        report_md_path.write_text(self._graph_recovery_report_markdown(recovery_manifest), encoding="utf-8")

        result = self._execute_compiled_fixture_graph(
            payload={
                **payload,
                "node_behaviors": behavior_overrides,
            },
            task=task,
            validated_graph=validated_graph,
            recovery_context={
                "recovery_id": recovery_id,
                "source_run_id": run_id,
                "strategy": strategy,
                "selected_node_ids": selected_node_ids,
                "rerun_node_ids": ordered_rerun_node_ids,
                "reused_node_ids": reusable_node_ids,
                "preloaded_node_states": preloaded_node_states,
                "preloaded_worker_bindings": preloaded_worker_bindings,
                "recovery_manifest": recovery_manifest,
            },
        )
        return {
            "recovery": recovery_manifest,
            **result,
        }

    def resolve_graph_run_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph approval payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        decision = str(payload.get("decision") or "").strip().lower()
        notes = _compact_text(redact_sensitive(payload.get("notes") or ""), limit=600)
        if not run_id:
            raise ValueError("run_id is required.")
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject.")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            raise ValueError("Unknown run_id for graph approval.")

        approval_details = dict(run_ref.get("approval_details") or {})
        if str(approval_details.get("status") or "").strip() != "pending":
            raise ValueError("This task graph run is not waiting on approval.")

        graph_id = str(run_ref.get("graph_id") or "").strip()
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found for the requested approval.")

        node_id = str(approval_details.get("node_id") or "node_gate").strip() or "node_gate"
        review_kind = str(approval_details.get("review_kind") or "human_gate").strip() or "human_gate"
        graph_node = next(
            (
                dict(item)
                for item in list(graph.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
            ),
            {},
        )
        created_at = self._later_iso(
            str(approval_details.get("requested_at") or "").strip(),
            now_iso(),
            plus_ms=100,
        )
        worker_thread_id = str(approval_details.get("worker_thread_id") or f"fixture-{node_id}-{run_id}").strip()
        binding = next(
            (
                dict(item)
                for item in list(run_ref.get("worker_bindings") or [])
                if isinstance(item, dict)
                and str(item.get("node_id") or "").strip() == node_id
                and str(item.get("worker_thread_id") or "").strip() == worker_thread_id
            ),
            None,
        )
        if binding is None:
            node = next(
                (
                    dict(item)
                    for item in list(graph.get("nodes") or [])
                    if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
                ),
                {},
            )
            self.record_graph_worker(
                {
                    "graph_id": graph_id,
                    "run_id": run_id,
                    "node_id": node_id,
                    "worker_thread_id": worker_thread_id,
                    "parent_thread_id": str(task.get("active_provider_thread_id") or ""),
                    "spawn_mode": "manual_only",
                    "worker_origin": "manual",
                    "agent_role": str(node.get("kind") or "gate"),
                    "agent_nickname": str(node.get("label") or node_id),
                    "status": "waiting_on_approval",
                    "created_at": str(approval_details.get("requested_at") or created_at),
                    "updated_at": str(approval_details.get("requested_at") or created_at),
                },
                graph_definition=graph,
            )
            refreshed = self.graph_run_ref(run_id) or {}
            run_ref = refreshed if isinstance(refreshed, dict) else run_ref

        resolved_status = "completed" if decision == "approve" else "blocked"
        resolved_outcome = "passed" if decision == "approve" else "blocked"
        human_summary = (
            "Manual promotion gate approved the high-risk action after human review."
            if decision == "approve"
            else "Manual promotion gate rejected the high-risk action and kept the run blocked."
        )
        next_actions = (
            ["Promote the provider update using the approved artifact bundle."]
            if decision == "approve"
            else ["Revise the smoke evidence or routing scope before asking for approval again."]
        )
        approval_output_payload = {
            "decision": decision,
            "review_kind": review_kind,
            "notes": notes,
            "approval_reason": approval_details.get("reason"),
        }
        output_ports = self._graph_node_port_map(graph_node, direction="outputs")
        typed_output_values = {}
        first_output_port_id = next(iter(output_ports), "")
        if first_output_port_id:
            typed_output_values[first_output_port_id] = deepcopy(approval_output_payload)
        worker_output = self.record_graph_worker_output(
            {
                "graph_id": graph_id,
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "human_summary": human_summary,
                "machine_result": approval_output_payload,
                "typed_output_values": typed_output_values,
                "confidence": "human_review",
                "next_action_hints": next_actions,
                "status": resolved_status,
                "created_at": created_at,
                "updated_at": created_at,
            },
            graph_definition=graph,
        )

        task = self.current_task() or task
        task = self._reconcile_fixture_worker_bindings(task, run_id=run_id, preferred_bindings=[dict(worker_output.get("worker_binding") or {})]) or task
        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            raise ValueError("Run disappeared while resolving approval.")
        run_policy_mode = str(dict(run_ref.get("policy_snapshot") or {}).get("mode") or "").strip()

        full_run = self._load_full_graph_run(run_ref)
        if run_policy_mode == "live_run" and isinstance(full_run, dict):
            validated_graph = validate_graph_definition(graph)
            orchestration_graph = (
                validated_graph
                if validated_graph.get("schema_registry") is not None
                else self._orchestration_graph_for_task_graph(validated_graph)
            )
            compiled_plan = compile_agent_orchestration_graph(
                orchestration_graph,
                known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
            )
            compiled_node_order = [
                str(item.get("node_id") or "").strip()
                for item in list(compiled_plan.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip()
            ]
            dependency_node_ids_by_node = {
                str(item.get("node_id") or "").strip(): [
                    str(dep_id).strip()
                    for dep_id in list(item.get("dependency_node_ids") or [])
                    if str(dep_id or "").strip()
                ]
                for item in list(compiled_plan.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip()
            }
            approval_state_value = {
                **approval_details,
                "status": "approved" if decision == "approve" else "rejected",
                "decision": decision,
                "notes": notes,
                "resolved_at": created_at,
                "resolution_summary": human_summary,
            }
            full_run["approval_state"] = approval_state_value
            full_run["updated_at"] = created_at
            full_run["worker_bindings"] = [
                deepcopy(dict(item))
                for item in list(run_ref.get("worker_bindings") or [])
                if isinstance(item, dict)
            ]
            node_run_states: list[dict[str, Any]] = []
            for item in list(full_run.get("node_run_states") or []):
                if not isinstance(item, dict):
                    continue
                current = dict(item)
                current_node_id = str(current.get("node_id") or "").strip()
                current_status = str(current.get("status") or "").strip()
                if current_node_id == node_id:
                    current["status"] = resolved_status
                    current["outcome"] = resolved_outcome
                    current["updated_at"] = created_at
                    current["warnings"] = [] if decision == "approve" else [human_summary]
                    current["summary"] = human_summary
                elif decision != "approve" and current_status in {
                    "queued",
                    "ready",
                    "running",
                    "waiting_on_dependencies",
                    "waiting_on_artifact",
                    "waiting_on_approval",
                }:
                    current["status"] = "blocked"
                    current["outcome"] = "blocked"
                    current["updated_at"] = created_at
                    current["warnings"] = [human_summary]
                    current["summary"] = (
                        f"{self._graph_node_label(graph, current_node_id)} remained blocked after approval rejection."
                    )
                node_run_states.append(current)
            if decision == "approve":
                node_state_by_id = {
                    str(item.get("node_id") or "").strip(): item
                    for item in node_run_states
                    if str(item.get("node_id") or "").strip()
                }
                for current_node_id in compiled_node_order:
                    if current_node_id == node_id:
                        continue
                    current = node_state_by_id.get(current_node_id)
                    if not isinstance(current, dict):
                        continue
                    current_status = str(current.get("status") or "").strip()
                    current_outcome = str(current.get("outcome") or "").strip()
                    if current_status in {"completed", "failed", "cancelled", "needs_review"} or current_outcome in {
                        "passed",
                        "failed",
                        "cancelled",
                        "needs_review",
                    }:
                        continue
                    dependency_node_ids = list(dependency_node_ids_by_node.get(current_node_id) or [])
                    if not dependency_node_ids:
                        continue
                    dependency_states = [
                        dict(node_state_by_id.get(dep_id) or {})
                        for dep_id in dependency_node_ids
                        if isinstance(node_state_by_id.get(dep_id), dict)
                    ]
                    if not dependency_states:
                        continue
                    if any(
                        str(item.get("status") or "").strip() in {"failed", "cancelled", "needs_review"}
                        or str(item.get("outcome") or "").strip() in {"failed", "blocked", "cancelled", "needs_review"}
                        for item in dependency_states
                    ):
                        continue
                    if all(str(item.get("status") or "").strip() == "completed" for item in dependency_states):
                        current["status"] = "queued"
                        current["outcome"] = "pending"
                        current["updated_at"] = created_at
                        current["warnings"] = []
                        current["summary"] = (
                            f"{self._graph_node_label(graph, current_node_id)} resumed after approval resolution."
                        )
                    else:
                        current["status"] = "waiting_on_dependencies"
                        current["outcome"] = "pending"
                        current["updated_at"] = created_at
                        current["warnings"] = []
                        current["summary"] = (
                            f"{self._graph_node_label(graph, current_node_id)} is waiting on upstream dependencies after approval resolution."
                        )
            full_run["node_run_states"] = node_run_states

            event_refs = [dict(item) for item in list(full_run.get("event_refs") or []) if isinstance(item, dict)]
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-approval-resolved",
                    "run_id": run_id,
                    "task_id": str(run_ref.get("task_id") or ""),
                    "trace_id": str(full_run.get("trace_id") or run_ref.get("trace_id") or f"trace-{run_id}"),
                    "event_type": "approval_resolved",
                    "created_at": created_at,
                    "summary": human_summary,
                    "node_id": node_id,
                    "status": "approved" if decision == "approve" else "rejected",
                }
            )

            unresolved_after_resolution = [
                dict(item)
                for item in node_run_states
                if str(item.get("status") or "").strip()
                not in {"completed", "failed", "cancelled", "needs_review", "blocked"}
            ]
            if decision == "approve" and unresolved_after_resolution:
                full_run["status"] = "queued"
            elif decision == "approve":
                full_run["status"] = "completed"
                event_refs.append(
                    {
                        "event_id": f"{run_id}-completed-after-approval",
                        "run_id": run_id,
                        "task_id": str(run_ref.get("task_id") or ""),
                        "trace_id": str(full_run.get("trace_id") or run_ref.get("trace_id") or f"trace-{run_id}"),
                        "event_type": "run_completed",
                        "created_at": created_at,
                        "summary": f"{str(graph.get('title') or graph_id)} completed after approval resolution.",
                    }
                )
            else:
                full_run["status"] = "failed"
                event_refs.append(
                    {
                        "event_id": f"{run_id}-failed-after-approval",
                        "run_id": run_id,
                        "task_id": str(run_ref.get("task_id") or ""),
                        "trace_id": str(full_run.get("trace_id") or run_ref.get("trace_id") or f"trace-{run_id}"),
                        "event_type": "run_failed",
                        "created_at": created_at,
                        "summary": f"{str(graph.get('title') or graph_id)} remained blocked after approval rejection.",
                    }
                )
            full_run["event_refs"] = event_refs
            compact_live_ref = self._compact_graph_run_ref(full_run)
            compact_live_ref = self._refresh_graph_run_export_report(compact_live_ref)
            self._persist_full_graph_run(compact_live_ref, full_run)
            task["graph_run_refs"] = [
                compact_live_ref if str(item.get("run_id") or "").strip() == run_id else item
                for item in graph_run_refs
            ]
            task["graph_activity_summary"] = self._graph_activity_summary(task)
            task["updated_at"] = now_iso()
            self._save_task(task)
            self.durable_run_store().sync_compact_run_ref(compact_live_ref)
            return {
                "approval": compact_live_ref.get("approval_details"),
                "run_ref": compact_live_ref,
                "graph": graph,
                "task": self.task_view(task, compact_graph_runs=True),
            }

        self._transition_run_ref_counts(
            run_ref,
            from_status="waiting_on_approval",
            to_status=resolved_status,
            from_outcome="pending",
            to_outcome=resolved_outcome,
        )
        run_ref["status"] = "completed" if decision == "approve" else "failed"
        run_ref["approval_state"] = "approved" if decision == "approve" else "rejected"
        resolved_approval_details = self._compact_graph_run_approval_state(
            {
                **approval_details,
                "status": "approved" if decision == "approve" else "rejected",
                "decision": decision,
                "notes": notes,
                "resolved_at": created_at,
                "resolution_summary": human_summary,
            }
        )
        run_ref["approval_details"] = resolved_approval_details
        run_ref["latest_event_type"] = "run_completed" if decision == "approve" else "run_failed"
        run_ref["latest_event_at"] = created_at
        run_ref["event_count"] = int(run_ref.get("event_count") or 0) + 2
        run_ref["updated_at"] = created_at

        if isinstance(full_run, dict):
            full_run["status"] = run_ref["status"]
            full_run["approval_state"] = {
                **approval_details,
                "status": "approved" if decision == "approve" else "rejected",
                "decision": decision,
                "notes": notes,
                "resolved_at": created_at,
                "resolution_summary": human_summary,
            }
            full_run["updated_at"] = created_at
            node_run_states = []
            for item in list(full_run.get("node_run_states") or []):
                if not isinstance(item, dict):
                    continue
                current = dict(item)
                if str(current.get("node_id") or "").strip() == node_id:
                    current["status"] = resolved_status
                    current["outcome"] = resolved_outcome
                    current["updated_at"] = created_at
                    current["warnings"] = [] if decision == "approve" else [human_summary]
                node_run_states.append(current)
            full_run["node_run_states"] = node_run_states
            event_refs = [dict(item) for item in list(full_run.get("event_refs") or []) if isinstance(item, dict)]
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-approval-resolved",
                    "run_id": run_id,
                    "task_id": str(run_ref.get("task_id") or ""),
                    "trace_id": str(full_run.get("trace_id") or run_ref.get("trace_id") or f"trace-{run_id}"),
                    "event_type": "approval_resolved",
                    "created_at": created_at,
                    "summary": human_summary,
                    "node_id": node_id,
                    "status": "approved" if decision == "approve" else "rejected",
                }
            )
            if decision == "approve":
                event_refs.append(
                    {
                        "event_id": f"{run_id}-completed-after-approval",
                        "run_id": run_id,
                        "task_id": str(run_ref.get("task_id") or ""),
                        "trace_id": str(full_run.get("trace_id") or run_ref.get("trace_id") or f"trace-{run_id}"),
                        "event_type": "run_completed",
                        "created_at": created_at,
                        "summary": f"{str(graph.get('title') or graph_id)} completed after approval resolution.",
                    }
                )
            else:
                event_refs.append(
                    {
                        "event_id": f"{run_id}-failed-after-approval",
                        "run_id": run_id,
                        "task_id": str(run_ref.get("task_id") or ""),
                        "trace_id": str(full_run.get("trace_id") or run_ref.get("trace_id") or f"trace-{run_id}"),
                        "event_type": "run_failed",
                        "created_at": created_at,
                        "summary": f"{str(graph.get('title') or graph_id)} remained blocked after approval rejection.",
                    }
                )
            full_run["event_refs"] = event_refs
            self._persist_full_graph_run(run_ref, full_run)

        task["graph_run_refs"] = [
            run_ref if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return {
            "approval": run_ref["approval_details"],
            "run_ref": run_ref,
            "graph": graph,
            "task": self.task_view(task, compact_graph_runs=True),
        }

    def _execute_fanout_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:

        branch_behaviors_raw = payload.get("branch_behaviors")
        branch_behaviors = dict(branch_behaviors_raw) if isinstance(branch_behaviors_raw, dict) else {}
        branch_a_behavior = str(branch_behaviors.get("node_research_a") or "completed").strip().lower() or "completed"
        branch_b_behavior = str(branch_behaviors.get("node_research_b") or "blocked").strip().lower() or "blocked"
        for behavior in (branch_a_behavior, branch_b_behavior):
            if behavior not in {"completed", "blocked", "failed"}:
                raise ValueError("Fixture branch behavior must be completed, blocked, or failed.")

        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "fixture-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        artifact_root.mkdir(parents=True, exist_ok=True)

        node_states = self._fanout_fixture_node_states(
            behaviors={
                "node_research_a": branch_a_behavior,
                "node_research_b": branch_b_behavior,
            }
        )
        node_results = [
            {
                "node_id": node_id,
                "label": self._graph_node_label(validated_graph, node_id),
                "outcome": state["outcome"],
                "status": state["status"],
                "reasons": list(state["reasons"]),
            }
            for node_id, state in node_states.items()
        ]

        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": self._fanout_fixture_run_status(node_states),
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": report_payload["run_status"],
            "entry_node_ids": list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
            "node_run_states": [
                {
                    "node_id": node_id,
                    "run_id": run_id,
                    "status": state["status"],
                    "outcome": state["outcome"],
                    "attempt_count": int(state.get("attempt_count") or 1),
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": state.get("worker_origin"),
                    "warnings": list(state["reasons"]) if state["outcome"] in {"blocked", "partial"} else [],
                }
                for node_id, state in node_states.items()
            ],
            "artifact_refs": [
                {
                    "artifact_id": f"{run_id}-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-report-md",
                    "artifact_kind": "run_summary",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_merge",
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
            ],
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": "Fixture run created.",
                },
                {
                    "event_id": f"{run_id}-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_completed" if report_payload["run_status"] == "completed" else "run_failed",
                    "created_at": created_at,
                    "summary": f"Fixture run completed with status {report_payload['run_status']}.",
                },
            ],
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "topology": "fanout_fanin_research",
                "branch_behaviors": {
                    "node_research_a": branch_a_behavior,
                    "node_research_b": branch_b_behavior,
                },
                "node_mcp_tool_policies": self._compiled_node_mcp_tool_policies(compiled_plan),
                "skill_ref": deepcopy(dict(payload.get("skill_ref") or {})),
                "resolution_ref": deepcopy(dict(payload.get("resolution_ref") or {})),
                "dry_run_receipt": deepcopy(dict(payload.get("dry_run_receipt") or {})),
                "approval": deepcopy(dict(payload.get("approval") or {})),
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        self.record_graph_run(validated_run, graph_definition=validated_graph)

        self._record_fixture_worker_output(
            graph=validated_graph,
            run_id=run_id,
            node_id="node_research_a",
            parent_thread_id=str(task.get("active_provider_thread_id") or ""),
            created_at=created_at,
            behavior=branch_a_behavior,
            summary="Branch A researched the first question set and produced bounded source notes.",
            machine_result={
                "findings": ["Branch A finding 1", "Branch A finding 2"],
                "sources": ["https://example.com/source-a"],
            },
            next_action_hints=["Merge Branch A artifacts into the synthesizer input."],
        )
        self._record_fixture_worker_output(
            graph=validated_graph,
            run_id=run_id,
            node_id="node_research_b",
            parent_thread_id=str(task.get("active_provider_thread_id") or ""),
            created_at=created_at,
            behavior=branch_b_behavior,
            summary="Branch B hit a bounded fixture issue and returned a diagnosable output instead of raw history.",
            machine_result={
                "findings": [] if branch_b_behavior != "completed" else ["Branch B finding 1"],
                "sources": [] if branch_b_behavior != "completed" else ["https://example.com/source-b"],
                "blocked_cases": ["Fixture branch B blocked"] if branch_b_behavior == "blocked" else [],
            },
            next_action_hints=["Continue with Branch A artifacts even if Branch B is blocked."],
        )
        merge_state = node_states["node_merge"]
        if merge_state["status"] != "skipped":
            refreshed_run = self.graph_run_ref(run_id) or {}
            branch_bindings = [
                dict(item)
                for item in list(refreshed_run.get("worker_bindings") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() in {"node_research_a", "node_research_b"}
            ]
            consumed_artifacts = [
                str(artifact.get("path") or "").strip()
                for binding in branch_bindings
                for artifact in list(binding.get("artifact_refs") or [])
                if isinstance(artifact, dict) and str(artifact.get("path") or "").strip()
            ]
            consumed_summaries = [
                str((binding.get("output_summary") or {}).get("artifact_bundle_path") or "").strip()
                for binding in branch_bindings
                if isinstance(binding.get("output_summary"), dict)
                and str((binding.get("output_summary") or {}).get("artifact_bundle_path") or "").strip()
            ]
            self._record_fixture_worker_output(
                graph=validated_graph,
                run_id=run_id,
                node_id="node_merge",
                parent_thread_id=str(task.get("active_provider_thread_id") or ""),
                created_at=created_at,
                behavior="completed" if merge_state["outcome"] == "passed" else "blocked",
                summary="Synthesizer consumed only declared artifact bundles and structured summaries from completed or partial worker branches.",
                machine_result={
                    "synthesis": "Merged fan-out findings into one bounded summary.",
                    "gaps": ["Branch B unavailable"] if branch_b_behavior != "completed" else [],
                    "consumed_worker_artifacts": consumed_artifacts,
                    "consumed_worker_summaries": consumed_summaries,
                },
                next_action_hints=["Review the merged artifact bundle from the run panel."],
                status=merge_state["status"],
            )

        refreshed_task = self.current_task()
        refreshed_run = self.graph_run_ref(run_id)
        report_payload["run_ref"] = refreshed_run
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": refreshed_run,
            },
            "graph": validated_graph,
            "task": self.task_view(refreshed_task, compact_graph_runs=True),
        }

    def _start_cancellable_fanout_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        artifact_root = Path(workspace_root) / "PRIVATE" / "task-graph" / "fixture-run" / run_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        compiled_plan_path = artifact_root / "compiled-plan.json"
        run_manifest_path = artifact_root / "run-manifest.json"
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
        )
        write_json(compiled_plan_path, compiled_plan)
        budget_snapshot = self._graph_run_budget_snapshot(
            graph=validated_graph,
            compiled_plan=compiled_plan,
            run_budget=dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else None,
        )
        node_results = [
            {
                "node_id": "node_supervisor",
                "label": self._graph_node_label(validated_graph, "node_supervisor"),
                "outcome": "passed",
                "status": "completed",
                "reasons": [],
            },
            {
                "node_id": "node_research_a",
                "label": self._graph_node_label(validated_graph, "node_research_a"),
                "outcome": "pending",
                "status": "running",
                "reasons": ["Branch A fixture run is still active and can be cancelled to test recovery diagnostics."],
            },
            {
                "node_id": "node_research_b",
                "label": self._graph_node_label(validated_graph, "node_research_b"),
                "outcome": "pending",
                "status": "waiting_on_dependencies",
                "reasons": ["Branch B is waiting on the primary branch artifact bundle."],
            },
            {
                "node_id": "node_merge",
                "label": self._graph_node_label(validated_graph, "node_merge"),
                "outcome": "pending",
                "status": "waiting_on_dependencies",
                "reasons": ["Synthesizer is waiting for a completed branch output."],
            },
        ]
        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": "running",
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
                "compiled_plan_json": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "run_manifest_json": run_manifest_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "running",
            "entry_node_ids": list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
            "node_run_states": [
                {
                    "node_id": "node_supervisor",
                    "run_id": run_id,
                    "status": "completed",
                    "outcome": "passed",
                    "attempt_count": 1,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                },
                {
                    "node_id": "node_research_a",
                    "run_id": run_id,
                    "status": "running",
                    "outcome": "pending",
                    "attempt_count": 1,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                },
                {
                    "node_id": "node_research_b",
                    "run_id": run_id,
                    "status": "waiting_on_dependencies",
                    "outcome": "pending",
                    "attempt_count": 0,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                },
                {
                    "node_id": "node_merge",
                    "run_id": run_id,
                    "status": "waiting_on_dependencies",
                    "outcome": "pending",
                    "attempt_count": 0,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                },
            ],
            "artifact_refs": [
                {
                    "artifact_id": f"{run_id}-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-report-md",
                    "artifact_kind": "run_summary",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-compiled-plan-json",
                    "artifact_kind": "graph_definition",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": compiled_plan_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-run-manifest-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": run_manifest_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
            ],
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": "Cancellable fan-out fixture run created.",
                },
                {
                    "event_id": f"{run_id}-supervisor-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_completed",
                    "created_at": created_at,
                    "summary": "Supervisor seeded the branch plan and declared the expected artifact bundle.",
                    "node_id": "node_supervisor",
                },
                {
                    "event_id": f"{run_id}-branch-a-started",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_started",
                    "created_at": created_at,
                    "summary": "Branch A started its bounded research fixture run.",
                    "node_id": "node_research_a",
                },
                {
                    "event_id": f"{run_id}-branch-a-progress",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_progress",
                    "created_at": created_at,
                    "summary": "Fixture run is still active and can be cancelled to test recovery diagnostics.",
                    "node_id": "node_research_a",
                },
            ],
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "topology": "fanout_fanin_research",
                "execution_mode": "cancellable",
                "max_parallelism": int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or 1),
                "budget": budget_snapshot,
                "node_mcp_tool_policies": self._compiled_node_mcp_tool_policies(compiled_plan),
                "skill_ref": deepcopy(dict(payload.get("skill_ref") or {})),
                "resolution_ref": deepcopy(dict(payload.get("resolution_ref") or {})),
                "dry_run_receipt": deepcopy(dict(payload.get("dry_run_receipt") or {})),
                "approval": deepcopy(dict(payload.get("approval") or {})),
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        write_json(run_manifest_path, run)
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        compact_ref = self.record_graph_run(validated_run, graph_definition=validated_graph)
        report_payload["run_ref"] = compact_ref
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": compact_ref,
            },
            "graph": validated_graph,
            "task": self.task_view(self.current_task(), compact_graph_runs=True),
        }

    def _execute_provider_gate_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "fixture-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        artifact_root.mkdir(parents=True, exist_ok=True)
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
        )
        budget_snapshot = self._graph_run_budget_snapshot(
            graph=validated_graph,
            compiled_plan=compiled_plan,
            run_budget=dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else None,
        )

        node_states = {
            "node_discover": {
                "status": "completed",
                "outcome": "passed",
                "reasons": [],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_smoke": {
                "status": "completed",
                "outcome": "passed",
                "reasons": [],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_gate": {
                "status": "waiting_on_approval",
                "outcome": "pending",
                "reasons": ["High-risk provider promotion is blocked until a human approves the gate."],
                "worker_origin": "manual",
                "attempt_count": 1,
            },
        }
        node_results = [
            {
                "node_id": node_id,
                "label": self._graph_node_label(validated_graph, node_id),
                "outcome": state["outcome"],
                "status": state["status"],
                "reasons": list(state["reasons"]),
            }
            for node_id, state in node_states.items()
        ]

        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": "paused_for_review",
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        worker_thread_id = f"fixture-node_gate-{run_id}"
        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "paused_for_review",
            "entry_node_ids": list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
            "node_run_states": [
                {
                    "node_id": node_id,
                    "run_id": run_id,
                    "status": state["status"],
                    "outcome": state["outcome"],
                    "attempt_count": int(state.get("attempt_count") or 1),
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": state.get("worker_origin"),
                    "warnings": list(state["reasons"]) if state["outcome"] in {"blocked", "pending"} else [],
                    "worker_thread_id": worker_thread_id if node_id == "node_gate" else None,
                    "parent_thread_id": str(task.get("active_provider_thread_id") or "") if node_id == "node_gate" else None,
                    "spawn_mode": "manual_only" if node_id == "node_gate" else "isolated_lane",
                    "agent_role": "gate" if node_id == "node_gate" else None,
                    "agent_nickname": self._graph_node_label(validated_graph, node_id) if node_id == "node_gate" else None,
                    "execution_backend": "human_review" if node_id == "node_gate" else None,
                }
                for node_id, state in node_states.items()
            ],
            "artifact_refs": [
                {
                    "artifact_id": f"{run_id}-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_discover",
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-report-md",
                    "artifact_kind": "run_summary",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_gate",
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
            ],
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": "Provider update gate fixture run created.",
                },
                {
                    "event_id": f"{run_id}-approval-requested",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "approval_requested",
                    "created_at": created_at,
                    "summary": "Manual promotion gate requested human approval before provider promotion.",
                    "node_id": "node_gate",
                },
            ],
            "approval_state": {
                "status": "pending",
                "review_kind": "provider_call_gate",
                "node_id": "node_gate",
                "reason": "Provider promotion is a high-risk action and requires human approval before execution continues.",
                "requested_at": created_at,
                "worker_thread_id": worker_thread_id,
                "allowed_actions": ["provider_call", "promotion"],
                "blocked_actions": ["silent_promotion", "external_writeback_without_review"],
            },
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "topology": "provider_update_smoke_gate",
                "requires_human_review": True,
                "max_parallelism": int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or 1),
                "budget": budget_snapshot,
                "node_mcp_tool_policies": self._compiled_node_mcp_tool_policies(compiled_plan),
                "skill_ref": deepcopy(dict(payload.get("skill_ref") or {})),
                "resolution_ref": deepcopy(dict(payload.get("resolution_ref") or {})),
                "dry_run_receipt": deepcopy(dict(payload.get("dry_run_receipt") or {})),
                "approval": deepcopy(dict(payload.get("approval") or {})),
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        self.record_graph_run(validated_run, graph_definition=validated_graph)

        self._record_fixture_worker_output(
            graph=validated_graph,
            run_id=run_id,
            node_id="node_discover",
            parent_thread_id=str(task.get("active_provider_thread_id") or ""),
            created_at=created_at,
            behavior="completed",
            summary="Discovery fixture found one provider metadata candidate and one promotion note for review.",
            machine_result={
                "provider_changes": ["qwen3-coder-plus metadata candidate"],
                "candidate_models": ["qwen3-coder-plus"],
            },
            next_action_hints=["Send the discovery artifact bundle into the smoke matrix node."],
        )
        self._record_fixture_worker_output(
            graph=validated_graph,
            run_id=run_id,
            node_id="node_smoke",
            parent_thread_id=str(task.get("active_provider_thread_id") or ""),
            created_at=created_at,
            behavior="completed",
            summary="Smoke validation fixture produced a bounded matrix and is ready for promotion review.",
            machine_result={
                "matrix": ["qwen3-coder-plus"],
                "blocked_cases": [],
            },
            next_action_hints=["Review the smoke matrix before approving promotion."],
        )
        self.record_graph_worker(
            {
                "graph_id": str(validated_graph.get("graph_id") or ""),
                "run_id": run_id,
                "node_id": "node_gate",
                "worker_thread_id": worker_thread_id,
                "parent_thread_id": str(task.get("active_provider_thread_id") or ""),
                "spawn_mode": "manual_only",
                "worker_origin": "manual",
                "agent_role": "gate",
                "agent_nickname": self._graph_node_label(validated_graph, "node_gate"),
                "status": "waiting_on_approval",
                "execution_backend": "human_review",
                "created_at": created_at,
                "updated_at": created_at,
            },
            graph_definition=validated_graph,
        )

        refreshed_task = self.current_task()
        refreshed_run = self.graph_run_ref(run_id)
        report_payload["run_ref"] = refreshed_run
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": refreshed_run,
            },
            "graph": validated_graph,
            "task": self.task_view(refreshed_task, compact_graph_runs=True),
        }

    def _dry_run_node_result(
        self,
        *,
        node: dict[str, Any],
        entry_node_ids: list[str],
        incoming_edges: list[dict[str, Any]],
        known_routes: set[tuple[str, str]],
        known_providers: set[str],
        profile_records_present: bool,
        require_live_contract: bool = False,
    ) -> dict[str, Any]:
        node_id = str(node.get("node_id") or "").strip()
        reasons: list[str] = []
        status = "pass"
        execution_policy = dict(node.get("execution_policy") or {})
        output_contract = dict(node.get("output_contract") or {})
        provider_id = str(node.get("provider_id") or "").strip()
        model_id = str(node.get("model_id") or "").strip()
        permission_mode = str(node.get("permission_mode") or "").strip()
        prompt_template = str(node.get("human_summary_template") or "").strip()
        if node_id not in entry_node_ids and not incoming_edges:
            status = "blocked"
            reasons.append("Node has no incoming edge and is not declared as an entry node.")
        if require_live_contract and not provider_id:
            status = "blocked"
            reasons.append("Live execution requires an explicit provider for every node.")
        if require_live_contract and not model_id:
            status = "blocked"
            reasons.append("Live execution requires a pinned model for every node.")
        if require_live_contract and not prompt_template:
            status = "blocked"
            reasons.append("Live execution requires an explicit node prompt; generic fallback prompts are not allowed.")
        if require_live_contract and not bool(execution_policy.get("allow_provider_calls")):
            status = "blocked"
            reasons.append("Live execution requires allow_provider_calls for every executable node.")
        if model_id and not provider_id:
            status = "blocked"
            reasons.append("Model is pinned but provider is empty.")
        if provider_id and not model_id:
            status = _promote_dry_run_status(status, "warning")
            reasons.append("Provider is set without a pinned model; route resolution is under-specified.")
        if provider_id and model_id:
            if profile_records_present and (provider_id, model_id) not in known_routes:
                status = "blocked"
                reasons.append(f"No configured profile matches {provider_id} / {model_id}.")
            elif not profile_records_present:
                status = _promote_dry_run_status(status, "warning")
                reasons.append("No profile catalog snapshot was available to verify provider/model compatibility.")
        elif provider_id and profile_records_present and provider_id not in known_providers:
            status = "blocked"
            reasons.append(f"Provider {provider_id} is not present in the configured profiles.")
        if permission_mode == "full":
            status = _promote_dry_run_status(status, "warning")
            reasons.append("Permission mode is full; this route should be reviewed before execution.")
        requires_human_approval = bool(execution_policy.get("requires_human_approval"))
        approval_gate = node.get("approval_gate")
        if (bool(execution_policy.get("allow_code_changes")) or bool(execution_policy.get("allow_install"))) and not approval_gate:
            status = "blocked"
            reasons.append("High-risk node allows code changes or installs without an approval gate.")
        if requires_human_approval and not approval_gate:
            status = "blocked"
            reasons.append("Execution policy requires human approval but no approval gate is declared.")
        artifact_outputs = [str(item).strip() for item in list(output_contract.get("artifact_outputs") or []) if str(item).strip()]
        machine_schema = output_contract.get("machine_result_schema")
        has_structured_machine_result = not bool(output_contract.get("artifact_only")) and isinstance(machine_schema, dict)
        if not artifact_outputs and not has_structured_machine_result:
            status = "blocked"
            reasons.append("Output contract does not declare any artifact outputs.")
        if not bool(output_contract.get("artifact_only")) and not isinstance(machine_schema, dict):
            status = "blocked"
            reasons.append("Output contract is missing machine_result_schema.")
        return {
            "node_id": node_id,
            "label": str(node.get("label") or node_id),
            "status": status,
            "reasons": reasons,
        }

    def _dry_run_edge_result(self, *, edge: dict[str, Any], node_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
        edge_id = str(edge.get("edge_id") or "").strip()
        reasons: list[str] = []
        status = "pass"
        context_policy = dict(edge.get("context_policy") or {})
        from_node = node_map.get(str(edge.get("from_node_id") or "").strip()) or {}
        source_outputs = [str(item).strip() for item in list(dict(from_node.get("output_contract") or {}).get("artifact_outputs") or []) if str(item).strip()]
        source_output_contract = dict(from_node.get("output_contract") or {})
        source_has_structured_machine_result = (
            not bool(source_output_contract.get("artifact_only"))
            and isinstance(source_output_contract.get("machine_result_schema"), dict)
        )
        artifact_mode = str(context_policy.get("artifact_mode") or "").strip()
        included_artifacts = [str(item).strip() for item in list(context_policy.get("included_artifacts") or []) if str(item).strip()]
        if artifact_mode == "required_output_only":
            included_artifacts = [item for item in included_artifacts if item != "required_output"]
        resource_refs = [str(item).strip() for item in list(context_policy.get("resource_refs") or []) if str(item).strip()]
        if artifact_mode == "explicit_artifacts" and not included_artifacts:
            status = "blocked"
            reasons.append("Edge uses explicit_artifacts but does not list included artifacts.")
        unknown_artifacts = sorted(set(included_artifacts).difference(source_outputs))
        if unknown_artifacts:
            status = "blocked"
            reasons.append(f"Included artifacts are not produced by the source node: {', '.join(unknown_artifacts)}.")
        if artifact_mode == "required_output_only" and not source_outputs and not source_has_structured_machine_result:
            status = "blocked"
            reasons.append("Edge expects required output artifacts but the source node does not declare any.")
        if str(context_policy.get("history_mode") or "").strip() == "explicit_refs_only" and not resource_refs and not included_artifacts:
            status = _promote_dry_run_status(status, "warning")
            reasons.append("Edge uses explicit_refs_only but no resource refs or included artifacts are listed.")
        if not bool(context_policy.get("exclude_private_memory", False)):
            status = "blocked"
            reasons.append("Edge does not exclude private memory.")
        return {
            "edge_id": edge_id,
            "label": f"{edge.get('from_node_id')} -> {edge.get('to_node_id')}",
            "status": status,
            "reasons": reasons,
        }

    def _dry_run_report_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            "# Task Graph Dry-Run Report",
            "",
            f"- Run ID: `{payload.get('run_id')}`",
            f"- Graph ID: `{payload.get('graph_id')}`",
            f"- Task ID: `{payload.get('task_id')}`",
            f"- Overall status: `{payload.get('overall_status')}`",
            f"- Created at: `{payload.get('created_at')}`",
            "",
            "## Graph",
            "",
            f"- Status: `{dict(payload.get('graph_result') or {}).get('status')}`",
        ]
        graph_reasons = [str(item) for item in list(dict(payload.get("graph_result") or {}).get("reasons") or []) if str(item).strip()]
        if graph_reasons:
            lines.extend(["- Reasons:"] + [f"  - {item}" for item in graph_reasons])
        lines.extend(["", "## Nodes", ""])
        for item in list(payload.get("node_results") or []):
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('node_id')}` / `{item.get('status')}`")
            for reason in list(item.get("reasons") or []):
                lines.append(f"  - {reason}")
        lines.extend(["", "## Edges", ""])
        for item in list(payload.get("edge_results") or []):
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('edge_id')}` / `{item.get('status')}`")
            for reason in list(item.get("reasons") or []):
                lines.append(f"  - {reason}")
        return "\n".join(lines).strip() + "\n"

    def _new_task(self, title: str) -> dict[str, Any]:
        project = self._project()
        task_id = new_id("task")
        now = now_iso()
        return {
            "schema_version": TASK_STATE_SCHEMA_VERSION,
            "task_id": task_id,
            "project_id": project.get("project_id"),
            "title": str(title or "New task").strip() or "New task",
            "status": "active",
            "handoff_policy": DEFAULT_HANDOFF_POLICY,
            "active_provider_thread_id": None,
            "provider_threads": [],
            "fork_threads": [],
            "handoff_events": [],
            "goal": None,
            "plan": None,
            "checkpoint_refs": [],
            "verification_refs": [],
            "diagnostic_refs": [],
            "asset_context_refs": [],
            "context_pack_refs": [],
            "graph_documents": [],
            "graph_definitions": [],
            "graph_run_refs": [],
            "graph_snapshot_refs": [],
            "graph_activity_summary": {
                "graph_count": 0,
                "run_count": 0,
                "latest_graph_id": None,
                "latest_run_id": None,
                "latest_run_status": None,
                "latest_updated_at": None,
            },
            "created_at": now,
            "updated_at": now,
        }

    def _bind_thread_to_task(
        self,
        task: dict[str, Any],
        *,
        thread_id: str,
        settings: dict[str, Any],
        role: str,
        make_active: bool,
    ) -> dict[str, Any]:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return task
        now = now_iso()
        hint = self._thread_context_hint(clean_thread_id)
        prior_entry: dict[str, Any] = {}
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                prior_entry = dict(item)
                break
        explicit_settings = {key: value for key, value in dict(settings or {}).items() if value is not None}
        merged_settings = {
            **{key: value for key, value in prior_entry.items() if value is not None},
            **{key: value for key, value in hint.items() if value is not None},
            **explicit_settings,
        }
        # Cache hints can be stale after provider handoffs or minimal visual turns.
        # Preserve an existing thread route unless this bind call explicitly
        # changes it; otherwise Kimi/DeepSeek metadata can bleed across providers.
        for route_key in (
            "profile_id",
            "provider_id",
            "model",
            "reasoning_effort",
            "permission_mode",
            "collaboration_mode",
            "execution_backend",
            "name",
        ):
            if route_key not in explicit_settings and prior_entry.get(route_key) is not None:
                merged_settings[route_key] = prior_entry.get(route_key)
        provider_id = merged_settings.get("provider_id")
        thread_entry = {
            "thread_id": clean_thread_id,
            "role": role or "provider",
            "profile_id": merged_settings.get("profile_id"),
            "provider_id": provider_id,
            "model": _display_model_id(merged_settings.get("model")),
            "reasoning_effort": _display_effort(merged_settings.get("reasoning_effort"), provider_id),
            "permission_mode": merged_settings.get("permission_mode"),
            "collaboration_mode": merged_settings.get("collaboration_mode"),
            "execution_backend": merged_settings.get("execution_backend"),
            "name": _display_thread_name(merged_settings.get("name"), provider_id),
            "updated_at": now,
        }
        existing = []
        created_at = now
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                created_at = str(item.get("created_at") or now)
                continue
            existing.append(item)
        thread_entry["created_at"] = created_at
        existing.insert(0, thread_entry)
        task["provider_threads"] = self._prune_provider_threads(existing)
        if role == "fork":
            fork_threads = [item for item in list(task.get("fork_threads") or []) if str(item.get("thread_id") or "") != clean_thread_id]
            fork_threads.insert(0, thread_entry)
            task["fork_threads"] = fork_threads[:40]
        if make_active:
            task["active_provider_thread_id"] = clean_thread_id
        if task.get("goal") is None and hint.get("goal") is not None:
            task["goal"] = redact_sensitive(hint.get("goal"))
        if task.get("plan") is None and hint.get("latest_plan") is not None:
            task["plan"] = redact_sensitive(hint.get("latest_plan"))
        task["updated_at"] = now
        return task

    def _prune_provider_threads(self, provider_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep task continuity records compact by route, not by raw thread count.

        The user-visible task should feel like one continuous chat even if app-server
        restarts or provider handoffs produce replacement internal threads. Keep the
        newest live thread per route and at most one recent missing diagnostic per
        route so context packs do not accumulate dozens of effectively equivalent
        provider-thread records.
        """
        seen_live_routes: set[tuple[str, str, str, str, str, str, str]] = set()
        seen_missing_routes: set[tuple[str, str, str, str, str, str, str]] = set()
        pruned: list[dict[str, Any]] = []
        for item in provider_threads:
            entry = dict(item)
            display_model = _display_model_id(entry.get("model"))
            if display_model is not None:
                entry["model"] = display_model
            display_effort = _display_effort(entry.get("reasoning_effort"), entry.get("provider_id"))
            if display_effort is not None:
                entry["reasoning_effort"] = display_effort
            display_name = _display_thread_name(entry.get("name"), entry.get("provider_id"))
            if display_name is not None or entry.get("name"):
                entry["name"] = display_name
            if not entry.get("missing_at") and not _provider_thread_entry_is_plausible(entry):
                entry["missing_at"] = now_iso()
                entry["missing_reason"] = "provider_model_mismatch"
            route_key = _provider_thread_route_key(entry)
            if entry.get("missing_at"):
                if route_key in seen_missing_routes:
                    continue
                seen_missing_routes.add(route_key)
            else:
                if route_key in seen_live_routes:
                    continue
                seen_live_routes.add(route_key)
                entry.pop("missing_at", None)
                entry.pop("missing_reason", None)
            pruned.append(entry)
        return pruned[:40]

    def _normalize_task(self, task: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        normalized = dict(task)
        changed = False
        original_threads = list(normalized.get("provider_threads") or [])
        pruned_threads = self._prune_provider_threads(original_threads)
        if pruned_threads != original_threads:
            normalized["provider_threads"] = pruned_threads
            changed = True
        original_forks = list(normalized.get("fork_threads") or [])
        pruned_forks = self._prune_fork_threads(original_forks)
        if pruned_forks != original_forks:
            normalized["fork_threads"] = pruned_forks
            changed = True
        original_checkpoints = list(normalized.get("checkpoint_refs") or [])
        pruned_checkpoints = self._dedupe_records(original_checkpoints, key_fields=("save_id",))
        if pruned_checkpoints != original_checkpoints:
            normalized["checkpoint_refs"] = pruned_checkpoints
            changed = True
        original_verification_refs = list(normalized.get("verification_refs") or [])
        pruned_verification_refs = self._dedupe_records(original_verification_refs, key_fields=("event_id",))
        if pruned_verification_refs != original_verification_refs:
            normalized["verification_refs"] = pruned_verification_refs
            changed = True
        original_diagnostic_refs = list(normalized.get("diagnostic_refs") or [])
        pruned_diagnostic_refs = self._dedupe_records(original_diagnostic_refs, key_fields=("event_id",))
        if pruned_diagnostic_refs != original_diagnostic_refs:
            normalized["diagnostic_refs"] = pruned_diagnostic_refs
            changed = True
        original_asset_refs = list(normalized.get("asset_context_refs") or [])
        pruned_asset_refs = self._dedupe_records(original_asset_refs, key_fields=("pack_type", "path"))
        if pruned_asset_refs != original_asset_refs:
            normalized["asset_context_refs"] = pruned_asset_refs
            changed = True
        original_context_refs = list(normalized.get("context_pack_refs") or [])
        pruned_context_refs = self._dedupe_records(original_context_refs, key_fields=("pack_type", "path"))
        if pruned_context_refs != original_context_refs:
            normalized["context_pack_refs"] = pruned_context_refs
            changed = True
        original_graph_definitions = list(normalized.get("graph_definitions") or [])
        pruned_graph_definitions = self._prune_graph_definitions(original_graph_definitions, task_id=str(normalized.get("task_id") or ""))
        if pruned_graph_definitions != original_graph_definitions:
            normalized["graph_definitions"] = pruned_graph_definitions
            changed = True
        original_graph_run_refs = list(normalized.get("graph_run_refs") or [])
        pruned_graph_run_refs = self._prune_graph_run_refs(
            original_graph_run_refs,
            task_id=str(normalized.get("task_id") or ""),
            graph_definitions=pruned_graph_definitions,
        )
        if pruned_graph_run_refs != original_graph_run_refs:
            normalized["graph_run_refs"] = pruned_graph_run_refs
            changed = True
        original_graph_snapshot_refs = list(normalized.get("graph_snapshot_refs") or [])
        pruned_graph_snapshot_refs = self._prune_graph_snapshot_refs(
            original_graph_snapshot_refs,
            task_id=str(normalized.get("task_id") or ""),
        )
        if pruned_graph_snapshot_refs != original_graph_snapshot_refs:
            normalized["graph_snapshot_refs"] = pruned_graph_snapshot_refs
            changed = True
        summary = self._graph_activity_summary({**normalized, "graph_definitions": pruned_graph_definitions, "graph_run_refs": pruned_graph_run_refs})
        if dict(normalized.get("graph_activity_summary") or {}) != summary:
            normalized["graph_activity_summary"] = summary
            changed = True
        preferred_active_thread_id = self._preferred_active_thread_id(normalized, pruned_threads)
        if str(normalized.get("active_provider_thread_id") or "") != preferred_active_thread_id:
            normalized["active_provider_thread_id"] = preferred_active_thread_id or None
            changed = True
        return normalized, changed

    def _prune_fork_threads(self, fork_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_ids: set[str] = set()
        pruned: list[dict[str, Any]] = []
        for item in fork_threads:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            thread_id = str(entry.get("thread_id") or "").strip()
            if not thread_id or thread_id in seen_ids:
                continue
            seen_ids.add(thread_id)
            pruned.append(entry)
        return pruned[:40]

    def _dedupe_records(self, records: list[Any], *, key_fields: tuple[str, ...], limit: int = 40) -> list[dict[str, Any]]:
        seen: set[tuple[str, ...]] = set()
        deduped: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            key = tuple(str(item.get(field) or "").strip() for field in key_fields)
            if not any(key):
                continue
            if key in seen:
                continue
            seen.add(key)
            deduped.append(dict(item))
        return deduped[:limit]

    def _prune_graph_definitions(self, records: list[Any], *, task_id: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        pruned: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            try:
                validated = validate_graph_definition(dict(item))
            except Exception:
                continue
            migrated = self._migrate_graph_record_to_current_document(validated, task_id=task_id)
            if not migrated:
                continue
            graph_id = str(migrated.get("graph_id") or "").strip()
            if not graph_id or graph_id in seen:
                continue
            seen.add(graph_id)
            pruned.append(migrated)
        return pruned[:GRAPH_DEFINITION_LIMIT]

    def _prune_graph_run_refs(
        self,
        records: list[Any],
        *,
        task_id: str,
        graph_definitions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        graph_map = {
            str(item.get("graph_id") or "").strip(): dict(item)
            for item in graph_definitions
            if isinstance(item, dict) and str(item.get("graph_id") or "").strip()
        }
        seen: set[str] = set()
        pruned: list[dict[str, Any]] = []
        for item in records:
            normalized = self._normalize_graph_run_ref(item, task_id=task_id, graph_definitions=graph_map)
            if not normalized:
                continue
            run_id = str(normalized.get("run_id") or "").strip()
            if not run_id or run_id in seen:
                continue
            seen.add(run_id)
            pruned.append(normalized)
        return pruned[:GRAPH_RUN_REF_LIMIT]

    def _normalize_graph_run_ref(
        self,
        value: Any,
        *,
        task_id: str,
        graph_definitions: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        run_id = str(value.get("run_id") or "").strip()
        graph_id = str(value.get("graph_id") or "").strip()
        current_task_id = str(value.get("task_id") or "").strip()
        # Accept persisted full run objects and compact them into refs.
        if value.get("schema_version") == "astrabridge-task-graph-run-v1":
            try:
                validated_run = validate_task_graph_run(
                    dict(value),
                    graph_definition=graph_definitions.get(graph_id),
                    workspace_root=self._projects.require_workspace_root(),
                )
            except Exception:
                return None
            if task_id and str(validated_run.get("task_id") or "") != task_id:
                return None
            return self._compact_graph_run_ref(validated_run)
        required = (
            "run_id",
            "graph_id",
            "task_id",
            "status",
            "created_at",
            "updated_at",
            "entry_node_ids",
            "node_status_counts",
            "artifact_count",
            "event_count",
        )
        if not run_id or not graph_id or not current_task_id:
            return None
        if task_id and current_task_id != task_id:
            return None
        if not all(field in value for field in required):
            return None
        normalized = dict(value)
        normalized["entry_node_ids"] = [
            str(item).strip()
            for item in list(normalized.get("entry_node_ids") or [])
            if str(item or "").strip()
        ]
        if not isinstance(normalized.get("node_status_counts"), dict):
            return None
        if "node_outcome_counts" in normalized and not isinstance(normalized.get("node_outcome_counts"), dict):
            return None
        approval_details = self._compact_graph_run_approval_state(normalized.get("approval_details"))
        if approval_details:
            normalized["approval_details"] = approval_details
        timeline_events = self._compact_graph_run_timeline_events(normalized.get("timeline_events"))
        if timeline_events:
            normalized["timeline_events"] = timeline_events
        diagnostic_refs = self._merge_graph_run_diagnostic_refs(normalized.get("diagnostic_refs"))
        if diagnostic_refs:
            normalized["diagnostic_refs"] = diagnostic_refs
        worker_bindings = []
        node_ids = set(normalized["entry_node_ids"])
        graph = graph_definitions.get(graph_id) or {}
        for node in list(graph.get("nodes") or []):
            if isinstance(node, dict):
                clean_node_id = str(node.get("node_id") or "").strip()
                if clean_node_id:
                    node_ids.add(clean_node_id)
        for item in list(normalized.get("worker_bindings") or []):
            binding = self._normalize_graph_worker_binding(item, graph_id=graph_id, run_id=run_id, node_ids=node_ids)
            if binding:
                worker_bindings.append(binding)
        if worker_bindings:
            normalized["worker_bindings"] = worker_bindings[:80]
            normalized["worker_count"] = len(normalized["worker_bindings"])
        else:
            normalized.pop("worker_bindings", None)
            normalized["worker_count"] = max(0, int(normalized.get("worker_count") or 0))
        return normalized

    def _compact_graph_run_ref(self, run: dict[str, Any]) -> dict[str, Any]:
        node_status_counts: dict[str, int] = {}
        node_outcome_counts: dict[str, int] = {}
        worker_bindings: list[dict[str, Any]] = []
        usage_signals: list[dict[str, Any]] = []
        provider_call_count = 0
        tool_call_count = 0
        total_retry_count = 0
        elapsed_values: list[int] = []
        for item in list(run.get("node_run_states") or []):
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").strip()
            if not status:
                continue
            node_status_counts[status] = int(node_status_counts.get(status) or 0) + 1
            outcome = str(item.get("outcome") or "").strip()
            if outcome:
                node_outcome_counts[outcome] = int(node_outcome_counts.get(outcome) or 0) + 1
            total_retry_count += max(0, int(item.get("attempt_count") or 0) - 1)
            if str(item.get("elapsed_ms") or "").strip():
                try:
                    elapsed_values.append(int(item.get("elapsed_ms") or 0))
                except (TypeError, ValueError):
                    pass
            if str(item.get("provider_call_count") or "").strip():
                provider_call_count += int(item.get("provider_call_count") or 0)
            if str(item.get("tool_call_count") or "").strip():
                tool_call_count += int(item.get("tool_call_count") or 0)
            usage_signal = item.get("usage_signal")
            if isinstance(usage_signal, dict):
                usage_signals.append(dict(usage_signal))
            worker_thread_id = str(item.get("worker_thread_id") or "").strip()
            if worker_thread_id:
                binding = self._normalize_graph_worker_binding(
                    {
                        "binding_id": item.get("worker_binding_id") or new_id("graph-worker"),
                        "graph_id": run.get("graph_id"),
                        "run_id": run.get("run_id"),
                        "node_id": item.get("node_id"),
                        "worker_thread_id": worker_thread_id,
                        "parent_thread_id": item.get("parent_thread_id"),
                        "spawn_mode": item.get("spawn_mode"),
                        "worker_origin": item.get("worker_origin"),
                        "agent_role": item.get("agent_role"),
                        "agent_nickname": item.get("agent_nickname"),
                        "status": item.get("status"),
                        "execution_backend": item.get("execution_backend"),
                        "artifact_refs": item.get("artifact_refs"),
                        "created_at": item.get("started_at") or run.get("created_at") or now_iso(),
                        "updated_at": item.get("updated_at") or run.get("updated_at") or now_iso(),
                    },
                    graph_id=str(run.get("graph_id") or ""),
                    run_id=str(run.get("run_id") or ""),
                    node_ids={str(item.get("node_id") or "").strip()},
                )
                if binding:
                    worker_bindings.append(binding)
        events = [dict(item) for item in list(run.get("event_refs") or []) if isinstance(item, dict)]
        latest_event = events[-1] if events else None
        raw_approval_state = run.get("approval_state")
        approval_state = (
            dict(raw_approval_state)
            if isinstance(raw_approval_state, dict)
            else {"status": str(raw_approval_state or "not_required").strip() or "not_required"}
        )
        compact = {
            "run_id": run.get("run_id"),
            "graph_id": run.get("graph_id"),
            "task_id": run.get("task_id"),
            "trace_id": run.get("trace_id"),
            "context_id": run.get("context_id"),
            "status": run.get("status"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "state_version": run.get("state_version"),
            "entry_node_ids": list(run.get("entry_node_ids") or []),
            "node_status_counts": node_status_counts,
            "node_outcome_counts": node_outcome_counts,
            "artifact_count": len(list(run.get("artifact_refs") or [])),
            "event_count": len(events),
            "approval_state": approval_state.get("status"),
            "approval_details": self._compact_graph_run_approval_state(approval_state),
            "latest_event_type": (latest_event or {}).get("event_type"),
            "latest_event_at": (latest_event or {}).get("created_at"),
            "timeline_events": self._compact_graph_run_timeline_events(events),
            "diagnostic_refs": self._extract_graph_run_diagnostic_refs(run),
            "artifact_refs": [
                {
                    "artifact_id": str(item.get("artifact_id") or "").strip(),
                    "artifact_kind": str(item.get("artifact_kind") or "").strip(),
                    "path": str(item.get("path") or "").strip(),
                    "status": str(item.get("status") or "").strip() or "ready",
                }
                for item in list(run.get("artifact_refs") or [])
                if isinstance(item, dict)
                and str(item.get("artifact_id") or "").strip()
                and str(item.get("artifact_kind") or "").strip()
                and str(item.get("path") or "").strip()
            ][:24],
            "policy_snapshot": redact_sensitive(dict(run.get("run_policy_snapshot") or {})),
        }
        compact["metrics"] = self._compact_graph_run_metrics(
            run=run,
            node_status_counts=node_status_counts,
            elapsed_values=elapsed_values,
            retry_count=total_retry_count,
            provider_call_count=provider_call_count,
            tool_call_count=tool_call_count,
            usage_signals=usage_signals,
            artifact_count=int(compact["artifact_count"] or 0),
            event_count=int(compact["event_count"] or 0),
            approval_status=str(compact.get("approval_state") or "").strip(),
        )
        compact["budget"] = self._compact_graph_run_budget(
            run=run,
            graph_metrics=dict(compact.get("metrics") or {}),
        )
        if worker_bindings:
            compact["worker_bindings"] = worker_bindings[:80]
            compact["worker_count"] = len(compact["worker_bindings"])
        else:
            compact["worker_count"] = 0
        return compact

    def _compact_graph_run_metrics(
        self,
        *,
        run: dict[str, Any],
        node_status_counts: dict[str, int],
        elapsed_values: list[int],
        retry_count: int,
        provider_call_count: int,
        tool_call_count: int,
        usage_signals: list[dict[str, Any]],
        artifact_count: int,
        event_count: int,
        approval_status: str,
    ) -> dict[str, Any]:
        policy_snapshot = dict(run.get("run_policy_snapshot") or {})
        pricing = dict(policy_snapshot.get("pricing") or {})
        combined_usage = self._combine_usage_signals(usage_signals, pricing=pricing)
        token_section = dict(combined_usage.get("tokens") or {})
        cost_section = dict(combined_usage.get("cost") or {})
        total_tokens = token_section.get("total_tokens")
        metrics_status = "available"
        unknown_fields: list[str] = []
        if combined_usage.get("status") != "available":
            metrics_status = "partial"
            unknown_fields.extend(["tokens", "cost"])
        if not provider_call_count:
            unknown_fields.append("provider_calls")
        if not tool_call_count:
            unknown_fields.append("tool_calls")
        elapsed_ms = max(elapsed_values) if elapsed_values else None
        if elapsed_ms is None:
            unknown_fields.append("elapsed_ms")
        parallelism = None
        if isinstance(policy_snapshot.get("max_parallelism"), int):
            parallelism = int(policy_snapshot.get("max_parallelism") or 0)
        elif isinstance(policy_snapshot.get("parallel_group_count"), int):
            parallelism = max(1, int(policy_snapshot.get("max_parallelism") or 1))
        if parallelism is None:
            unknown_fields.append("max_parallelism")
        if metrics_status == "available" and unknown_fields:
            metrics_status = "partial"
        failure_count = int(node_status_counts.get("failed") or 0) + int(node_status_counts.get("blocked") or 0)
        return {
            "status": metrics_status if metrics_status else "unknown",
            "elapsed_ms": elapsed_ms,
            "max_parallelism": parallelism,
            "artifact_count": artifact_count,
            "event_count": event_count,
            "retry_count": retry_count,
            "failure_count": failure_count,
            "approval_count": 0 if approval_status in {"", "not_required"} else 1,
            "provider_call_count": provider_call_count if provider_call_count else None,
            "tool_call_count": tool_call_count if tool_call_count else None,
            "token_usage": {
                "status": combined_usage.get("status") or "not_available",
                "reason": combined_usage.get("reason"),
                "input_tokens": token_section.get("input_tokens"),
                "output_tokens": token_section.get("output_tokens"),
                "reasoning_tokens": token_section.get("reasoning_tokens"),
                "cached_input_tokens": token_section.get("cached_input_tokens"),
                "total_tokens": total_tokens,
            },
            "cost": {
                "status": cost_section.get("status") or "not_available",
                "reason": cost_section.get("reason"),
                "currency": cost_section.get("currency"),
                "total_cost": cost_section.get("total_cost"),
            },
            "unknown_fields": sorted(set(unknown_fields)),
        }

    def _combine_usage_signals(self, signals: list[dict[str, Any]], *, pricing: dict[str, Any]) -> dict[str, Any]:
        available = [dict(item) for item in signals if isinstance(item, dict) and str(item.get("status") or "") == "available"]
        if not available:
            return usage_not_available(
                source="task_graph_run",
                reason="usage_not_reported",
                pricing=pricing,
                request_kind="graph_run",
            )
        totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cached_input_tokens": 0,
            "total_tokens": 0,
        }
        has_value = False
        provider_id = None
        model = None
        for signal in available:
            provider_id = provider_id or signal.get("provider_id")
            model = model or signal.get("model")
            tokens = dict(signal.get("tokens") or {})
            for key in tuple(totals):
                value = tokens.get(key)
                if value is None:
                    continue
                totals[key] += int(value)
                has_value = True
        if not has_value:
            return usage_not_available(
                source="task_graph_run",
                reason="usage_not_reported",
                provider_id=provider_id,
                model=model,
                pricing=pricing,
                request_kind="graph_run",
            )
        return normalize_usage_signal(
            source="task_graph_run",
            provider_id=provider_id,
            model=model,
            usage=totals,
            pricing=pricing,
            request_kind="graph_run",
        )

    def _compact_graph_run_budget(self, *, run: dict[str, Any], graph_metrics: dict[str, Any]) -> dict[str, Any]:
        policy_snapshot = dict(run.get("run_policy_snapshot") or {})
        budget = dict(policy_snapshot.get("budget") or {})
        if not budget:
            return {"status": "not_configured", "enforcement": "none"}
        def metric_or_snapshot(value: Any, fallback: Any) -> Any:
            return fallback if value is None else value
        graph_snapshot_observed = dict(dict(budget.get("graph") or {}).get("observed") or {})
        run_snapshot_observed = dict(dict(budget.get("run") or {}).get("observed") or {})
        graph_budget = self._evaluate_budget_section(
            limits=dict(dict(budget.get("graph") or {}).get("limits") or {}),
            observed={
                "max_parallelism": metric_or_snapshot(graph_metrics.get("max_parallelism"), graph_snapshot_observed.get("max_parallelism")),
                "artifact_count": metric_or_snapshot(graph_metrics.get("artifact_count"), graph_snapshot_observed.get("artifact_count")),
                "elapsed_ms": metric_or_snapshot(graph_metrics.get("elapsed_ms"), graph_snapshot_observed.get("elapsed_ms")),
                "provider_call_count": metric_or_snapshot(graph_metrics.get("provider_call_count"), graph_snapshot_observed.get("provider_call_count")),
                "tool_call_count": metric_or_snapshot(graph_metrics.get("tool_call_count"), graph_snapshot_observed.get("tool_call_count")),
                "total_tokens": metric_or_snapshot(dict(graph_metrics.get("token_usage") or {}).get("total_tokens"), graph_snapshot_observed.get("total_tokens")),
                "total_cost": metric_or_snapshot(dict(graph_metrics.get("cost") or {}).get("total_cost"), graph_snapshot_observed.get("total_cost")),
            },
        )
        run_budget = self._evaluate_budget_section(
            limits=dict(dict(budget.get("run") or {}).get("limits") or {}),
            observed={
                "artifact_count": metric_or_snapshot(graph_metrics.get("artifact_count"), run_snapshot_observed.get("artifact_count")),
                "event_count": metric_or_snapshot(graph_metrics.get("event_count"), run_snapshot_observed.get("event_count")),
                "failure_count": metric_or_snapshot(graph_metrics.get("failure_count"), run_snapshot_observed.get("failure_count")),
                "retry_count": metric_or_snapshot(graph_metrics.get("retry_count"), run_snapshot_observed.get("retry_count")),
                "elapsed_ms": metric_or_snapshot(graph_metrics.get("elapsed_ms"), run_snapshot_observed.get("elapsed_ms")),
                "provider_call_count": metric_or_snapshot(graph_metrics.get("provider_call_count"), run_snapshot_observed.get("provider_call_count")),
                "tool_call_count": metric_or_snapshot(graph_metrics.get("tool_call_count"), run_snapshot_observed.get("tool_call_count")),
                "total_tokens": metric_or_snapshot(dict(graph_metrics.get("token_usage") or {}).get("total_tokens"), run_snapshot_observed.get("total_tokens")),
                "total_cost": metric_or_snapshot(dict(graph_metrics.get("cost") or {}).get("total_cost"), run_snapshot_observed.get("total_cost")),
            },
        )
        provider_models = []
        for item in list(budget.get("provider_models") or []):
            if not isinstance(item, dict):
                continue
            provider_model_observed = dict(item.get("observed") or {})
            provider_models.append(
                {
                    "provider_id": str(item.get("provider_id") or "").strip() or None,
                    "model_id": str(item.get("model_id") or "").strip() or None,
                    **self._evaluate_budget_section(
                        limits=dict(item.get("limits") or {}),
                        observed={
                            "provider_call_count": metric_or_snapshot(graph_metrics.get("provider_call_count"), provider_model_observed.get("provider_call_count")),
                            "total_tokens": metric_or_snapshot(dict(graph_metrics.get("token_usage") or {}).get("total_tokens"), provider_model_observed.get("total_tokens")),
                            "total_cost": metric_or_snapshot(dict(graph_metrics.get("cost") or {}).get("total_cost"), provider_model_observed.get("total_cost")),
                        },
                    ),
                }
            )
        nodes = []
        for item in list(budget.get("nodes") or []):
            if not isinstance(item, dict):
                continue
            node_observed = dict(item.get("observed") or {})
            nodes.append(
                {
                    "node_id": str(item.get("node_id") or "").strip() or None,
                    "label": str(item.get("label") or "").strip() or None,
                    **self._evaluate_budget_section(
                        limits=dict(item.get("limits") or {}),
                        observed={
                            "attempt_count": node_observed.get("attempt_count"),
                            "elapsed_ms": node_observed.get("elapsed_ms"),
                            "provider_call_count": node_observed.get("provider_call_count"),
                            "tool_call_count": node_observed.get("tool_call_count"),
                            "total_tokens": node_observed.get("total_tokens"),
                            "total_cost": node_observed.get("total_cost"),
                        },
                    ),
                }
            )
        statuses = [graph_budget["status"], run_budget["status"], *[str(item.get("status") or "") for item in provider_models], *[str(item.get("status") or "") for item in nodes]]
        overall = "within_budget"
        if "exceeded" in statuses:
            overall = "exceeded"
        elif any(status == "unknown" for status in statuses):
            overall = "unknown"
        elif statuses and all(status == "not_configured" for status in statuses):
            overall = "not_configured"
        return {
            "status": overall,
            "enforcement": str(budget.get("enforcement") or "fail_fast_static_then_report_only_dynamic"),
            "graph": graph_budget,
            "run": run_budget,
            "provider_models": provider_models,
            "nodes": nodes,
        }

    def _evaluate_budget_section(self, *, limits: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
        clean_limits = {
            str(key).strip(): value
            for key, value in dict(limits or {}).items()
            if str(key).strip() and isinstance(value, (int, float))
        }
        if not clean_limits:
            return {"status": "not_configured", "limits": {}, "observed": {}, "exceeded_fields": [], "unknown_fields": []}
        exceeded_fields: list[str] = []
        unknown_fields: list[str] = []
        clean_observed: dict[str, Any] = {}
        for key, limit in clean_limits.items():
            value = observed.get(key)
            clean_observed[key] = value
            if value is None:
                unknown_fields.append(key)
                continue
            try:
                if float(value) > float(limit):
                    exceeded_fields.append(key)
            except (TypeError, ValueError):
                unknown_fields.append(key)
        status = "within_budget"
        if exceeded_fields:
            status = "exceeded"
        elif unknown_fields:
            status = "unknown"
        return {
            "status": status,
            "limits": clean_limits,
            "observed": clean_observed,
            "exceeded_fields": exceeded_fields,
            "unknown_fields": unknown_fields,
        }

    def _graph_run_budget_snapshot(
        self,
        *,
        graph: dict[str, Any],
        compiled_plan: dict[str, Any],
        run_budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        graph_policy = dict(graph.get("graph_policy") or {})
        graph_budget = dict(graph_policy.get("budget") or {})
        topology = dict(compiled_plan.get("topology") or {})
        routed_nodes = [
            dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and bool(dict(item.get("execution_policy") or {}).get("allow_provider_calls"))
        ]
        provider_model_expected: dict[tuple[str, str], int] = {}
        node_budgets = []
        static_blockers: list[str] = []
        for node in routed_nodes:
            provider_id = str(node.get("provider_id") or "").strip()
            model_id = str(node.get("model_id") or "").strip()
            if provider_id or model_id:
                key = (provider_id, model_id)
                provider_model_expected[key] = int(provider_model_expected.get(key) or 0) + 1
        for node in list(graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            budget = dict(node.get("budget") or {})
            execution_policy = dict(node.get("execution_policy") or {})
            if not budget:
                continue
            section = self._evaluate_budget_section(
                limits=budget,
                observed={
                    "attempt_count": int(dict(execution_policy.get("retry_policy") or {}).get("max_attempts") or 0),
                    "elapsed_ms": int(execution_policy.get("timeout_ms") or 0) if str(execution_policy.get("timeout_ms") or "").strip() else None,
                    "provider_call_count": 1 if bool(execution_policy.get("allow_provider_calls")) else 0,
                },
            )
            node_budgets.append(
                {
                    "node_id": str(node.get("node_id") or "").strip(),
                    "label": str(node.get("label") or "").strip(),
                    **section,
                }
            )
            if section["status"] == "exceeded":
                static_blockers.append(
                    f"Node budget exceeded for {str(node.get('label') or node.get('node_id') or 'node')}: {', '.join(section['exceeded_fields'])}."
                )
        provider_model_sections = []
        for item in list(graph_budget.get("provider_model_limits") or []):
            if not isinstance(item, dict):
                continue
            provider_id = str(item.get("provider_id") or "").strip()
            model_id = str(item.get("model_id") or "").strip()
            limits = dict(item.get("limits") or {})
            expected_calls = provider_model_expected.get((provider_id, model_id))
            section = self._evaluate_budget_section(
                limits=limits,
                observed={
                    "provider_call_count": expected_calls,
                },
            )
            provider_model_sections.append(
                {
                    "provider_id": provider_id or None,
                    "model_id": model_id or None,
                    **section,
                }
            )
            if section["status"] == "exceeded":
                static_blockers.append(
                    f"Provider/model budget exceeded for {provider_id or 'unknown provider'} / {model_id or 'unknown model'}: {', '.join(section['exceeded_fields'])}."
                )
        graph_section = self._evaluate_budget_section(
            limits=dict(graph_budget.get("limits") or {}),
            observed={
                "max_parallelism": int(topology.get("max_parallelism") or 1),
                "node_count": int(topology.get("node_count") or len(list(graph.get("nodes") or []))),
                "edge_count": int(topology.get("edge_count") or len(list(graph.get("edges") or []))),
                "provider_call_count": len(routed_nodes),
            },
        )
        if graph_section["status"] == "exceeded":
            static_blockers.append(f"Graph budget exceeded: {', '.join(graph_section['exceeded_fields'])}.")
        run_section = self._evaluate_budget_section(
            limits=dict(dict(run_budget or {}).get("limits") or (run_budget or {})),
            observed={
                "max_parallelism": int(topology.get("max_parallelism") or 1),
                "node_count": int(topology.get("node_count") or len(list(graph.get("nodes") or []))),
                "provider_call_count": len(routed_nodes),
            },
        )
        if run_section["status"] == "exceeded":
            static_blockers.append(f"Run budget exceeded: {', '.join(run_section['exceeded_fields'])}.")
        statuses = [graph_section["status"], run_section["status"], *[str(item.get("status") or "") for item in node_budgets], *[str(item.get("status") or "") for item in provider_model_sections]]
        overall = "within_budget"
        if "exceeded" in statuses:
            overall = "exceeded"
        elif "unknown" in statuses:
            overall = "unknown"
        elif "not_configured" in statuses and all(status == "not_configured" for status in statuses):
            overall = "not_configured"
        return {
            "status": overall,
            "enforcement": "fail_closed_goal_budget_with_dynamic_reconciliation",
            "graph": graph_section,
            "run": run_section,
            "provider_models": provider_model_sections,
            "nodes": node_budgets,
            "static_blockers": static_blockers,
        }

    @staticmethod
    def _compiled_node_mcp_tool_policies(compiled_plan: dict[str, Any]) -> dict[str, Any]:
        policies: dict[str, Any] = {}
        for item in list(compiled_plan.get("nodes") or []):
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("node_id") or "").strip()
            tool_policy = dict(item.get("tool_policy") or {})
            mcp_tool_policy = dict(tool_policy.get("mcp_tool_policy") or {})
            if node_id and mcp_tool_policy:
                policies[node_id] = deepcopy(mcp_tool_policy)
        return policies

    def _compact_graph_run_timeline_events(self, value: Any) -> list[dict[str, Any]]:
        events = [dict(item) for item in list(value or []) if isinstance(item, dict)]
        compact: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in events:
            event_id = str(item.get("event_id") or "").strip()
            event_type = str(item.get("event_type") or "").strip()
            created_at = str(item.get("created_at") or "").strip()
            if not event_id or not event_type or not created_at:
                continue
            if event_id in seen:
                continue
            seen.add(event_id)
            compact.append(
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "created_at": created_at,
                    "summary": _compact_text(redact_sensitive(item.get("summary") or ""), limit=240) or None,
                    "node_id": str(item.get("node_id") or "").strip() or None,
                    "edge_id": str(item.get("edge_id") or "").strip() or None,
                    "artifact_id": str(item.get("artifact_id") or "").strip() or None,
                    "parallel_group_id": str(item.get("parallel_group_id") or "").strip() or None,
                    "elapsed_ms": int(item.get("elapsed_ms") or 0) if str(item.get("elapsed_ms") or "").strip() else None,
                    "status": self._timeline_status_for_event_type(event_type),
                }
            )
        return compact[-24:]

    def _extract_graph_run_diagnostic_refs(self, run: dict[str, Any]) -> list[dict[str, Any]]:
        return self._merge_graph_run_diagnostic_refs(
            [
                {
                    "artifact_id": item.get("artifact_id"),
                    "artifact_kind": item.get("artifact_kind"),
                    "path": item.get("path"),
                    "status": item.get("status"),
                    "label": self._graph_run_diagnostic_label(item),
                }
                for item in list(run.get("artifact_refs") or [])
                if isinstance(item, dict)
                and str(item.get("artifact_kind") or "").strip() in {"validation_report", "diagnostic_bundle", "run_summary"}
            ]
        )

    def _merge_graph_run_diagnostic_refs(self, value: Any) -> list[dict[str, Any]]:
        refs = [dict(item) for item in list(value or []) if isinstance(item, dict)]
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in refs:
            artifact_id = str(item.get("artifact_id") or "").strip()
            artifact_kind = str(item.get("artifact_kind") or "").strip()
            path = str(item.get("path") or "").strip()
            if not artifact_id or not artifact_kind or not path:
                continue
            key = f"{artifact_id}|{path}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_kind": artifact_kind,
                    "path": path,
                    "status": str(item.get("status") or "").strip() or "ready",
                    "label": _compact_text(redact_sensitive(item.get("label") or ""), limit=120) or self._graph_run_diagnostic_label(item),
                }
            )
        return merged[:12]

    @staticmethod
    def _graph_run_diagnostic_label(item: dict[str, Any]) -> str:
        artifact_kind = str(item.get("artifact_kind") or "").strip()
        if artifact_kind == "validation_report":
            return "Validation report"
        if artifact_kind == "diagnostic_bundle":
            return "Diagnostic bundle"
        if artifact_kind == "run_summary":
            return "Run summary"
        return artifact_kind or "Diagnostic"

    @staticmethod
    def _timeline_status_for_event_type(event_type: str) -> str:
        if event_type in {"run_failed", "node_failed", "node_blocked"}:
            return "failed"
        if event_type in {"run_cancel_requested", "run_cancelled", "node_cancelled"}:
            return "cancelled"
        if event_type in {"run_completed", "node_completed", "approval_resolved", "artifact_created"}:
            return "completed"
        if event_type in {"node_started", "node_progress", "approval_requested", "run_dry_run_started"}:
            return "in_progress"
        return "pending"

    def _merge_graph_worker_artifact_refs(
        self,
        existing: list[Any],
        additions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*list(existing or []), *additions]:
            if not isinstance(item, dict):
                continue
            artifact_id = str(item.get("artifact_id") or "").strip()
            artifact_kind = str(item.get("artifact_kind") or "").strip()
            path = str(item.get("path") or "").strip()
            if not artifact_id or not artifact_kind or not path:
                continue
            key = f"{artifact_id}|{path}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_kind": artifact_kind,
                    "path": path,
                    "status": str(item.get("status") or "").strip() or "ready",
                }
            )
        return merged[:24]

    def _execute_supervisor_worker_synth_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        del payload
        return self._execute_linear_template_fixture_graph(
            task=task,
            validated_graph=validated_graph,
            topology="supervisor_worker_synthesizer",
            node_specs=[
                {
                    "node_id": "node_supervisor",
                    "summary": "Supervisor produced a bounded execution plan with one worker assignment and one synthesis expectation.",
                    "machine_result": {"plan": ["Inspect task input", "Delegate execution", "Synthesize result"], "next_workers": ["node_worker"]},
                    "next_action_hints": ["Send only the bounded execution plan into the worker lane."],
                },
                {
                    "node_id": "node_worker",
                    "summary": "Worker executed the bounded task and returned a constrained result bundle for synthesis.",
                    "machine_result": {"result": "Worker completed the requested bounded execution path.", "confidence": "fixture"},
                    "next_action_hints": ["Pass the worker artifact bundle into the synthesizer node."],
                },
                {
                    "node_id": "node_synth",
                    "summary": "Synthesizer merged the declared plan and worker output into one final operator-facing summary.",
                    "machine_result": {"summary": "Fixture workflow completed successfully.", "decision": "deliver_summary"},
                    "next_action_hints": ["Review the final run summary from the latest run panel."],
                },
            ],
        )

    def _execute_code_fix_review_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        del payload
        return self._execute_linear_template_fixture_graph(
            task=task,
            validated_graph=validated_graph,
            topology="code_fix_test_review",
            node_specs=[
                {
                    "node_id": "node_plan_fix",
                    "summary": "Planner scoped the bug fix to a bounded file set and declared the expected validation evidence.",
                    "machine_result": {"files": ["apps/example.ts"], "approach": "Narrow bug fix with explicit follow-on test and review."},
                    "next_action_hints": ["Apply only the planned diff in the code-fix node."],
                },
                {
                    "node_id": "node_code_fix",
                    "summary": "Code-fix worker produced a bounded diff artifact without relying on transcript replay.",
                    "machine_result": {"changed_files": ["apps/example.ts"], "summary": "Applied the planned guard condition and preserved existing behavior elsewhere."},
                    "next_action_hints": ["Use the diff artifact as the only input to the test and review nodes."],
                },
                {
                    "node_id": "node_test",
                    "summary": "Test validator executed the declared regression checks against the bounded diff artifact.",
                    "machine_result": {"status": "passed", "failures": []},
                    "next_action_hints": ["Attach the test report to the review node."],
                },
                {
                    "node_id": "node_review",
                    "summary": "Review node accepted the bounded change after reading the diff and test evidence.",
                    "machine_result": {"decision": "approved", "issues": []},
                    "next_action_hints": ["Surface the review report and test evidence together in the run panel."],
                },
            ],
        )

    def _execute_document_extract_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        del payload
        return self._execute_linear_template_fixture_graph(
            task=task,
            validated_graph=validated_graph,
            topology="document_extract_analyze_report",
            node_specs=[
                {
                    "node_id": "node_extract",
                    "summary": "Extractor produced a bounded document extract with sections and entities preserved as structured output.",
                    "machine_result": {"sections": ["Overview", "Risks"], "entities": ["Provider A", "Model B"]},
                    "next_action_hints": ["Pass only the extract artifact bundle into the analyst node."],
                },
                {
                    "node_id": "node_analyze",
                    "summary": "Analyst consumed the declared extract artifact and returned a structured interpretation.",
                    "machine_result": {"analysis": "The extracted document highlights two major rollout risks.", "confidence": "fixture"},
                    "next_action_hints": ["Generate the final report from the extract and analysis artifacts only."],
                },
                {
                    "node_id": "node_report",
                    "summary": "Report node produced a final operator-facing summary grounded in the bounded extract and analysis artifacts.",
                    "machine_result": {"report": "Fixture document report completed.", "recommendations": ["Validate the rollout gate before publishing."]},
                    "next_action_hints": ["Review the report artifact from the latest run panel."],
                },
            ],
        )

    def _execute_linear_template_fixture_graph(
        self,
        *,
        task: dict[str, Any],
        validated_graph: dict[str, Any],
        topology: str,
        node_specs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "fixture-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"

        node_results = [
            {
                "node_id": str(spec.get("node_id") or ""),
                "label": self._graph_node_label(validated_graph, str(spec.get("node_id") or "")),
                "outcome": "passed",
                "status": "completed",
                "reasons": [],
            }
            for spec in node_specs
        ]
        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": "completed",
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "completed",
            "entry_node_ids": list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
            "node_run_states": [
                {
                    "node_id": str(spec.get("node_id") or ""),
                    "run_id": run_id,
                    "status": "completed",
                    "outcome": "passed",
                    "attempt_count": 1,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                }
                for spec in node_specs
            ],
            "artifact_refs": [
                {
                    "artifact_id": f"{run_id}-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": str(node_specs[0].get("node_id") or ""),
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-report-md",
                    "artifact_kind": "run_summary",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": str(node_specs[-1].get("node_id") or ""),
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
            ],
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": f"{validated_graph['title']} fixture run created.",
                },
                *[
                    {
                        "event_id": f"{run_id}-{spec['node_id']}-completed",
                        "run_id": run_id,
                        "task_id": validated_graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_completed",
                        "created_at": created_at,
                        "summary": str(spec.get("summary") or ""),
                        "node_id": str(spec.get("node_id") or ""),
                    }
                    for spec in node_specs
                ],
                {
                    "event_id": f"{run_id}-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_completed",
                    "created_at": created_at,
                    "summary": f"{validated_graph['title']} fixture run completed.",
                },
            ],
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "topology": topology,
                "execution_mode": "default",
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        compact_ref = self.record_graph_run(validated_run, graph_definition=validated_graph)
        for spec in node_specs:
            self._record_fixture_worker_output(
                graph=validated_graph,
                run_id=run_id,
                node_id=str(spec.get("node_id") or ""),
                parent_thread_id=str(task.get("active_provider_thread_id") or ""),
                created_at=created_at,
                behavior="completed",
                summary=str(spec.get("summary") or ""),
                machine_result=dict(spec.get("machine_result") or {}),
                next_action_hints=[str(item).strip() for item in list(spec.get("next_action_hints") or []) if str(item or "").strip()],
                status="completed",
            )
        refreshed_task = self.current_task()
        refreshed_run = self.graph_run_ref(run_id)
        report_payload["run_ref"] = refreshed_run or compact_ref
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": refreshed_run or compact_ref,
            },
            "graph": validated_graph,
            "task": self.task_view(refreshed_task, compact_graph_runs=True),
        }

    def _fanout_fixture_node_states(self, *, behaviors: dict[str, str]) -> dict[str, dict[str, Any]]:
        branch_a = str(behaviors.get("node_research_a") or "completed").strip().lower() or "completed"
        branch_b = str(behaviors.get("node_research_b") or "blocked").strip().lower() or "blocked"
        merge_outcome = "passed"
        merge_status = "completed"
        merge_reasons: list[str] = []
        completed_branches = sum(1 for item in (branch_a, branch_b) if item == "completed")
        if completed_branches == 0:
            merge_outcome = "skipped"
            merge_status = "skipped"
            merge_reasons = ["No successful worker branch produced declared artifacts for the synthesizer."]
        elif completed_branches < 2:
            merge_outcome = "partial"
            merge_status = "partial"
            merge_reasons = ["One fan-out branch did not finish successfully; synthesizer merged the remaining declared artifacts only."]
        return {
            "node_supervisor": {
                "status": "completed",
                "outcome": "passed",
                "reasons": [],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_research_a": {
                "status": self._fixture_behavior_to_node_status(branch_a),
                "outcome": "passed" if branch_a == "completed" else branch_a,
                "reasons": [] if branch_a == "completed" else [f"Fixture branch A finished with status {branch_a}."],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_research_b": {
                "status": self._fixture_behavior_to_node_status(branch_b),
                "outcome": "passed" if branch_b == "completed" else branch_b,
                "reasons": [] if branch_b == "completed" else [f"Fixture branch B finished with status {branch_b}."],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_merge": {
                "status": merge_status,
                "outcome": merge_outcome,
                "reasons": merge_reasons,
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
        }

    @staticmethod
    def _fixture_behavior_to_node_status(behavior: str) -> str:
        mapping = {
            "completed": "completed",
            "blocked": "blocked",
            "failed": "failed",
            "partial": "partial",
            "skipped": "skipped",
        }
        return mapping.get(str(behavior or "").strip().lower(), "failed")

    @staticmethod
    def _fanout_fixture_run_status(node_states: dict[str, dict[str, Any]]) -> str:
        merge = dict(node_states.get("node_merge") or {})
        merge_status = str(merge.get("status") or "").strip()
        if merge_status == "completed":
            return "completed"
        if merge_status == "partial":
            return "partial"
        return "failed"

    @staticmethod
    def _compact_graph_run_approval_state(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        status = str(value.get("status") or "").strip()
        if not status:
            return None
        compact = {
            "status": status,
            "review_kind": str(value.get("review_kind") or "").strip() or None,
            "node_id": str(value.get("node_id") or "").strip() or None,
            "reason": _compact_text(redact_sensitive(value.get("reason") or ""), limit=240) or None,
            "requested_at": str(value.get("requested_at") or "").strip() or None,
            "resolved_at": str(value.get("resolved_at") or "").strip() or None,
            "decision": str(value.get("decision") or "").strip() or None,
            "notes": _compact_text(redact_sensitive(value.get("notes") or ""), limit=240) or None,
            "resolution_summary": _compact_text(redact_sensitive(value.get("resolution_summary") or ""), limit=240) or None,
            "worker_thread_id": str(value.get("worker_thread_id") or "").strip() or None,
            "allowed_actions": [str(item).strip() for item in list(value.get("allowed_actions") or []) if str(item or "").strip()][:8],
            "blocked_actions": [str(item).strip() for item in list(value.get("blocked_actions") or []) if str(item or "").strip()][:8],
        }
        return compact

    @staticmethod
    def _transition_run_ref_counts(
        run_ref: dict[str, Any],
        *,
        from_status: str,
        to_status: str,
        from_outcome: str | None = None,
        to_outcome: str | None = None,
    ) -> None:
        status_counts = dict(run_ref.get("node_status_counts") or {})
        if from_status:
            current = int(status_counts.get(from_status) or 0) - 1
            if current > 0:
                status_counts[from_status] = current
            else:
                status_counts.pop(from_status, None)
        if to_status:
            status_counts[to_status] = int(status_counts.get(to_status) or 0) + 1
        run_ref["node_status_counts"] = status_counts

        outcome_counts = dict(run_ref.get("node_outcome_counts") or {})
        if from_outcome:
            current = int(outcome_counts.get(from_outcome) or 0) - 1
            if current > 0:
                outcome_counts[from_outcome] = current
            else:
                outcome_counts.pop(from_outcome, None)
        if to_outcome:
            outcome_counts[to_outcome] = int(outcome_counts.get(to_outcome) or 0) + 1
        run_ref["node_outcome_counts"] = outcome_counts

    @staticmethod
    def _graph_node_label(graph: dict[str, Any], node_id: str) -> str:
        for node in list(graph.get("nodes") or []):
            if isinstance(node, dict) and str(node.get("node_id") or "").strip() == node_id:
                return str(node.get("label") or node_id)
        return node_id

    def _fixture_typed_output_values(
        self,
        *,
        graph: dict[str, Any],
        node: dict[str, Any],
        run_id: str,
        worker_thread_id: str,
        machine_result: dict[str, Any],
        summary: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Materialize deterministic values for every declared fixture output port.

        Fixture runners historically emitted only ``machine_result``.  That was
        sufficient for the older compatibility edges, but it made a fixture
        unable to exercise typed artifact handoffs such as ``code_diff`` or
        ``image``.  Keep the fixture local and provider-free while still
        producing protocol-valid values and preserved artifact paths for every
        optional output port.
        """

        workspace_root = self._projects.require_workspace_root()
        node_id = str(node.get("node_id") or "").strip() or "fixture-node"
        task_id = str(graph.get("task_id") or "").strip() or "fixture-task"
        relative_root = Path("PRIVATE") / "task-graph" / "workers" / run_id / node_id
        artifact_root = Path(workspace_root) / relative_root
        artifact_root.mkdir(parents=True, exist_ok=True)
        typed_output_values: dict[str, Any] = {}
        generated_artifact_refs: list[dict[str, Any]] = []
        media_types = {
            "code_diff": "text/x-diff",
            "image": "image/png",
            "audio": "audio/wav",
            "video": "video/mp4",
            "document": "application/json",
            "dataset": "application/json",
            "agent_report": "text/markdown",
            "approval_record": "application/json",
            "tool_result": "application/json",
            "structured_json": "application/json",
        }
        default_artifact_kinds = {
            "code_diff": "code_diff",
            "image": "image",
            "audio": "audio",
            "video": "video",
            "document": "document_extract",
            "dataset": "dataset",
            "agent_report": "text_report",
            "approval_record": "approval_record",
            "tool_result": "tool_result",
            "structured_json": "structured_json",
        }

        for port_id, port in self._graph_node_port_map(node, direction="outputs").items():
            if port_id == "machine_result":
                typed_output_values[port_id] = deepcopy(machine_result)
                continue
            port_type = str(port.get("port_type") or "structured_json").strip() or "structured_json"
            artifact_kind = str(port.get("artifact_kind") or default_artifact_kinds.get(port_type) or "fixture_artifact").strip()
            artifact_id = f"{worker_thread_id}-{port_id}-artifact"
            safe_suffix = "md" if port_type in {"text", "agent_report"} else "diff" if port_type == "code_diff" else "json"
            relative_path = (relative_root / f"{port_id}.{safe_suffix}").as_posix()
            artifact_path = Path(workspace_root) / relative_path
            media_type = media_types.get(port_type, "application/octet-stream")

            if port_type == "text":
                typed_output_values[port_id] = str(summary or f"Fixture output for {node_id}.{port_id}.").strip() or f"Fixture output for {node_id}.{port_id}."
                artifact_path.write_text(str(typed_output_values[port_id]), encoding="utf-8")
            elif port_type in {"structured_json", "tool_result"}:
                typed_output_values[port_id] = {
                    "fixture": True,
                    "node_id": node_id,
                    "port_id": port_id,
                    "summary": str(summary or "").strip()[:240],
                }
                write_json(artifact_path, typed_output_values[port_id])
            elif port_type == "code_diff":
                typed_output_values[port_id] = self._graph_worker_protocol_artifact_ref(
                    {
                        "artifact_id": artifact_id,
                        "artifact_kind": artifact_kind,
                        "path": relative_path,
                        "media_type": media_type,
                        "status": "ready",
                    },
                    task_id=task_id,
                    run_id=run_id,
                    source_node_id=node_id,
                )
                artifact_path.write_text(
                    "--- a/fixture.txt\n+++ b/fixture.txt\n@@\n+fixture-only bounded patch\n",
                    encoding="utf-8",
                )
            else:
                typed_output_values[port_id] = self._graph_worker_protocol_artifact_ref(
                    {
                        "artifact_id": artifact_id,
                        "artifact_kind": artifact_kind,
                        "path": relative_path,
                        "media_type": media_type,
                        "status": "ready",
                    },
                    task_id=task_id,
                    run_id=run_id,
                    source_node_id=node_id,
                )
                # The fixture deliberately preserves a redacted placeholder;
                # no provider payload or user file is copied into the bundle.
                write_json(
                    artifact_path,
                    {
                        "fixture": True,
                        "artifact_kind": artifact_kind,
                        "node_id": node_id,
                        "port_id": port_id,
                        "placeholder": "provider-free fixture artifact",
                    },
                )
            generated_artifact_refs.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_kind": artifact_kind,
                    "path": relative_path,
                    "status": "ready",
                }
            )
        return typed_output_values, generated_artifact_refs

    def _record_fixture_worker_output(
        self,
        *,
        graph: dict[str, Any],
        run_id: str,
        node_id: str,
        parent_thread_id: str,
        created_at: str,
        updated_at: str | None = None,
        behavior: str,
        summary: str,
        machine_result: dict[str, Any],
        next_action_hints: list[str],
        status: str | None = None,
        ) -> dict[str, Any]:
        effective_updated_at = str(updated_at or created_at or now_iso()).strip() or now_iso()
        worker_thread_id = f"fixture-{node_id}-{run_id}"
        node = next(
            (
                dict(item)
                for item in list(graph.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
            ),
            {},
        )
        role = str(node.get("kind") or "").strip() or "worker"
        nickname = str(node.get("label") or "").strip() or node_id
        self.record_graph_worker(
            {
                "graph_id": str(graph.get("graph_id") or ""),
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "parent_thread_id": parent_thread_id,
                "spawn_mode": "isolated_lane",
                "worker_origin": "fixture_runner",
                "agent_role": role,
                "agent_nickname": nickname,
                "status": status or self._fixture_behavior_to_node_status(behavior),
                "created_at": created_at,
                "updated_at": effective_updated_at,
            },
            graph_definition=graph,
        )
        typed_graph = dict(graph.get("orchestration_graph") or graph)
        typed_node = next(
            (
                dict(item)
                for item in list(typed_graph.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
            ),
            node,
        )
        fixture_typed_output_values, fixture_artifact_refs = self._fixture_typed_output_values(
            graph=typed_graph,
            node=typed_node,
            run_id=run_id,
            worker_thread_id=worker_thread_id,
            machine_result=machine_result,
            summary=summary,
        )
        return self.record_graph_worker_output(
            {
                "graph_id": str(graph.get("graph_id") or ""),
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "human_summary": summary,
                "machine_result": machine_result,
                "typed_output_values": fixture_typed_output_values,
                "generated_artifact_refs": fixture_artifact_refs,
                "confidence": "fixture",
                "next_action_hints": next_action_hints,
                "status": status or self._fixture_behavior_to_node_status(behavior),
                "created_at": created_at,
                "updated_at": effective_updated_at,
            },
            graph_definition=graph,
        )

    def _reconcile_fixture_worker_bindings(
        self,
        task: dict[str, Any] | None,
        *,
        run_id: str,
        preferred_bindings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if not task:
            return task
        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            return task
        merged_bindings = [dict(item) for item in list(run_ref.get("worker_bindings") or []) if isinstance(item, dict)]
        for binding in list(preferred_bindings or []):
            if not isinstance(binding, dict):
                continue
            merged_bindings = self._merge_run_ref_worker_binding(merged_bindings, binding)
        for binding in list(run_ref.get("worker_bindings") or []):
            if not isinstance(binding, dict):
                continue
            output_path = str(dict(binding.get("output_summary") or {}).get("artifact_bundle_path") or "").strip()
            if output_path:
                merged_bindings = self._merge_run_ref_worker_binding(merged_bindings, binding)
        run_ref["worker_bindings"] = merged_bindings[:80]
        run_ref["worker_count"] = len(run_ref["worker_bindings"])
        task["graph_run_refs"] = [
            run_ref if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return task

    @staticmethod
    def _merge_run_ref_worker_binding(existing: list[dict[str, Any]], binding: dict[str, Any]) -> list[dict[str, Any]]:
        clean_binding_id = str(binding.get("binding_id") or "").strip()
        clean_node_id = str(binding.get("node_id") or "").strip()
        clean_worker_thread_id = str(binding.get("worker_thread_id") or "").strip()
        remainder = [
            dict(item)
            for item in existing
            if isinstance(item, dict)
            and str(item.get("binding_id") or "").strip() != clean_binding_id
            and not (
                str(item.get("node_id") or "").strip() == clean_node_id
                and str(item.get("worker_thread_id") or "").strip() == clean_worker_thread_id
            )
        ]
        return [dict(binding), *remainder]

    @staticmethod
    def _graph_worker_stable_identifier(prefix: str, *parts: Any) -> str:
        seed = "::".join(str(part or "").strip() for part in parts if str(part or "").strip())
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        return f"{prefix}-{digest}"

    def _graph_worker_protocol_artifact_ref(
        self,
        artifact: dict[str, Any],
        *,
        task_id: str,
        run_id: str,
        source_node_id: str,
    ) -> dict[str, Any]:
        canonical = adapt_legacy_artifact_path(
            artifact,
            task_id=task_id,
            run_id=run_id,
            source_node_id=source_node_id,
        )
        canonical["metadata"] = {
            **dict(canonical.get("metadata") or {}),
            "relative_path": str(artifact.get("path") or "").replace("\\", "/").strip() or None,
            "artifact_kind": str(artifact.get("artifact_kind") or "").strip() or None,
        }
        return validate_protocol_payload("ArtifactRef", canonical)

    @staticmethod
    def _graph_node_port_map(
        node: dict[str, Any],
        *,
        direction: str,
    ) -> dict[str, dict[str, Any]]:
        ports = dict(node.get("ports") or {})
        return {
            str(item.get("port_id") or "").strip(): dict(item)
            for item in list(ports.get(direction) or [])
            if isinstance(item, dict) and str(item.get("port_id") or "").strip()
        }

    @staticmethod
    def _graph_json_schema_errors(schema: dict[str, Any], value: Any) -> list[str]:
        validator = Draft202012Validator(schema)
        errors = sorted(
            validator.iter_errors(value),
            key=lambda item: (
                tuple(str(part) for part in item.path),
                tuple(str(part) for part in item.schema_path),
            ),
        )
        formatted: list[str] = []
        for item in errors[:8]:
            instance_path = "/" + "/".join(str(part) for part in item.path) if list(item.path) else "$"
            formatted.append(f"{instance_path}: {item.message}")
        return formatted

    def _graph_validate_port_value(
        self,
        *,
        port: dict[str, Any],
        value: Any,
        schema_registry: dict[str, Any],
        edge_id: str,
        node_id: str,
        port_id: str,
        direction: str,
    ) -> None:
        port_type = str(port.get("port_type") or "").strip()
        shape = str(port.get("shape") or "single").strip() or "single"
        if shape != "single":
            raise GraphContractValidationError(
                f"edge {edge_id} {direction} port {node_id}.{port_id} uses unsupported shape {shape}; live typed delivery currently requires shape=single."
            )
        if port_type == "text":
            if not isinstance(value, str) or not value.strip():
                raise GraphContractValidationError(
                    f"edge {edge_id} {direction} port {node_id}.{port_id} expects a non-empty text value."
                )
        elif port_type in {"structured_json", "tool_result"}:
            if not isinstance(value, (dict, list)):
                raise GraphContractValidationError(
                    f"edge {edge_id} {direction} port {node_id}.{port_id} expects structured JSON data."
                )
        else:
            if not isinstance(value, dict):
                raise GraphContractValidationError(
                    f"edge {edge_id} {direction} port {node_id}.{port_id} expects a protocol ArtifactRef payload."
                )
            try:
                validate_protocol_payload("ArtifactRef", value)
            except ProtocolValidationError as exc:
                raise GraphContractValidationError(
                    f"edge {edge_id} {direction} port {node_id}.{port_id} received an invalid ArtifactRef payload: {exc}"
                ) from exc
        schema_ref = str(port.get("schema_ref") or "").strip()
        if not schema_ref:
            return
        schema = schema_registry.get(schema_ref)
        if not isinstance(schema, dict) or not schema:
            raise GraphContractValidationError(
                f"edge {edge_id} {direction} port {node_id}.{port_id} references missing schema {schema_ref}."
            )
        errors = self._graph_json_schema_errors(schema, value)
        if errors:
            raise GraphContractValidationError(
                f"edge {edge_id} {direction} port {node_id}.{port_id} violated {schema_ref}: {errors[0]}"
            )

    def _build_graph_worker_typed_handoff_projection(
        self,
        *,
        graph: dict[str, Any],
        edge: dict[str, Any],
        source_node: dict[str, Any],
        target_node: dict[str, Any],
        output_bundle: dict[str, Any],
        artifact_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        edge_id = str(edge.get("edge_id") or "").strip() or "edge"
        handoff_contract = dict(edge.get("handoff_contract") or {})
        schema_registry = dict(graph.get("schema_registry") or {})
        port_bindings = [
            {
                "from_port_id": str(item.get("from_port_id") or "").strip(),
                "to_port_id": str(item.get("to_port_id") or "").strip(),
            }
            for item in list(handoff_contract.get("port_bindings") or [])
            if isinstance(item, dict)
            and str(item.get("from_port_id") or "").strip()
            and str(item.get("to_port_id") or "").strip()
        ]
        if not port_bindings:
            return {
                "status": "compatibility_required",
                "mode": "legacy_raw_text_blocked",
                "diagnostic": (
                    f"edge {edge_id} is missing typed port_bindings; refresh the migrated graph before live delivery."
                ),
                "bindings": [],
                "inputs": {},
                "required_output_schema_refs": [
                    str(item).strip()
                    for item in list(handoff_contract.get("required_output_schema_refs") or [])
                    if str(item or "").strip()
                ],
            }
        source_ports = self._graph_node_port_map(source_node, direction="outputs")
        target_ports = self._graph_node_port_map(target_node, direction="inputs")
        if not source_ports or not target_ports:
            return {
                "status": "compatibility_required",
                "mode": "legacy_raw_text_blocked",
                "diagnostic": (
                    f"edge {edge_id} is missing typed source or target ports; refresh the migrated graph before live delivery."
                ),
                "bindings": [],
                "inputs": {},
                "required_output_schema_refs": [
                    str(item).strip()
                    for item in list(handoff_contract.get("required_output_schema_refs") or [])
                    if str(item or "").strip()
                ],
            }
        human_summary = str(output_bundle.get("human_summary") or "").strip()
        machine_result = redact_sensitive(output_bundle.get("machine_result") or {})
        source_values: dict[str, Any] = {
            str(item.get("artifact_id") or "").strip(): deepcopy(item)
            for item in artifact_refs
            if isinstance(item, dict) and str(item.get("artifact_id") or "").strip()
        }
        for port_id, value in dict(output_bundle.get("typed_output_values") or {}).items():
            clean_port_id = str(port_id or "").strip()
            if not clean_port_id:
                continue
            source_values[clean_port_id] = deepcopy(value)
        if human_summary and "human_summary" not in source_values:
            source_values["human_summary"] = human_summary
        if isinstance(machine_result, dict) and machine_result and "machine_result" not in source_values:
            source_values["machine_result"] = deepcopy(machine_result)

        projected_inputs: dict[str, Any] = {}
        binding_records: list[dict[str, Any]] = []
        declared_schema_refs = {
            str(item).strip()
            for item in list(handoff_contract.get("required_output_schema_refs") or [])
            if str(item or "").strip()
        }
        for binding in port_bindings:
            from_port_id = binding["from_port_id"]
            to_port_id = binding["to_port_id"]
            source_port = dict(source_ports.get(from_port_id) or {})
            target_port = dict(target_ports.get(to_port_id) or {})
            if not source_port:
                raise GraphContractValidationError(
                    f"edge {edge_id} references unknown source output port {from_port_id}."
                )
            if not target_port:
                raise GraphContractValidationError(
                    f"edge {edge_id} references unknown target input port {to_port_id}."
                )
            source_shape = str(source_port.get("shape") or "single").strip() or "single"
            target_shape = str(target_port.get("shape") or "single").strip() or "single"
            if source_shape != target_shape:
                raise GraphContractValidationError(
                    f"edge {edge_id} has incompatible port shapes for {from_port_id}->{to_port_id}: {source_shape} != {target_shape}."
                )
            source_type = str(source_port.get("port_type") or "").strip()
            target_type = str(target_port.get("port_type") or "").strip()
            if source_type and target_type and source_type != target_type:
                raise GraphContractValidationError(
                    f"edge {edge_id} has incompatible live port types for {from_port_id}->{to_port_id}: {source_type} != {target_type}."
                )
            if from_port_id not in source_values:
                raise GraphContractValidationError(
                    f"edge {edge_id} expected source output port {from_port_id}, but the node did not produce a value for it."
                )
            source_schema_ref = str(source_port.get("schema_ref") or "").strip()
            if source_schema_ref and declared_schema_refs and source_schema_ref not in declared_schema_refs:
                raise GraphContractValidationError(
                    f"edge {edge_id} is missing required_output_schema_refs coverage for source schema {source_schema_ref}."
                )
            value = deepcopy(source_values[from_port_id])
            self._graph_validate_port_value(
                port=source_port,
                value=value,
                schema_registry=schema_registry,
                edge_id=edge_id,
                node_id=str(source_node.get("node_id") or "").strip() or "source",
                port_id=from_port_id,
                direction="source",
            )
            self._graph_validate_port_value(
                port=target_port,
                value=value,
                schema_registry=schema_registry,
                edge_id=edge_id,
                node_id=str(target_node.get("node_id") or "").strip() or "target",
                port_id=to_port_id,
                direction="target",
            )
            if to_port_id in projected_inputs:
                raise GraphContractValidationError(
                    f"edge {edge_id} attempted to assign multiple values to target input port {to_port_id}."
                )
            projected_inputs[to_port_id] = deepcopy(value)
            binding_records.append(
                {
                    "from_port_id": from_port_id,
                    "to_port_id": to_port_id,
                    "source_port_type": source_type,
                    "target_port_type": target_type,
                    "source_schema_ref": source_schema_ref or None,
                    "target_schema_ref": str(target_port.get("schema_ref") or "").strip() or None,
                    "value": deepcopy(value),
                }
            )
        return {
            "status": "validated",
            "mode": "typed_ports",
            "diagnostic": None,
            "bindings": binding_records,
            "inputs": projected_inputs,
            "required_output_schema_refs": sorted(declared_schema_refs),
        }

    def _validate_graph_handoff_typed_projection(
        self,
        *,
        graph: dict[str, Any],
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = dict(envelope.get("metadata") or {})
        edge_id = str(metadata.get("edge_id") or "").strip()
        source_node_id = str(metadata.get("source_node_id") or "").strip()
        target_node_id = str(metadata.get("target_node_id") or "").strip()
        if not edge_id or not source_node_id or not target_node_id:
            raise ValueError("agent envelope typed handoff metadata is missing edge/source/target identifiers.")
        edge = next(
            (
                dict(item)
                for item in list(graph.get("edges") or [])
                if isinstance(item, dict) and str(item.get("edge_id") or "").strip() == edge_id
            ),
            {},
        )
        injection_mode = str(metadata.get("injection_mode") or "").strip()
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        source_node = dict(node_map.get(source_node_id) or {})
        target_node = dict(node_map.get(target_node_id) or {})
        if not target_node:
            raise ValueError("agent envelope typed handoff references unknown source or target node.")
        typed_handoff = dict(metadata.get("typed_handoff") or {})
        if not typed_handoff:
            raise ValueError(
                "agent envelope is missing typed_handoff projection; legacy raw-text fallback is blocked until the graph migration is refreshed."
            )
        if str(typed_handoff.get("status") or "").strip() != "validated":
            diagnostic = str(typed_handoff.get("diagnostic") or "").strip() or "typed handoff projection requires migration"
            raise ValueError(
                f"agent envelope typed handoff is not live-runnable: {diagnostic}"
            )
        if not edge:
            if injection_mode != "subgraph_entry_seed":
                raise ValueError(f"agent envelope references unknown edge_id {edge_id}.")
            binding_records = [
                dict(item)
                for item in list(typed_handoff.get("bindings") or [])
                if isinstance(item, dict)
            ]
            if not binding_records:
                raise ValueError("subgraph entry seed handoff is missing typed binding records.")
            inputs = dict(typed_handoff.get("inputs") or {})
            target_ports = self._graph_node_port_map(target_node, direction="inputs")
            schema_registry = dict(graph.get("schema_registry") or {})
            for binding in binding_records:
                to_port_id = str(binding.get("to_port_id") or "").strip()
                if not to_port_id or to_port_id not in inputs:
                    raise ValueError("subgraph entry seed handoff is missing a required target input payload.")
                value = binding.get("value")
                if inputs[to_port_id] != value:
                    raise ValueError(
                        f"subgraph entry seed payload for {to_port_id} does not match its binding value."
                    )
                target_port = dict(target_ports.get(to_port_id) or {})
                if not target_port:
                    raise ValueError(
                        f"subgraph entry seed references unknown target input port {to_port_id}."
                    )
                self._graph_validate_port_value(
                    port=target_port,
                    value=value,
                    schema_registry=schema_registry,
                    edge_id=edge_id,
                    node_id=target_node_id,
                    port_id=to_port_id,
                    direction="target",
                )
            return typed_handoff
        if not source_node:
            raise ValueError("agent envelope typed handoff references unknown source or target node.")
        expected_bindings = [
            {
                "from_port_id": str(item.get("from_port_id") or "").strip(),
                "to_port_id": str(item.get("to_port_id") or "").strip(),
            }
            for item in list(dict(edge.get("handoff_contract") or {}).get("port_bindings") or [])
            if isinstance(item, dict)
            and str(item.get("from_port_id") or "").strip()
            and str(item.get("to_port_id") or "").strip()
        ]
        binding_records = [
            dict(item)
            for item in list(typed_handoff.get("bindings") or [])
            if isinstance(item, dict)
        ]
        if len(binding_records) != len(expected_bindings):
            raise ValueError(
                f"agent envelope typed handoff binding count does not match edge {edge_id}."
            )
        inputs = dict(typed_handoff.get("inputs") or {})
        source_ports = self._graph_node_port_map(source_node, direction="outputs")
        target_ports = self._graph_node_port_map(target_node, direction="inputs")
        schema_registry = dict(graph.get("schema_registry") or {})
        expected_target_ids = {item["to_port_id"] for item in expected_bindings}
        unexpected_input_ids = sorted(set(inputs).difference(expected_target_ids))
        if unexpected_input_ids:
            raise ValueError(
                f"agent envelope typed handoff contains unexpected target inputs: {', '.join(unexpected_input_ids)}"
            )
        for index, expected in enumerate(expected_bindings):
            binding = dict(binding_records[index])
            from_port_id = str(binding.get("from_port_id") or "").strip()
            to_port_id = str(binding.get("to_port_id") or "").strip()
            if from_port_id != expected["from_port_id"] or to_port_id != expected["to_port_id"]:
                raise ValueError(
                    f"agent envelope typed handoff binding order/content does not match edge {edge_id}."
                )
            if to_port_id not in inputs:
                raise ValueError(
                    f"agent envelope typed handoff is missing input payload for {to_port_id}."
                )
            value = binding.get("value")
            if inputs[to_port_id] != value:
                raise ValueError(
                    f"agent envelope typed handoff payload for {to_port_id} does not match its binding value."
                )
            source_port = dict(source_ports.get(from_port_id) or {})
            target_port = dict(target_ports.get(to_port_id) or {})
            if not source_port or not target_port:
                raise ValueError(
                    f"agent envelope typed handoff references unknown source/target port {from_port_id}->{to_port_id}."
                )
            self._graph_validate_port_value(
                port=source_port,
                value=value,
                schema_registry=schema_registry,
                edge_id=edge_id,
                node_id=source_node_id,
                port_id=from_port_id,
                direction="source",
            )
            self._graph_validate_port_value(
                port=target_port,
                value=value,
                schema_registry=schema_registry,
                edge_id=edge_id,
                node_id=target_node_id,
                port_id=to_port_id,
                direction="target",
            )
        return typed_handoff

    def validate_graph_node_machine_result_contract(
        self,
        graph_definition: dict[str, Any],
        *,
        node_id: str,
        machine_result: Any,
    ) -> dict[str, Any] | None:
        node = next(
            (
                dict(item)
                for item in list(graph_definition.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
            ),
            {},
        )
        if not node:
            raise ValueError(f"Unknown node_id for output validation: {node_id}")
        output_contract = dict(node.get("output_contract") or {})
        if bool(output_contract.get("artifact_only")):
            return None
        schema = output_contract.get("machine_result_schema")
        if not isinstance(schema, dict) or not schema:
            return {
                "schema_ref": None,
                "errors": ["output_contract.machine_result_schema is missing."],
            }
        if not isinstance(machine_result, dict) or not machine_result:
            return {
                "schema_ref": f"schema.{node_id}.machine_result",
                "errors": ["machine_result must be a non-empty object."],
            }
        errors = self._graph_json_schema_errors(schema, machine_result)
        if not errors:
            return None
        return {
            "schema_ref": f"schema.{node_id}.machine_result",
            "errors": errors,
        }

    def _graph_worker_content_parts(
        self,
        *,
        output_bundle: dict[str, Any],
        message_parts: list[dict[str, Any]],
        artifact_refs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        artifact_by_id = {
            str(item.get("artifact_id") or "").strip(): dict(item)
            for item in artifact_refs
            if isinstance(item, dict) and str(item.get("artifact_id") or "").strip()
        }
        for index, item in enumerate(message_parts, start=1):
            if not isinstance(item, dict):
                continue
            part_type = str(item.get("part_type") or "").strip()
            if not part_type:
                continue
            if part_type == "human_summary":
                human_summary = str(output_bundle.get("human_summary") or "").strip()
                if not human_summary:
                    continue
                parts.append(
                    validate_protocol_payload(
                        "ContentPart",
                        {
                            "part_id": self._graph_worker_stable_identifier(
                                "part",
                                output_bundle.get("run_id"),
                                output_bundle.get("node_id"),
                                output_bundle.get("attempt_count"),
                                "human_summary",
                                index,
                            ),
                            "kind": "text",
                            "mime_type": "text/markdown",
                            "text": human_summary,
                            "metadata": {
                                "part_type": "human_summary",
                                "relative_path": str(item.get("path") or "").strip() or None,
                                "preview": str(item.get("preview") or "").strip() or None,
                            },
                        },
                    )
                )
                continue
            if part_type == "machine_result":
                machine_result = redact_sensitive(output_bundle.get("machine_result") or {})
                if not isinstance(machine_result, dict) or not machine_result:
                    continue
                parts.append(
                    validate_protocol_payload(
                        "ContentPart",
                        {
                            "part_id": self._graph_worker_stable_identifier(
                                "part",
                                output_bundle.get("run_id"),
                                output_bundle.get("node_id"),
                                output_bundle.get("attempt_count"),
                                "machine_result",
                                index,
                            ),
                            "kind": "json",
                            "mime_type": "application/json",
                            "data": machine_result,
                            "metadata": {
                                "part_type": "machine_result",
                                "relative_path": str(item.get("path") or "").strip() or None,
                                "preview": str(item.get("preview") or "").strip() or None,
                            },
                        },
                    )
                )
                continue
            if part_type == "artifact_ref":
                artifact_id = str(item.get("artifact_id") or "").strip()
                artifact = artifact_by_id.get(artifact_id)
                if artifact is None:
                    continue
                parts.append(
                    validate_protocol_payload(
                        "ContentPart",
                        {
                            "part_id": self._graph_worker_stable_identifier(
                                "part",
                                output_bundle.get("run_id"),
                                output_bundle.get("node_id"),
                                output_bundle.get("attempt_count"),
                                artifact_id,
                                index,
                            ),
                            "kind": "artifact",
                            "mime_type": str(artifact.get("media_type") or "application/octet-stream"),
                            "artifact": artifact,
                            "metadata": {
                                "part_type": "artifact_ref",
                                "artifact_kind": str(item.get("artifact_kind") or dict(artifact.get("metadata") or {}).get("artifact_kind") or "").strip() or None,
                                "relative_path": str(item.get("path") or "").strip() or str(dict(artifact.get("metadata") or {}).get("relative_path") or "").strip() or None,
                            },
                        },
                    )
                )
                continue
            if part_type == "resource_ref":
                resource_ref = str(item.get("path") or "").strip()
                if not resource_ref:
                    continue
                parts.append(
                    validate_protocol_payload(
                        "ContentPart",
                        {
                            "part_id": self._graph_worker_stable_identifier(
                                "part",
                                output_bundle.get("run_id"),
                                output_bundle.get("node_id"),
                                output_bundle.get("attempt_count"),
                                "resource_ref",
                                index,
                            ),
                            "kind": "text",
                            "mime_type": "text/uri-list",
                            "text": resource_ref,
                            "metadata": {"part_type": "resource_ref"},
                        },
                    )
                )
        return parts

    def _build_graph_worker_handoffs(
        self,
        *,
        graph: dict[str, Any],
        node_id: str,
        run_id: str,
        output_bundle: dict[str, Any],
        output_envelope: dict[str, Any],
        bundle_paths: dict[str, str],
        generated_artifact_refs: list[dict[str, Any]],
        selected_edge_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        handoffs: list[dict[str, Any]] = []
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        source_node = dict(node_map.get(node_id) or {})
        for edge in list(graph.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            if str(edge.get("from_node_id") or "").strip() != node_id:
                continue
            edge_id = str(edge.get("edge_id") or "").strip()
            if selected_edge_ids is not None and edge_id not in selected_edge_ids:
                continue
            context_policy = dict(edge.get("context_policy") or {})
            handoff_contract = dict(edge.get("handoff_contract") or {})
            input_envelope = self._build_graph_worker_input_envelope(
                edge=edge,
                output_bundle=output_bundle,
                output_envelope=output_envelope,
                generated_artifact_refs=generated_artifact_refs,
                bundle_paths=bundle_paths,
            )
            input_envelope_path = (
                Path(bundle_paths["output_json"]).parent / f"input-envelope-{str(edge.get('edge_id') or '').strip() or 'edge'}.json"
            ).as_posix()
            write_json(self._projects.require_workspace_root() / input_envelope_path, input_envelope)
            target_node_id = str(edge.get("to_node_id") or "").strip()
            target_node = dict(node_map.get(target_node_id) or {})
            agent_envelope_path = (
                Path(bundle_paths["output_json"]).parent / f"agent-envelope-{str(edge.get('edge_id') or '').strip() or 'edge'}.json"
            ).as_posix()
            agent_envelope = self._build_graph_worker_agent_envelope(
                graph=graph,
                edge=edge,
                source_node=source_node,
                target_node=target_node,
                output_bundle=output_bundle,
                input_envelope=input_envelope,
                bundle_paths={
                    **bundle_paths,
                    "input_envelope_json": input_envelope_path,
                },
            )
            write_json(self._projects.require_workspace_root() / agent_envelope_path, agent_envelope)
            self.durable_run_store().record_agent_envelope(agent_envelope)
            envelope_artifact_ref = {
                "artifact_id": f"{str(output_bundle.get('worker_thread_id') or '').strip()}-{str(edge.get('edge_id') or '').strip() or 'edge'}-agent-envelope-json",
                "artifact_kind": "structured_json",
                "path": agent_envelope_path,
                "status": "ready",
            }
            handoffs.append(
                {
                    "edge_id": str(edge.get("edge_id") or "").strip(),
                    "to_node_id": target_node_id,
                    "edge_type": str(edge.get("edge_type") or "").strip(),
                    "agent_envelope": {
                        "envelope_id": str(agent_envelope.get("envelope_id") or "").strip(),
                        "message_id": str(agent_envelope.get("message_id") or "").strip(),
                        "agent_envelope_path": agent_envelope_path,
                        "artifact_ref": envelope_artifact_ref,
                        "delivery": deepcopy(dict(agent_envelope.get("delivery") or {})),
                        "sender": deepcopy(dict(agent_envelope.get("sender") or {})),
                        "recipient": deepcopy(dict(agent_envelope.get("recipient") or {})),
                        "metadata": deepcopy(dict(agent_envelope.get("metadata") or {})),
                        "content_part_kinds": [
                            str(part.get("kind") or "").strip()
                            for part in list(agent_envelope.get("content") or [])
                            if isinstance(part, dict) and str(part.get("kind") or "").strip()
                        ],
                    },
                    "context_policy": {
                        "history_mode": str(context_policy.get("history_mode") or "").strip(),
                        "artifact_mode": str(context_policy.get("artifact_mode") or "").strip(),
                        "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
                        "include_machine_results": bool(context_policy.get("include_machine_results")),
                        "include_human_summaries": bool(context_policy.get("include_human_summaries")),
                        "summary_strategy": str(context_policy.get("summary_strategy") or "").strip(),
                        "history_length": int(context_policy.get("history_length") or 0),
                        "included_artifacts": [str(item).strip() for item in list(context_policy.get("included_artifacts") or []) if str(item or "").strip()],
                        "resource_refs": [str(item).strip() for item in list(context_policy.get("resource_refs") or []) if str(item or "").strip()],
                    },
                    "downstream_input": {
                        "source": "artifact_refs_and_context_policy",
                        "run_id": run_id,
                        "artifact_paths": [bundle_paths["output_json"], bundle_paths["summary_md"]],
                        "human_summary_path": bundle_paths["summary_md"] if output_bundle.get("human_summary") else None,
                        "machine_result_path": bundle_paths["output_json"],
                        "output_envelope_path": bundle_paths["output_envelope_json"],
                        "input_envelope_path": input_envelope_path,
                        "agent_envelope_path": agent_envelope_path,
                        "message_part_types": list(input_envelope.get("message_part_types") or []),
                        "delivery": deepcopy(dict(agent_envelope.get("delivery") or {})),
                        "artifact_refs": deepcopy(list(input_envelope.get("artifact_refs") or [])),
                        "resource_refs": deepcopy(list(input_envelope.get("resource_refs") or [])),
                        "exclude_private_memory": bool(input_envelope.get("exclude_private_memory")),
                        "handoff_contract": {
                            "message_part_modes": [str(item).strip() for item in list(handoff_contract.get("message_part_modes") or []) if str(item or "").strip()],
                            "required_output_schema_refs": [str(item).strip() for item in list(handoff_contract.get("required_output_schema_refs") or []) if str(item or "").strip()],
                        },
                    },
                }
            )
        return handoffs[:20]

    def _build_graph_worker_output_envelope(
        self,
        *,
        graph: dict[str, Any],
        source_node: dict[str, Any],
        output_bundle: dict[str, Any],
        output_contract: dict[str, Any],
        bundle_paths: dict[str, str],
        generated_artifact_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        human_summary = str(output_bundle.get("human_summary") or "").strip()
        machine_result = redact_sensitive(output_bundle.get("machine_result") or {})
        message_parts: list[dict[str, Any]] = []
        if isinstance(machine_result, dict) and machine_result:
            message_parts.append(
                {
                    "part_type": "machine_result",
                    "port_type": "structured_json",
                    "path": bundle_paths["output_json"],
                    "preview": _compact_text(machine_result, limit=240),
                }
            )
        if human_summary:
            message_parts.append(
                {
                    "part_type": "human_summary",
                    "port_type": "text",
                    "path": bundle_paths["summary_md"],
                    "preview": _compact_text(human_summary, limit=240),
                }
            )
        for item in generated_artifact_refs:
            if not isinstance(item, dict):
                continue
            message_parts.append(
                {
                    "part_type": "artifact_ref",
                    "artifact_id": str(item.get("artifact_id") or "").strip(),
                    "artifact_kind": str(item.get("artifact_kind") or "").strip(),
                    "path": str(item.get("path") or "").strip(),
                }
            )
        return {
            "schema_version": "astrabridge-task-graph-output-envelope-v1",
            "graph_id": str(graph.get("graph_id") or ""),
            "run_id": str(output_bundle.get("run_id") or ""),
            "task_id": str(output_bundle.get("task_id") or ""),
            "node_id": str(output_bundle.get("node_id") or ""),
            "worker_thread_id": str(output_bundle.get("worker_thread_id") or ""),
            "created_at": str(output_bundle.get("created_at") or now_iso()),
            "output_contract": {
                "artifact_only": bool(output_contract.get("artifact_only")),
                "human_summary_required": bool(output_contract.get("human_summary_required")),
                "artifact_outputs": list(output_contract.get("artifact_outputs") or []),
            },
            "source_node": {
                "node_id": str(source_node.get("node_id") or ""),
                "label": str(source_node.get("label") or ""),
                "kind": str(source_node.get("kind") or ""),
                "role": str(source_node.get("role") or ""),
            },
            "message_part_types": [str(item.get("part_type") or "").strip() for item in message_parts if str(item.get("part_type") or "").strip()],
            "message_parts": message_parts,
            "artifact_refs": deepcopy(generated_artifact_refs),
            "resource_refs": [],
            "exclude_private_memory": True,
        }

    def _build_graph_worker_input_envelope(
        self,
        *,
        edge: dict[str, Any],
        output_bundle: dict[str, Any],
        output_envelope: dict[str, Any],
        generated_artifact_refs: list[dict[str, Any]],
        bundle_paths: dict[str, str],
    ) -> dict[str, Any]:
        context_policy = dict(edge.get("context_policy") or {})
        handoff_contract = dict(edge.get("handoff_contract") or {})
        message_part_modes = {
            str(item).strip()
            for item in list(handoff_contract.get("message_part_modes") or [])
            if str(item or "").strip()
        }
        if not message_part_modes:
            message_part_modes = {"machine_result", "human_summary", "artifact_ref"}
        include_machine_results = bool(context_policy.get("include_machine_results"))
        include_human_summaries = bool(context_policy.get("include_human_summaries"))
        included_artifacts = {
            str(item).strip()
            for item in list(context_policy.get("included_artifacts") or [])
            if str(item or "").strip()
        }
        resource_refs = [str(item).strip() for item in list(context_policy.get("resource_refs") or []) if str(item or "").strip()]
        artifact_mode = str(context_policy.get("artifact_mode") or "").strip()
        selected_artifact_refs = []
        if artifact_mode != "none":
            for item in generated_artifact_refs:
                if not isinstance(item, dict):
                    continue
                artifact_id = str(item.get("artifact_id") or "").strip()
                artifact_kind = str(item.get("artifact_kind") or "").strip()
                if included_artifacts and artifact_id not in included_artifacts and artifact_kind not in included_artifacts:
                    continue
                selected_artifact_refs.append(
                    {
                        "artifact_id": artifact_id,
                        "artifact_kind": artifact_kind,
                        "path": str(item.get("path") or "").strip(),
                        "status": str(item.get("status") or "").strip() or "ready",
                    }
                )

        message_parts: list[dict[str, Any]] = []
        if include_machine_results and "machine_result" in message_part_modes:
            machine_result = redact_sensitive(output_bundle.get("machine_result") or {})
            if isinstance(machine_result, dict) and machine_result:
                message_parts.append(
                    {
                        "part_type": "machine_result",
                        "port_type": "structured_json",
                        "path": bundle_paths["output_json"],
                        "preview": _compact_text(machine_result, limit=240),
                    }
                )
        if include_human_summaries and "human_summary" in message_part_modes:
            human_summary = str(output_bundle.get("human_summary") or "").strip()
            if human_summary:
                message_parts.append(
                    {
                        "part_type": "human_summary",
                        "port_type": "text",
                        "path": bundle_paths["summary_md"],
                        "preview": _compact_text(human_summary, limit=240),
                    }
                )
        if "artifact_ref" in message_part_modes:
            for item in selected_artifact_refs:
                message_parts.append(
                    {
                        "part_type": "artifact_ref",
                        "artifact_id": str(item.get("artifact_id") or "").strip(),
                        "artifact_kind": str(item.get("artifact_kind") or "").strip(),
                        "path": str(item.get("path") or "").strip(),
                    }
                )
        for ref in resource_refs:
            message_parts.append(
                {
                    "part_type": "resource_ref",
                    "path": ref,
                }
            )
        return {
            "schema_version": "astrabridge-task-graph-input-envelope-v1",
            "graph_id": str(output_bundle.get("graph_id") or ""),
            "run_id": str(output_bundle.get("run_id") or ""),
            "task_id": str(output_bundle.get("task_id") or ""),
            "from_node_id": str(edge.get("from_node_id") or ""),
            "to_node_id": str(edge.get("to_node_id") or ""),
            "edge_id": str(edge.get("edge_id") or ""),
            "created_at": str(output_bundle.get("created_at") or now_iso()),
            "context_policy": {
                "history_mode": str(context_policy.get("history_mode") or "").strip(),
                "artifact_mode": artifact_mode,
                "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
                "include_machine_results": include_machine_results,
                "include_human_summaries": include_human_summaries,
                "summary_strategy": str(context_policy.get("summary_strategy") or "").strip(),
                "included_artifacts": sorted(included_artifacts),
                "resource_refs": resource_refs,
            },
            "handoff_contract": {
                "message_template": str(handoff_contract.get("message_template") or "").strip(),
                "message_part_modes": sorted(message_part_modes),
                "required_output_schema_refs": [str(item).strip() for item in list(handoff_contract.get("required_output_schema_refs") or []) if str(item or "").strip()],
            },
            "source_output_envelope_path": bundle_paths["output_envelope_json"],
            "message_part_types": [str(item.get("part_type") or "").strip() for item in message_parts if str(item.get("part_type") or "").strip()],
            "message_parts": message_parts,
            "artifact_refs": selected_artifact_refs,
            "resource_refs": resource_refs,
            "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
        }

    def _build_graph_worker_agent_envelope(
        self,
        *,
        graph: dict[str, Any],
        edge: dict[str, Any],
        source_node: dict[str, Any],
        target_node: dict[str, Any],
        output_bundle: dict[str, Any],
        input_envelope: dict[str, Any],
        bundle_paths: dict[str, str],
    ) -> dict[str, Any]:
        task_id = str(output_bundle.get("task_id") or "").strip()
        run_id = str(output_bundle.get("run_id") or "").strip()
        graph_id = str(graph.get("graph_id") or output_bundle.get("graph_id") or "").strip()
        source_node_id = str(source_node.get("node_id") or output_bundle.get("node_id") or "").strip()
        target_node_id = str(target_node.get("node_id") or edge.get("to_node_id") or "").strip()
        edge_id = str(edge.get("edge_id") or "").strip()
        attempt_count = max(1, int(output_bundle.get("attempt_count") or 1))
        correlation_id = self._graph_worker_stable_identifier("corr", run_id, source_node_id, attempt_count)
        causation_id = self._graph_worker_stable_identifier("cause", run_id, source_node_id, attempt_count, "output")
        envelope_id = self._graph_worker_stable_identifier("envelope", run_id, edge_id, source_node_id, target_node_id, attempt_count)
        message_id = self._graph_worker_stable_identifier("message", run_id, edge_id, source_node_id, target_node_id, attempt_count)
        delivery_idempotency_key = self._graph_worker_stable_identifier("delivery", run_id, edge_id, source_node_id, target_node_id, attempt_count)
        artifact_refs = [
            self._graph_worker_protocol_artifact_ref(
                item,
                task_id=task_id,
                run_id=run_id,
                source_node_id=source_node_id,
            )
            for item in list(input_envelope.get("artifact_refs") or [])
            if isinstance(item, dict)
        ]
        typed_handoff = self._build_graph_worker_typed_handoff_projection(
            graph=graph,
            edge=edge,
            source_node=source_node,
            target_node=target_node,
            output_bundle=output_bundle,
            artifact_refs=artifact_refs,
        )
        content = self._graph_worker_content_parts(
            output_bundle=output_bundle,
            message_parts=[dict(item) for item in list(input_envelope.get("message_parts") or []) if isinstance(item, dict)],
            artifact_refs=artifact_refs,
        )
        if not content:
            raise ValueError(f"Graph handoff {edge_id or target_node_id} did not produce any structured content parts.")
        context_policy = dict(input_envelope.get("context_policy") or {})
        handoff_contract = dict(input_envelope.get("handoff_contract") or {})
        sender = {
            "agent_id": self._graph_worker_stable_identifier("agent", graph_id, source_node_id),
            "provider_id": str(output_bundle.get("provider_id") or source_node.get("provider_id") or "unknown").strip() or "unknown",
        }
        sender_model_id = str(output_bundle.get("model") or source_node.get("model_id") or "").strip()
        if sender_model_id:
            sender["model_id"] = sender_model_id
        sender_lane_id = str(output_bundle.get("worker_thread_id") or "").strip()
        if sender_lane_id:
            sender["lane_id"] = sender_lane_id
        recipient = {
            "agent_id": self._graph_worker_stable_identifier("agent", graph_id, target_node_id),
            "provider_id": str(target_node.get("provider_id") or "unknown").strip() or "unknown",
        }
        recipient_model_id = str(target_node.get("model_id") or "").strip()
        if recipient_model_id:
            recipient["model_id"] = recipient_model_id
        if target_node_id:
            recipient["lane_id"] = target_node_id
        envelope = {
            "envelope_id": envelope_id,
            "schema_version": PROTOCOL_SCHEMA_VERSION,
            "message_id": message_id,
            "task_id": task_id,
            "run_id": run_id,
            "sender": sender,
            "recipient": recipient,
            "kind": "handoff",
            "content": content,
            "created_at": str(output_bundle.get("created_at") or now_iso()),
            "delivery": {
                "attempt": attempt_count,
                "idempotency_key": delivery_idempotency_key,
                "trace_id": str(output_bundle.get("trace_id") or f"trace-{run_id}"),
                "sequence": max(0, attempt_count - 1),
            },
            "security_policy": {
                "exclude_private_memory": bool(input_envelope.get("exclude_private_memory")),
                "redaction_applied": True,
            },
            "metadata": {
                "graph_id": graph_id,
                "context_id": str(output_bundle.get("context_id") or f"context-{run_id}"),
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
                "edge_id": edge_id,
                "intent": "graph_node_handoff",
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "deadline_at": None,
                "ttl_seconds": 0,
                "schema_refs": [str(item).strip() for item in list(handoff_contract.get("required_output_schema_refs") or []) if str(item or "").strip()],
                "context_policy_snapshot": context_policy,
                "budget": deepcopy(dict(output_bundle.get("budget") or {})),
                "typed_handoff": typed_handoff,
                "provenance": {
                    "source_output_envelope_path": bundle_paths["output_envelope_json"],
                    "legacy_input_envelope_path": bundle_paths.get("input_envelope_json"),
                    "source_worker_thread_id": str(output_bundle.get("worker_thread_id") or "").strip() or None,
                    "source_status": str(output_bundle.get("status") or "").strip() or None,
                    "retry_count": int(output_bundle.get("retry_count") or 0),
                },
                "message_part_types": [str(part.get("kind") or "").strip() for part in content if str(part.get("kind") or "").strip()],
            },
        }
        return validate_protocol_payload("AgentEnvelope", envelope)

    def _load_graph_handoff_agent_envelope(
        self,
        handoff: dict[str, Any],
        *,
        expected_target_node_id: str,
        graph_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        downstream_input = dict(handoff.get("downstream_input") or {})
        relative_path = str(downstream_input.get("agent_envelope_path") or "").strip()
        if not relative_path:
            raise ValueError("downstream handoff is missing agent_envelope_path.")
        envelope_path = resolve_under(self._projects.require_workspace_root(), relative_path)
        if envelope_path is None or not envelope_path.exists():
            raise ValueError(f"agent envelope path is missing: {relative_path}")
        loaded = json.loads(envelope_path.read_text(encoding="utf-8"))
        envelope = validate_protocol_payload("AgentEnvelope", loaded)
        metadata = dict(envelope.get("metadata") or {})
        security_policy = dict(envelope.get("security_policy") or {})
        recipient = dict(envelope.get("recipient") or {})
        delivery = dict(envelope.get("delivery") or {})
        required_metadata = (
            "graph_id",
            "context_id",
            "source_node_id",
            "target_node_id",
            "edge_id",
            "intent",
            "correlation_id",
            "causation_id",
            "schema_refs",
            "context_policy_snapshot",
            "budget",
            "provenance",
        )
        missing = [field for field in required_metadata if field not in metadata]
        if missing:
            raise ValueError(f"agent envelope is missing required metadata fields: {', '.join(missing)}")
        if str(metadata.get("target_node_id") or "").strip() != expected_target_node_id:
            raise ValueError("agent envelope target node does not match the requested node.")
        if str(recipient.get("lane_id") or "").strip() and str(recipient.get("lane_id") or "").strip() != expected_target_node_id:
            raise ValueError("agent envelope recipient lane_id does not match the target node.")
        if str(recipient.get("agent_id") or "").strip() != self._graph_worker_stable_identifier("agent", metadata.get("graph_id"), expected_target_node_id):
            raise ValueError("agent envelope recipient agent_id does not match the target node.")
        if str(metadata.get("intent") or "").strip() != "graph_node_handoff":
            raise ValueError("agent envelope intent must be graph_node_handoff.")
        if not bool(security_policy.get("exclude_private_memory")):
            raise ValueError("agent envelope must exclude private memory.")
        if int(delivery.get("attempt") or 0) <= 0:
            raise ValueError("agent envelope delivery attempt must be positive.")
        if not isinstance(envelope.get("content"), list) or not list(envelope.get("content") or []):
            raise ValueError("agent envelope content must contain at least one structured part.")
        if isinstance(graph_definition, dict):
            orchestration_graph = (
                graph_definition
                if graph_definition.get("schema_registry") is not None
                else self._orchestration_graph_for_task_graph(graph_definition)
            )
            typed_handoff = self._validate_graph_handoff_typed_projection(
                graph=orchestration_graph,
                envelope=envelope,
            )
            envelope["metadata"] = {
                **metadata,
                "typed_handoff": typed_handoff,
            }
        return envelope

    def _graph_worker_summary_markdown(self, output_bundle: dict[str, Any]) -> str:
        human_summary = str(output_bundle.get("human_summary") or "").strip()
        hints = [str(item).strip() for item in list(output_bundle.get("next_action_hints") or []) if str(item or "").strip()]
        lines = [
            "# Worker output",
            "",
            f"- Node: `{output_bundle.get('node_id')}`",
            f"- Worker thread: `{output_bundle.get('worker_thread_id')}`",
            f"- Role: `{dict(output_bundle.get('provenance') or {}).get('agent_role') or ''}`",
            f"- Created at: `{output_bundle.get('created_at')}`",
            "",
        ]
        if human_summary:
            lines.extend(["## Human summary", "", human_summary, ""])
        machine_preview = _compact_text(redact_sensitive(output_bundle.get("machine_result") or {}), limit=480)
        if machine_preview:
            lines.extend(["## Machine result preview", "", "```json", machine_preview, "```", ""])
        if hints:
            lines.extend(["## Next actions", ""])
            lines.extend([f"- {hint}" for hint in hints])
            lines.append("")
        return "\n".join(lines)

    def _fixture_run_report_markdown(self, report_payload: dict[str, Any]) -> str:
        lines = [
            "# Fixture run",
            "",
            f"- Run id: `{report_payload.get('run_id')}`",
            f"- Graph id: `{report_payload.get('graph_id')}`",
            f"- Status: `{report_payload.get('run_status')}`",
            "",
            "## Node results",
            "",
        ]
        for item in list(report_payload.get("node_results") or []):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("node_id") or "node")
            outcome = str(item.get("outcome") or "")
            status = str(item.get("status") or "")
            reasons = [str(reason).strip() for reason in list(item.get("reasons") or []) if str(reason or "").strip()]
            lines.append(f"- **{label}**: `{outcome}` / `{status}`")
            for reason in reasons:
                lines.append(f"  - {reason}")
        lines.append("")
        return "\n".join(lines)

    def _cancelled_run_report_markdown(self, report_payload: dict[str, Any]) -> str:
        lines = [
            "# Cancelled task graph run",
            "",
            f"- Run id: `{report_payload.get('run_id')}`",
            f"- Graph id: `{report_payload.get('graph_id')}`",
            f"- Previous status: `{report_payload.get('previous_status')}`",
            f"- Cancelled at: `{report_payload.get('cancelled_at')}`",
            "",
            "## Summary",
            "",
            str(report_payload.get("summary") or "Run cancelled."),
            "",
        ]
        if report_payload.get("notes"):
            lines.extend(["## Notes", "", str(report_payload.get("notes") or ""), ""])
        return "\n".join(lines)

    def _load_full_graph_run(self, run_ref: dict[str, Any]) -> dict[str, Any] | None:
        artifact_refs = [dict(item) for item in list(run_ref.get("artifact_refs") or []) if isinstance(item, dict)]
        manifest_ref = next(
            (
                item
                for item in artifact_refs
                if str(item.get("artifact_kind") or "").strip() == "structured_json"
                and str(item.get("artifact_id") or "").strip().endswith("-run-manifest-json")
            ),
            None,
        )
        if manifest_ref is None:
            return None
        relative_path = str(manifest_ref.get("path") or "").strip()
        if not relative_path:
            return None
        workspace_root = self._projects.require_workspace_root()
        manifest_path = resolve_under(workspace_root, relative_path)
        if manifest_path is None or not manifest_path.exists():
            return None
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return dict(loaded) if isinstance(loaded, dict) else None

    def _persist_full_graph_run(self, run_ref: dict[str, Any], run: dict[str, Any]) -> bool:
        artifact_refs = [dict(item) for item in list(run_ref.get("artifact_refs") or []) if isinstance(item, dict)]
        manifest_ref = next(
            (
                item
                for item in artifact_refs
                if str(item.get("artifact_kind") or "").strip() == "structured_json"
                and str(item.get("artifact_id") or "").strip().endswith("-run-manifest-json")
            ),
            None,
        )
        if manifest_ref is None:
            return False
        relative_path = str(manifest_ref.get("path") or "").strip()
        if not relative_path:
            return False
        workspace_root = self._projects.require_workspace_root()
        manifest_path = resolve_under(workspace_root, relative_path)
        if manifest_path is None:
            return False
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(manifest_path, run)
        return True

    @staticmethod
    def _graph_recovery_closure(*, initial_targets: list[str], downstream_by_node: dict[str, list[str]]) -> set[str]:
        closure = {str(item).strip() for item in list(initial_targets or []) if str(item or "").strip()}
        queue = list(closure)
        while queue:
            node_id = queue.pop(0)
            for downstream in list(downstream_by_node.get(node_id) or []):
                clean = str(downstream or "").strip()
                if not clean or clean in closure:
                    continue
                closure.add(clean)
                queue.append(clean)
        return closure

    def _graph_recovery_report_markdown(self, manifest: dict[str, Any]) -> str:
        lines = [
            "# Task graph recovery",
            "",
            f"- Recovery id: `{manifest.get('recovery_id')}`",
            f"- Source run id: `{manifest.get('source_run_id')}`",
            f"- Strategy: `{manifest.get('strategy')}`",
            f"- Source status: `{manifest.get('source_run_status')}`",
            f"- Selected node ids: `{', '.join(list(manifest.get('selected_node_ids') or [])) or '-'}`",
            f"- Initial targets: `{', '.join(list(manifest.get('initial_target_node_ids') or [])) or '-'}`",
            f"- Rerun node ids: `{', '.join(list(manifest.get('rerun_node_ids') or [])) or '-'}`",
            f"- Reused node ids: `{', '.join(list(manifest.get('reused_node_ids') or [])) or '-'}`",
            "",
            "## Effective Fixture Behaviors",
            "",
        ]
        for node_id, behavior in dict(manifest.get("effective_node_behaviors") or {}).items():
            lines.append(f"- `{node_id}` -> `{behavior}`")
        lines.append("")
        return "\n".join(lines)

    def _normalize_graph_worker_binding(
        self,
        value: Any,
        *,
        graph_id: str,
        run_id: str,
        node_ids: set[str],
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        binding_id = str(value.get("binding_id") or "").strip()
        node_id = str(value.get("node_id") or "").strip()
        worker_thread_id = str(value.get("worker_thread_id") or "").strip()
        current_graph_id = str(value.get("graph_id") or graph_id).strip()
        current_run_id = str(value.get("run_id") or run_id).strip()
        if not binding_id or not node_id or not worker_thread_id:
            return None
        if current_graph_id != graph_id or current_run_id != run_id:
            return None
        if node_ids and node_id not in node_ids:
            return None
        artifact_refs: list[dict[str, Any]] = []
        for item in list(value.get("artifact_refs") or []):
            if not isinstance(item, dict):
                continue
            artifact_path = str(item.get("path") or "").strip()
            artifact_kind = str(item.get("artifact_kind") or "").strip()
            artifact_status = str(item.get("status") or "").strip() or "ready"
            if not artifact_path or not artifact_kind:
                continue
            artifact_refs.append(
                {
                    "artifact_id": str(item.get("artifact_id") or "").strip() or new_id("graph-artifact"),
                    "artifact_kind": artifact_kind,
                    "path": artifact_path,
                    "status": artifact_status,
                }
            )
        output_summary = value.get("output_summary")
        normalized_output_summary = None
        if isinstance(output_summary, dict):
            normalized_output_summary = {
                "human_summary": _compact_text(redact_sensitive(output_summary.get("human_summary") or ""), limit=240),
                "machine_result_preview": _compact_text(redact_sensitive(output_summary.get("machine_result_preview") or ""), limit=240),
                "confidence": redact_sensitive(output_summary.get("confidence")),
                "next_action_hints": [
                    _compact_text(redact_sensitive(item), limit=240)
                    for item in list(output_summary.get("next_action_hints") or [])
                    if str(item or "").strip()
                ][:8],
                "artifact_bundle_path": str(output_summary.get("artifact_bundle_path") or "").strip(),
                "output_envelope_path": str(output_summary.get("output_envelope_path") or "").strip(),
            }
        runtime_contract = dict(value.get("runtime_contract") or {})
        normalized_runtime_contract = {
            "profile_id": str(runtime_contract.get("profile_id") or "").strip(),
            "provider_id": str(runtime_contract.get("provider_id") or "").strip(),
            "model": str(runtime_contract.get("model") or "").strip(),
            "reasoning_effort": str(runtime_contract.get("reasoning_effort") or "").strip(),
            "permission_mode": str(runtime_contract.get("permission_mode") or "").strip(),
            "collaboration_mode": str(runtime_contract.get("collaboration_mode") or "").strip() or "default",
            "execution_backend": str(runtime_contract.get("execution_backend") or "").strip(),
            "spawn_mode": str(runtime_contract.get("spawn_mode") or "").strip(),
            "timeout_ms": int(runtime_contract.get("timeout_ms") or 0),
            "mcp_preset_ids": [
                str(entry).strip()
                for entry in list(runtime_contract.get("mcp_preset_ids") or [])
                if str(entry or "").strip()
            ][:16],
            "skill_ids": [
                str(entry).strip()
                for entry in list(runtime_contract.get("skill_ids") or [])
                if str(entry or "").strip()
            ][:16],
            "prompt_template_mode": str(runtime_contract.get("prompt_template_mode") or "").strip(),
            "tool_policy": {
                "approval_mode": str(dict(runtime_contract.get("tool_policy") or {}).get("approval_mode") or "").strip(),
                "allowed_tool_classes": [
                    str(entry).strip()
                    for entry in list(dict(runtime_contract.get("tool_policy") or {}).get("allowed_tool_classes") or [])
                    if str(entry or "").strip()
                ][:16],
                "supports_mcp": bool(dict(runtime_contract.get("tool_policy") or {}).get("supports_mcp")),
                "mcp_tool_policy": deepcopy(dict(dict(runtime_contract.get("tool_policy") or {}).get("mcp_tool_policy") or {})),
            },
            "subagent_policy": {
                "isolation_mode": str(dict(runtime_contract.get("subagent_policy") or {}).get("isolation_mode") or "").strip(),
                "max_turns": int(dict(runtime_contract.get("subagent_policy") or {}).get("max_turns") or 0),
                "allow_direct_teammate_messages": bool(dict(runtime_contract.get("subagent_policy") or {}).get("allow_direct_teammate_messages")),
                "share_worktree": bool(dict(runtime_contract.get("subagent_policy") or {}).get("share_worktree")),
                "allow_nested_subagents": bool(dict(runtime_contract.get("subagent_policy") or {}).get("allow_nested_subagents")),
            },
        }
        downstream_handoffs: list[dict[str, Any]] = []
        for item in list(value.get("downstream_handoffs") or []):
            if not isinstance(item, dict):
                continue
            context_policy = dict(item.get("context_policy") or {})
            downstream_input = dict(item.get("downstream_input") or {})
            downstream_handoffs.append(
                {
                    "edge_id": str(item.get("edge_id") or "").strip(),
                    "to_node_id": str(item.get("to_node_id") or "").strip(),
                    "edge_type": str(item.get("edge_type") or "").strip(),
                    "agent_envelope": {
                        "envelope_id": str(dict(item.get("agent_envelope") or {}).get("envelope_id") or "").strip() or None,
                        "message_id": str(dict(item.get("agent_envelope") or {}).get("message_id") or "").strip() or None,
                        "agent_envelope_path": str(dict(item.get("agent_envelope") or {}).get("agent_envelope_path") or "").strip() or None,
                        "delivery": deepcopy(dict(dict(item.get("agent_envelope") or {}).get("delivery") or {})),
                        "sender": deepcopy(dict(dict(item.get("agent_envelope") or {}).get("sender") or {})),
                        "recipient": deepcopy(dict(dict(item.get("agent_envelope") or {}).get("recipient") or {})),
                        "metadata": deepcopy(dict(dict(item.get("agent_envelope") or {}).get("metadata") or {})),
                        "content_part_kinds": [
                            str(entry).strip()
                            for entry in list(dict(item.get("agent_envelope") or {}).get("content_part_kinds") or [])
                            if str(entry or "").strip()
                        ],
                        "artifact_ref": (
                            {
                                "artifact_id": str(dict(dict(item.get("agent_envelope") or {}).get("artifact_ref") or {}).get("artifact_id") or "").strip(),
                                "artifact_kind": str(dict(dict(item.get("agent_envelope") or {}).get("artifact_ref") or {}).get("artifact_kind") or "").strip(),
                                "path": str(dict(dict(item.get("agent_envelope") or {}).get("artifact_ref") or {}).get("path") or "").strip(),
                                "status": str(dict(dict(item.get("agent_envelope") or {}).get("artifact_ref") or {}).get("status") or "").strip() or "ready",
                            }
                            if isinstance(dict(item.get("agent_envelope") or {}).get("artifact_ref"), dict)
                            else None
                        ),
                    },
                    "context_policy": {
                        "history_mode": str(context_policy.get("history_mode") or "").strip(),
                        "artifact_mode": str(context_policy.get("artifact_mode") or "").strip(),
                        "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
                        "include_machine_results": bool(context_policy.get("include_machine_results")),
                        "include_human_summaries": bool(context_policy.get("include_human_summaries")),
                        "summary_strategy": str(context_policy.get("summary_strategy") or "").strip(),
                        "history_length": int(context_policy.get("history_length") or 0),
                        "included_artifacts": [str(entry).strip() for entry in list(context_policy.get("included_artifacts") or []) if str(entry or "").strip()],
                        "resource_refs": [str(entry).strip() for entry in list(context_policy.get("resource_refs") or []) if str(entry or "").strip()],
                    },
                    "downstream_input": {
                        "source": str(downstream_input.get("source") or "").strip(),
                        "run_id": str(downstream_input.get("run_id") or "").strip(),
                        "artifact_paths": [str(entry).strip() for entry in list(downstream_input.get("artifact_paths") or []) if str(entry or "").strip()],
                        "human_summary_path": str(downstream_input.get("human_summary_path") or "").strip() or None,
                        "machine_result_path": str(downstream_input.get("machine_result_path") or "").strip() or None,
                        "output_envelope_path": str(downstream_input.get("output_envelope_path") or "").strip() or None,
                        "input_envelope_path": str(downstream_input.get("input_envelope_path") or "").strip() or None,
                        "agent_envelope_path": str(downstream_input.get("agent_envelope_path") or "").strip() or None,
                        "message_part_types": [str(entry).strip() for entry in list(downstream_input.get("message_part_types") or []) if str(entry or "").strip()],
                        "delivery": deepcopy(dict(downstream_input.get("delivery") or {})),
                        "artifact_refs": [
                            {
                                "artifact_id": str(entry.get("artifact_id") or "").strip(),
                                "artifact_kind": str(entry.get("artifact_kind") or "").strip(),
                                "path": str(entry.get("path") or "").strip(),
                                "status": str(entry.get("status") or "").strip() or "ready",
                            }
                            for entry in list(downstream_input.get("artifact_refs") or [])
                            if isinstance(entry, dict)
                            and str(entry.get("artifact_id") or "").strip()
                            and str(entry.get("path") or "").strip()
                        ],
                        "resource_refs": [str(entry).strip() for entry in list(downstream_input.get("resource_refs") or []) if str(entry or "").strip()],
                        "exclude_private_memory": bool(downstream_input.get("exclude_private_memory")),
                        },
                }
            )
        return {
            "binding_id": binding_id,
            "graph_id": graph_id,
            "run_id": run_id,
            "node_id": node_id,
            "worker_thread_id": worker_thread_id,
            "parent_thread_id": str(value.get("parent_thread_id") or "").strip(),
            "spawn_mode": str(value.get("spawn_mode") or "").strip(),
            "worker_origin": str(value.get("worker_origin") or "").strip(),
            "agent_role": str(value.get("agent_role") or "").strip(),
            "agent_nickname": str(value.get("agent_nickname") or "").strip(),
            "status": str(value.get("status") or "").strip() or "queued",
            "execution_backend": str(value.get("execution_backend") or "").strip(),
            "runtime_contract": normalized_runtime_contract,
            "artifact_refs": artifact_refs[:16],
            "output_summary": normalized_output_summary,
            "downstream_handoffs": downstream_handoffs[:20],
            "created_at": str(value.get("created_at") or "").strip() or now_iso(),
            "updated_at": str(value.get("updated_at") or "").strip() or now_iso(),
        }

    def _graph_activity_summary(self, task: dict[str, Any]) -> dict[str, Any]:
        return self._graph_run_refs.graph_activity_summary(task)

    def _select_reloaded_task(
        self,
        tasks: list[dict[str, Any]],
        *,
        current_task_id: str,
        preferred_thread_id: str,
    ) -> dict[str, Any] | None:
        existing = self._find_task(tasks, current_task_id)
        if existing:
            return existing
        if preferred_thread_id:
            for task in tasks:
                for item in list(task.get("provider_threads") or []):
                    if str((item or {}).get("thread_id") or "").strip() == preferred_thread_id:
                        return dict(task)
        if tasks:
            tasks = [dict(item) for item in tasks]
            tasks.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return tasks[0]
        return None

    def _preferred_active_thread_id(self, task: dict[str, Any], provider_threads: list[dict[str, Any]]) -> str:
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        live_threads = [
            dict(item)
            for item in provider_threads
            if not item.get("missing_at") and _provider_thread_entry_is_plausible(item)
        ]
        live_ids = {str(item.get("thread_id") or "").strip() for item in live_threads}
        known_ids = {str(item.get("thread_id") or "").strip() for item in provider_threads}
        project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
        current_task_id = str((self._projects.current_project or {}).get("current_task_id") or "").strip()
        task_id = str(task.get("task_id") or "").strip()
        if active_thread_id and active_thread_id in live_ids:
            return active_thread_id
        if task_id and current_task_id == task_id and project_thread_id and project_thread_id in live_ids:
            return project_thread_id
        if project_thread_id and project_thread_id in live_ids:
            return project_thread_id
        if live_threads:
            live_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return str(live_threads[0].get("thread_id") or "").strip()
        if active_thread_id and active_thread_id in known_ids:
            return active_thread_id
        if project_thread_id and project_thread_id in known_ids:
            return project_thread_id
        if provider_threads:
            provider_threads = [dict(item) for item in provider_threads]
            provider_threads.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return str(provider_threads[0].get("thread_id") or "").strip()
        return ""

    def _thread_context_hint(self, thread_id: str) -> dict[str, Any]:
        """Return secret-free task continuity hints for a known Codex thread."""
        if not thread_id:
            return {}
        shell_root = self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME
        merged: dict[str, Any] = {}
        context_state = read_json(shell_root / "project_context_state.json", {})
        context_threads = context_state.get("threads") if isinstance(context_state, dict) else None
        if isinstance(context_threads, dict):
            context_entry = context_threads.get(thread_id)
            if isinstance(context_entry, dict):
                merged.update(context_entry)
        thread_cache = read_json(shell_root / "thread_cache.json", {})
        cache_entry = (thread_cache.get("by_id") or {}).get(thread_id) if isinstance(thread_cache, dict) else None
        if isinstance(cache_entry, dict):
            merged.update({key: value for key, value in cache_entry.items() if value is not None})
        provider_id = merged.get("provider_id")
        if not provider_id:
            model_text = str(merged.get("model") or "")
            if "/" in model_text:
                provider_id = model_text.split("/", 1)[0]
        return redact_sensitive(
            {
                "profile_id": merged.get("profile_id"),
                "provider_id": provider_id,
                "model": merged.get("model"),
                "reasoning_effort": merged.get("reasoning_effort"),
                "permission_mode": merged.get("permission_mode"),
                "collaboration_mode": merged.get("collaboration_mode"),
                "name": merged.get("name"),
                "goal": merged.get("goal"),
                "latest_plan": merged.get("latest_plan"),
            }
        )

    def _save_task(self, task: dict[str, Any]) -> None:
        state = self._state()
        persisted_task = self._find_task(list(state.get("tasks") or []), str(task.get("task_id") or ""))
        if persisted_task:
            task = self._merge_task_graph_state(persisted_task, task)
        updated_tasks = self._replace_task(list(state.get("tasks") or []), task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)

    def _merge_task_graph_state(self, persisted_task: dict[str, Any], incoming_task: dict[str, Any]) -> dict[str, Any]:
        merged = dict(persisted_task)
        merged.update(incoming_task)
        merged["graph_definitions"] = self._merge_task_graph_definitions(
            persisted_task.get("graph_definitions"),
            incoming_task.get("graph_definitions"),
        )
        merged["graph_run_refs"] = self._merge_task_graph_run_refs(
            persisted_task.get("graph_run_refs"),
            incoming_task.get("graph_run_refs"),
        )
        merged["graph_snapshot_refs"] = self._merge_task_graph_snapshot_refs(
            persisted_task.get("graph_snapshot_refs"),
            incoming_task.get("graph_snapshot_refs"),
        )
        return merged

    def _merge_task_graph_definitions(self, persisted: Any, incoming: Any) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        ordered_ids: list[str] = []
        for source in (incoming, persisted):
            for item in list(source or []):
                if not isinstance(item, dict):
                    continue
                graph_id = str(item.get("graph_id") or "").strip()
                if not graph_id:
                    continue
                if graph_id not in ordered_ids:
                    ordered_ids.append(graph_id)
                if graph_id not in by_id:
                    by_id[graph_id] = dict(item)
        merged = [by_id[graph_id] for graph_id in ordered_ids if graph_id in by_id]
        return self._prune_graph_definitions(merged, task_id="")

    def _orchestration_graph_for_task_graph(self, task_graph: dict[str, Any]) -> dict[str, Any]:
        base = dict(dict(task_graph.get("graph_document") or {}).get("canonical_graph") or {})
        if not base:
            base = dict(task_graph.get("orchestration_graph") or {})
        if base:
            return self._sync_orchestration_graph_with_task_graph(base, task_graph=task_graph)
        return self._sync_orchestration_graph_with_task_graph(
            lift_task_graph_to_agent_orchestration_graph(task_graph),
            task_graph=task_graph,
        )

    def _sync_orchestration_graph_with_task_graph(self, orchestration_graph: dict[str, Any], *, task_graph: dict[str, Any]) -> dict[str, Any]:
        executable_graph = self._reachable_task_graph_projection(task_graph)
        existing_graph = deepcopy(orchestration_graph) if isinstance(orchestration_graph, dict) else {}
        interop_source_format = self._graph_interop_source_format({"orchestration_graph": existing_graph})
        try:
            canonical_lifted = lift_task_graph_to_agent_orchestration_graph(executable_graph)
        except Exception:
            if (
                existing_graph
                and interop_source_format
                in {COMFYUI_WORKFLOW_SOURCE_FORMAT, LANGGRAPH_STATEGRAPH_SOURCE_FORMAT}
            ):
                canonical_lifted = validate_agent_orchestration_graph(existing_graph)
            else:
                raise
        synced = {**deepcopy(canonical_lifted), **existing_graph}
        synced["graph_id"] = task_graph["graph_id"]
        synced["task_id"] = task_graph["task_id"]
        synced["title"] = task_graph["title"]
        synced["template_id"] = task_graph["template_id"]
        synced["status"] = task_graph["status"]
        synced["state_version"] = task_graph["state_version"]
        synced["graph_policy"] = {
            **dict(synced.get("graph_policy") or {}),
            "entry_node_ids": list(dict(task_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
        }
        metadata = dict(synced.get("metadata") or {})
        metadata["updated_at"] = str(task_graph.get("updated_at") or metadata.get("updated_at") or now_iso())
        synced["metadata"] = metadata
        schema_registry = dict(synced.get("schema_registry") or {})
        node_schema_refs: dict[str, str] = {}

        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(executable_graph.get("nodes") or [])
            if isinstance(item, dict)
        }
        existing_nodes = {
            str(item.get("node_id") or "").strip(): deepcopy(item)
            for item in list(existing_graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        synced["nodes"] = [
            {
                **deepcopy(item),
                **deepcopy(existing_nodes.get(str(item.get("node_id") or "").strip()) or {}),
            }
            for item in list(canonical_lifted.get("nodes") or [])
            if isinstance(item, dict)
        ]
        for node in list(synced.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            task_node = node_map.get(str(node.get("node_id") or "").strip())
            if not task_node:
                continue
            task_ui_hints = dict(task_node.get("ui_hints") or {})
            if (
                str(task_node.get("kind") or "").strip() == OPAQUE_DISABLED_NODE_TYPE_ID
                and str(task_ui_hints.get("original_node_type_kind") or "").strip()
            ):
                node["kind"] = str(task_ui_hints.get("original_node_type_kind") or "").strip()
                diagnostics = [
                    deepcopy(item)
                    for item in list(task_ui_hints.get("node_type_diagnostics") or [])
                    if isinstance(item, dict)
                ]
                if diagnostics:
                    node["node_type_diagnostics"] = diagnostics
                    node["status"] = "disabled"
            else:
                node["kind"] = task_node.get("kind")
            node["label"] = task_node.get("label")
            node["card_ref"] = task_node.get("agent_card_ref")
            routing = dict(node.get("routing") or {})
            provider_id = str(task_node.get("provider_id") or "").strip()
            model_id = str(task_node.get("model_id") or "").strip()
            if provider_id and model_id:
                routing.update(
                    {
                        "selection_mode": "explicit",
                        "provider_id": provider_id,
                        "model_id": model_id,
                    }
                )
            elif provider_id:
                routing.update({"selection_mode": "explicit", "provider_id": provider_id})
            elif model_id:
                routing.update({"selection_mode": "explicit", "model_id": model_id})
            node["routing"] = routing
            prompt = dict(node.get("prompt") or {})
            human_summary_template = str(task_node.get("human_summary_template") or "").strip()
            if human_summary_template:
                prompt["template"] = human_summary_template
            node["prompt"] = prompt
            execution = dict(node.get("execution") or {})
            execution_policy = dict(task_node.get("execution_policy") or {})
            if execution_policy:
                execution["spawn_mode"] = execution_policy.get("spawn_mode", execution.get("spawn_mode"))
                execution["timeout_ms"] = execution_policy.get("timeout_ms", execution.get("timeout_ms"))
                execution["retry_policy"] = deepcopy(execution_policy.get("retry_policy") or execution.get("retry_policy") or {"max_attempts": 1})
                if execution.get("spawn_mode") == "subagent_worker":
                    execution["subagent_policy"] = deepcopy(
                        execution_policy.get("subagent_policy")
                        or execution.get("subagent_policy")
                        or {
                            "isolation_mode": "lane",
                            "max_turns": 8,
                            "allow_direct_teammate_messages": False,
                            "share_worktree": False,
                            "allow_nested_subagents": False,
                        }
                    )
            node["execution"] = execution
            safety = dict(node.get("safety") or {})
            if execution_policy:
                safety["allow_provider_calls"] = bool(execution_policy.get("allow_provider_calls"))
                safety["allow_code_changes"] = bool(execution_policy.get("allow_code_changes"))
                safety["allow_install"] = bool(execution_policy.get("allow_install"))
                safety["requires_human_approval"] = bool(execution_policy.get("requires_human_approval"))
            approval_kind = str(dict(task_node.get("approval_gate") or {}).get("review_kind") or "").strip()
            if approval_kind:
                safety["approval_kind"] = approval_kind
            node["safety"] = safety
            output_contract = dict(node.get("output_contract") or {})
            task_output_contract = dict(task_node.get("output_contract") or {})
            output_contract["human_summary_required"] = bool(task_output_contract.get("human_summary_required", output_contract.get("human_summary_required", True)))
            output_contract["mode"] = "artifact_only" if bool(task_output_contract.get("artifact_only")) else "structured_and_artifacts"
            artifact_outputs = [
                str(item).strip()
                for item in list(task_output_contract.get("artifact_outputs") or [])
                if str(item).strip()
            ]
            if artifact_outputs:
                existing_specs = [
                    deepcopy(item)
                    for item in list(output_contract.get("artifact_specs") or [])
                    if isinstance(item, dict)
                ]
                output_contract["artifact_specs"] = [
                    {
                        "kind": item if item in ARTIFACT_KINDS else "structured_json",
                        "id": self._artifact_spec_id_for_kind(existing_specs, item),
                    }
                    for item in artifact_outputs
                ]
            machine_schema = task_output_contract.get("machine_result_schema")
            if isinstance(machine_schema, dict) and machine_schema:
                schema_ref = f"schema.{task_node['node_id']}.machine_result"
                schema_registry[schema_ref] = deepcopy(machine_schema)
                output_contract["machine_result_schema_ref"] = schema_ref
                node_schema_refs[str(task_node["node_id"])] = schema_ref
            node["output_contract"] = output_contract
            if (
                interop_source_format in {COMFYUI_WORKFLOW_SOURCE_FORMAT, LANGGRAPH_STATEGRAPH_SOURCE_FORMAT}
                and isinstance(dict(existing_nodes.get(str(node.get("node_id") or "").strip()) or {}).get("ports"), dict)
            ):
                node["ports"] = deepcopy(dict(existing_nodes.get(str(node.get("node_id") or "").strip()) or {}).get("ports") or {})
            else:
                node["ports"] = self._sync_orchestration_node_ports(
                    node=dict(node),
                    output_contract=output_contract,
                )
            ui = dict(node.get("ui") or {})
            ui["position"] = deepcopy(task_node.get("position") or ui.get("position") or {"x": 0, "y": 0})
            node["ui"] = ui
            if "node_type_id" in task_ui_hints and task_ui_hints.get("node_type_id") is not None:
                node["resolved_node_type_id"] = str(task_ui_hints.get("node_type_id") or "")
            if "node_type_registry_fingerprint" in task_ui_hints and task_ui_hints.get("node_type_registry_fingerprint") is not None:
                node["node_type_registry_fingerprint"] = str(task_ui_hints.get("node_type_registry_fingerprint") or "")
            if not list(node.get("node_type_diagnostics") or []):
                node["status"] = task_node.get("status")
        synced["schema_registry"] = schema_registry

        task_node_positions = {
            str(item.get("node_id") or "").strip(): dict(item.get("position") or {})
            for item in list(executable_graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        edge_map = {
            str(item.get("edge_id") or "").strip(): dict(item)
            for item in list(executable_graph.get("edges") or [])
            if isinstance(item, dict)
        }
        existing_edges = {
            str(item.get("edge_id") or "").strip(): deepcopy(item)
            for item in list(existing_graph.get("edges") or [])
            if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
        }
        synced_node_map = {
            str(item.get("node_id") or "").strip(): item
            for item in list(synced.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        for task_edge in edge_map.values():
            edge_id = str(task_edge.get("edge_id") or "").strip()
            from_node_id = str(task_edge.get("from_node_id") or "").strip()
            to_node_id = str(task_edge.get("to_node_id") or "").strip()
            source_schema_ref = str(node_schema_refs.get(from_node_id) or "").strip()
            task_handoff_contract = task_edge.get("handoff_contract") if isinstance(task_edge.get("handoff_contract"), dict) else {}
            existing_edge = dict(existing_edges.get(edge_id) or {})
            existing_bindings = [
                dict(item)
                for item in list(dict(existing_edge.get("handoff_contract") or {}).get("port_bindings") or [])
                if isinstance(item, dict)
            ]
            existing_has_explicit_typed_binding = bool(existing_bindings) and not all(
                str(item.get("from_port_id") or "").strip() == "machine_result"
                and str(item.get("to_port_id") or "").strip() == "task_context"
                for item in existing_bindings
            )
            if (
                not edge_id
                or not from_node_id
                or not to_node_id
                or not source_schema_ref
                or list(task_handoff_contract.get("port_bindings") or [])
                or existing_has_explicit_typed_binding
            ):
                continue
            target_node = synced_node_map.get(to_node_id)
            if not isinstance(target_node, dict):
                continue
            source_task_node = node_map.get(from_node_id) or {}
            self._ensure_inferred_handoff_input_port(
                target_node,
                edge_id=edge_id,
                source_node_id=from_node_id,
                source_node_label=str(source_task_node.get("label") or from_node_id).strip() or from_node_id,
                schema_ref=source_schema_ref,
            )
        synced["edges"] = [
            {
                **deepcopy(item),
                **deepcopy(existing_edges.get(str(item.get("edge_id") or "").strip()) or {}),
            }
            for item in list(canonical_lifted.get("edges") or [])
            if isinstance(item, dict)
        ]
        synced_edges: list[dict[str, Any]] = []
        for edge in list(synced.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            task_edge = edge_map.get(str(edge.get("edge_id") or "").strip())
            if not task_edge:
                synced_edges.append(edge)
                continue
            edge["from_node_id"] = task_edge.get("from_node_id")
            edge["to_node_id"] = task_edge.get("to_node_id")
            edge["edge_type"] = task_edge.get("edge_type")
            edge["context_policy"] = deepcopy(task_edge.get("context_policy") or edge.get("context_policy") or {})
            handoff_contract = dict(edge.get("handoff_contract") or {})
            task_handoff_contract = task_edge.get("handoff_contract")
            if isinstance(task_handoff_contract, dict):
                handoff_contract.update(deepcopy(task_handoff_contract))
            source_schema_ref = str(node_schema_refs.get(str(edge["from_node_id"]) or "") or "").strip()
            if source_schema_ref:
                handoff_contract["required_output_schema_refs"] = [source_schema_ref]
            handoff_contract["port_bindings"] = self._default_handoff_port_bindings(
                synced,
                edge_id=str(edge.get("edge_id") or ""),
                from_node_id=str(edge["from_node_id"] or ""),
                to_node_id=str(edge["to_node_id"] or ""),
                existing=list(handoff_contract.get("port_bindings") or []),
            )
            edge["handoff_contract"] = handoff_contract
            edge["status"] = task_edge.get("status")
            synced_edges.append(edge)

        existing_edge_ids = {
            str(item.get("edge_id") or "").strip()
            for item in synced_edges
            if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
        }
        for task_edge in edge_map.values():
            edge_id = str(task_edge.get("edge_id") or "").strip()
            if not edge_id or edge_id in existing_edge_ids:
                continue
            from_node_id = str(task_edge.get("from_node_id") or "").strip()
            to_node_id = str(task_edge.get("to_node_id") or "").strip()
            source_schema_ref = str(node_schema_refs.get(from_node_id) or "").strip()
            task_handoff_contract = task_edge.get("handoff_contract") if isinstance(task_edge.get("handoff_contract"), dict) else {}
            from_position = task_node_positions.get(from_node_id) or {}
            to_position = task_node_positions.get(to_node_id) or {}
            synced_edges.append(
                {
                    "edge_id": edge_id,
                    "from_node_id": from_node_id,
                    "to_node_id": to_node_id,
                    "edge_type": task_edge.get("edge_type"),
                    "handoff_contract": {
                        "message_template": str(task_handoff_contract.get("message_template") or f"Deliver the required output from {from_node_id or 'source'} to {to_node_id or 'target'}."),
                        "message_part_modes": [
                            str(item).strip()
                            for item in list(task_handoff_contract.get("message_part_modes") or ["machine_result", "human_summary"])
                            if str(item).strip()
                        ],
                        "required_output_schema_refs": [source_schema_ref] if source_schema_ref else [
                            str(item).strip()
                            for item in list(task_handoff_contract.get("required_output_schema_refs") or [])
                            if str(item).strip()
                        ],
                        "port_bindings": self._default_handoff_port_bindings(
                            synced,
                            edge_id=edge_id,
                            from_node_id=from_node_id,
                            to_node_id=to_node_id,
                            existing=list(task_handoff_contract.get("port_bindings") or []),
                        ),
                    },
                    "context_policy": deepcopy(task_edge.get("context_policy") or {}),
                    "ui": {
                        "position": {
                            "x": (float(from_position.get("x") or 0) + float(to_position.get("x") or 0)) / 2,
                            "y": (float(from_position.get("y") or 0) + float(to_position.get("y") or 0)) / 2,
                        }
                    },
                    "status": task_edge.get("status") or "ready",
                }
            )
        synced["edges"] = synced_edges
        return synced

    @staticmethod
    def _reachable_task_graph_projection(task_graph: dict[str, Any]) -> dict[str, Any]:
        projected = deepcopy(task_graph)
        nodes = [dict(item) for item in list(projected.get("nodes") or []) if isinstance(item, dict)]
        edges = [dict(item) for item in list(projected.get("edges") or []) if isinstance(item, dict)]
        node_ids = {
            str(item.get("node_id") or "").strip()
            for item in nodes
            if str(item.get("node_id") or "").strip()
        }
        entry_node_ids = [
            str(item).strip()
            for item in list(dict(projected.get("graph_policy") or {}).get("entry_node_ids") or [])
            if str(item).strip() in node_ids
        ]
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for edge in edges:
            from_node_id = str(edge.get("from_node_id") or "").strip()
            to_node_id = str(edge.get("to_node_id") or "").strip()
            if from_node_id in node_ids and to_node_id in node_ids:
                adjacency.setdefault(from_node_id, []).append(to_node_id)

        reachable: set[str] = set()
        pending = list(reversed(entry_node_ids))
        while pending:
            node_id = pending.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            pending.extend(reversed(adjacency.get(node_id, [])))

        projected["nodes"] = [
            item for item in nodes if str(item.get("node_id") or "").strip() in reachable
        ]
        projected["edges"] = [
            item
            for item in edges
            if str(item.get("from_node_id") or "").strip() in reachable
            and str(item.get("to_node_id") or "").strip() in reachable
        ]
        projected.pop("orchestration_graph", None)
        return projected

    def _sync_orchestration_node_ports(self, *, node: dict[str, Any], output_contract: dict[str, Any]) -> dict[str, Any]:
        ports = dict(node.get("ports") or {})
        inputs = [deepcopy(item) for item in list(ports.get("inputs") or []) if isinstance(item, dict)]
        outputs = [deepcopy(item) for item in list(ports.get("outputs") or []) if isinstance(item, dict)]
        input_contract = dict(node.get("input_contract") or {})
        input_mode = str(input_contract.get("mode") or "").strip()
        if not inputs and input_mode != "task_context":
            inputs = [{"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True}]

        machine_schema_ref = str(output_contract.get("machine_result_schema_ref") or "").strip()
        artifact_specs = [deepcopy(item) for item in list(output_contract.get("artifact_specs") or []) if isinstance(item, dict)]
        by_id = {
            str(item.get("port_id") or "").strip(): item
            for item in outputs
            if str(item.get("port_id") or "").strip()
        }
        normalized_outputs: list[dict[str, Any]] = []
        if machine_schema_ref:
            machine_port = dict(by_id.get("machine_result") or {})
            machine_port.update(
                {
                    "port_id": "machine_result",
                    "label": str(machine_port.get("label") or "Machine Result"),
                    "port_type": "structured_json",
                    "shape": "single",
                    "required": True,
                    "schema_ref": machine_schema_ref,
                }
            )
            normalized_outputs.append(machine_port)
        for spec in artifact_specs:
            artifact_id = str(spec.get("id") or spec.get("kind") or "artifact").strip()
            artifact_kind = str(spec.get("kind") or "").strip() or "structured_json"
            artifact_port = dict(by_id.get(artifact_id) or {})
            artifact_port.update(
                {
                    "port_id": artifact_id,
                    "label": str(artifact_port.get("label") or artifact_id.replace("_", " ").title()),
                    "port_type": self._artifact_kind_to_port_type(artifact_kind),
                    "shape": "single",
                    "required": False,
                    "artifact_kind": artifact_kind,
                }
            )
            artifact_port.pop("schema_ref", None)
            normalized_outputs.append(artifact_port)
        if not normalized_outputs:
            normalized_outputs = outputs or [{"port_id": "human_summary", "label": "Human Summary", "port_type": "text", "shape": "single", "required": True}]
        return {"inputs": inputs, "outputs": normalized_outputs}

    def _default_handoff_port_bindings(self, orchestration_graph: dict[str, Any], *, edge_id: str = "", from_node_id: str, to_node_id: str, existing: list[Any]) -> list[dict[str, str]]:
        normalized_existing: list[dict[str, str]] = []
        for item in existing:
            if not isinstance(item, dict):
                continue
            from_port_id = str(item.get("from_port_id") or "").strip()
            to_port_id = str(item.get("to_port_id") or "").strip()
            if from_port_id and to_port_id:
                normalized_existing.append({"from_port_id": from_port_id, "to_port_id": to_port_id})
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(orchestration_graph.get("nodes") or [])
            if isinstance(item, dict)
        }
        source_outputs = {
            str(item.get("port_id") or "").strip(): dict(item)
            for item in list(dict(node_map.get(from_node_id) or {}).get("ports", {}).get("outputs") or [])
            if isinstance(item, dict) and str(item.get("port_id") or "").strip()
        }
        target_inputs = {
            str(item.get("port_id") or "").strip(): dict(item)
            for item in list(dict(node_map.get(to_node_id) or {}).get("ports", {}).get("inputs") or [])
            if isinstance(item, dict) and str(item.get("port_id") or "").strip()
        }
        if normalized_existing:
            legacy_task_context_only = all(
                item["from_port_id"] == "machine_result" and item["to_port_id"] == "task_context"
                for item in normalized_existing
            )
            if not legacy_task_context_only:
                return normalized_existing
            if "machine_result" not in source_outputs:
                return normalized_existing
            typed_targets = [
                port_id
                for port_id, port in target_inputs.items()
                if port_id != "task_context"
                and str(port.get("port_type") or "").strip() == str(dict(source_outputs.get("machine_result") or {}).get("port_type") or "").strip()
            ]
            if not typed_targets:
                return normalized_existing
        bindings: list[dict[str, str]] = []
        if "machine_result" in source_outputs:
            inferred_target_id = f"{str(edge_id or '').strip()}_input" if str(edge_id or "").strip() else ""
            preferred_targets = []
            if inferred_target_id and inferred_target_id in target_inputs:
                preferred_targets.append(inferred_target_id)
            preferred_targets.extend(
                port_id
                for port_id in target_inputs
                if port_id != "task_context" and port_id != inferred_target_id
            )
            if not preferred_targets and "task_context" in target_inputs:
                preferred_targets = ["task_context"]
            if preferred_targets:
                bindings.append({"from_port_id": "machine_result", "to_port_id": preferred_targets[0]})
        bound_targets = {
            str(item.get("to_port_id") or "").strip()
            for item in bindings
            if str(item.get("to_port_id") or "").strip()
        }
        for port_id in source_outputs:
            if port_id == "machine_result":
                continue
            if port_id in target_inputs:
                if port_id in bound_targets:
                    continue
                bindings.append({"from_port_id": port_id, "to_port_id": port_id})
                bound_targets.add(port_id)
                continue
            source_type = str(source_outputs[port_id].get("port_type") or "").strip()
            target_match = next(
                (
                    target_id
                    for target_id, target in target_inputs.items()
                    if target_id != "task_context"
                    and target_id not in bound_targets
                    and str(target.get("port_type") or "").strip() == source_type
                ),
                "",
            )
            if target_match:
                bindings.append({"from_port_id": port_id, "to_port_id": target_match})
                bound_targets.add(target_match)
        if not bindings and source_outputs and target_inputs:
            first_source = next(iter(source_outputs))
            first_target = next(iter(target_inputs))
            bindings.append({"from_port_id": first_source, "to_port_id": first_target})
        return bindings

    def _ensure_inferred_handoff_input_port(
        self,
        node: dict[str, Any],
        *,
        edge_id: str,
        source_node_id: str,
        source_node_label: str,
        schema_ref: str,
    ) -> None:
        inferred_port_id = f"{edge_id}_input"
        ports = dict(node.get("ports") or {})
        inputs = [deepcopy(item) for item in list(ports.get("inputs") or []) if isinstance(item, dict)]
        if not any(str(item.get("port_id") or "").strip() == inferred_port_id for item in inputs):
            inputs.append(
                {
                    "port_id": inferred_port_id,
                    "label": f"Input From {source_node_label or source_node_id}",
                    "port_type": "structured_json",
                    "shape": "single",
                    "required": True,
                    "schema_ref": schema_ref,
                }
            )
        ports["inputs"] = inputs
        node["ports"] = ports
        input_contract = dict(node.get("input_contract") or {})
        existing_port_ids = [
            str(item).strip()
            for item in list(input_contract.get("port_ids") or [])
            if str(item or "").strip()
        ]
        if inferred_port_id not in existing_port_ids:
            existing_port_ids.append(inferred_port_id)
        input_contract["mode"] = "task_context_and_typed_ports"
        input_contract["port_ids"] = existing_port_ids
        node["input_contract"] = input_contract

    @staticmethod
    def _artifact_spec_id_for_kind(existing_specs: list[dict[str, Any]], artifact_kind: str) -> str:
        for spec in existing_specs:
            if str(spec.get("kind") or "").strip() == artifact_kind:
                existing_id = str(spec.get("id") or "").strip()
                if existing_id:
                    return existing_id
        return artifact_kind

    @staticmethod
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
            "validation_report": "agent_report",
            "run_summary": "agent_report",
            "test_report": "agent_report",
            "text_report": "text",
            "diagnostic_bundle": "agent_report",
            "graph_definition": "structured_json",
        }
        return mapping.get(kind, "text")

    def _merge_task_graph_run_refs(self, persisted: Any, incoming: Any) -> list[dict[str, Any]]:
        return self._graph_run_refs.merge_task_graph_run_refs(
            persisted,
            incoming,
            limit=GRAPH_RUN_REF_LIMIT,
        )

    def _merge_task_graph_run_ref(
        self,
        existing: dict[str, Any] | None,
        candidate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return self._graph_run_refs.merge_task_graph_run_ref(existing, candidate)

    def _select_task_graph_run_ref_timeline_events(
        self,
        *,
        preferred: dict[str, Any],
        fallback: dict[str, Any],
        preferred_sort_key: tuple[float, float, str],
        fallback_sort_key: tuple[float, float, str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._graph_run_refs._select_task_graph_run_ref_timeline_events(
            preferred=preferred,
            fallback=fallback,
            preferred_sort_key=preferred_sort_key,
            fallback_sort_key=fallback_sort_key,
        )

    def _select_task_graph_run_ref_object_array(
        self,
        *,
        preferred: Any,
        fallback: Any,
        preferred_sort_key: tuple[float, float, str],
        fallback_sort_key: tuple[float, float, str],
        key_for: Callable[[dict[str, Any]], str],
    ) -> tuple[list[dict[str, Any]], bool]:
        return self._graph_run_refs._select_task_graph_run_ref_object_array(
            preferred=preferred,
            fallback=fallback,
            preferred_sort_key=preferred_sort_key,
            fallback_sort_key=fallback_sort_key,
            key_for=key_for,
        )

    @staticmethod
    def _compact_task_graph_run_ref_object_array(
        value: Any,
        *,
        key_for: Callable[[dict[str, Any]], str],
    ) -> list[dict[str, Any]]:
        return TaskGraphRunRefService._compact_task_graph_run_ref_object_array(value, key_for=key_for)

    @staticmethod
    def _merge_task_graph_run_ref_count_map(left: Any, right: Any) -> dict[str, int]:
        return TaskGraphRunRefService._merge_task_graph_run_ref_count_map(left, right)

    def _merge_task_graph_snapshot_refs(self, persisted: Any, incoming: Any) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for source in (persisted, incoming):
            for item in list(source or []):
                if not isinstance(item, dict):
                    continue
                snapshot_id = str(item.get("snapshot_id") or "").strip()
                if not snapshot_id:
                    continue
                existing = by_id.get(snapshot_id)
                candidate = dict(item)
                if existing is None or self._graph_snapshot_ref_sort_key(candidate) >= self._graph_snapshot_ref_sort_key(existing):
                    by_id[snapshot_id] = candidate
        merged = sorted(
            by_id.values(),
            key=self._graph_snapshot_ref_sort_key,
            reverse=True,
        )
        return merged[:GRAPH_SNAPSHOT_REF_LIMIT]

    @staticmethod
    def _graph_run_ref_sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
        return TaskGraphRunRefService.graph_run_ref_sort_key(item)

    @staticmethod
    def _graph_snapshot_ref_sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
        updated = str(item.get("updated_at") or "").strip()
        created = str(item.get("created_at") or "").strip()
        updated_ts = dt.datetime.fromisoformat(updated).timestamp() if updated else float("-inf")
        created_ts = dt.datetime.fromisoformat(created).timestamp() if created else float("-inf")
        return (updated_ts, created_ts, str(item.get("snapshot_id") or "").strip())

    def _sync_project_current_task(self, task: dict[str, Any]) -> None:
        self._projects.reconcile_task_projection(task)

    def _project_sync_needed(self, task: dict[str, Any]) -> bool:
        project = self._project()
        task_id = str(task.get("task_id") or "")
        active_thread = str(task.get("active_provider_thread_id") or "")
        return (
            str(project.get("current_task_id") or "") != task_id
            or str(project.get("current_thread_id") or "") != active_thread
        )

    def _replace_task(self, tasks: list[dict[str, Any]], task: dict[str, Any]) -> list[dict[str, Any]]:
        return [task, *[item for item in tasks if item.get("task_id") != task.get("task_id")]][:100]

    def _enforce_task_thread_ownership(self, tasks: list[dict[str, Any]], *, owner_task: dict[str, Any]) -> list[dict[str, Any]]:
        owner_task_id = str(owner_task.get("task_id") or "").strip()
        if not owner_task_id:
            return tasks[:100]
        owned_thread_ids = {
            str(item.get("thread_id") or "").strip()
            for item in [
                *list(owner_task.get("provider_threads") or []),
                *list(owner_task.get("fork_threads") or []),
            ]
            if isinstance(item, dict) and str(item.get("thread_id") or "").strip()
        }
        if not owned_thread_ids:
            return tasks[:100]
        normalized_tasks: list[dict[str, Any]] = []
        for item in tasks[:100]:
            if not isinstance(item, dict):
                continue
            task = dict(item)
            task_id = str(task.get("task_id") or "").strip()
            if task_id == owner_task_id:
                normalized_tasks.append(task)
                continue
            changed = False
            provider_threads = [
                dict(entry)
                for entry in list(task.get("provider_threads") or [])
                if isinstance(entry, dict)
            ]
            filtered_provider_threads = [
                entry for entry in provider_threads if str(entry.get("thread_id") or "").strip() not in owned_thread_ids
            ]
            if filtered_provider_threads != provider_threads:
                task["provider_threads"] = filtered_provider_threads
                changed = True
            fork_threads = [
                dict(entry)
                for entry in list(task.get("fork_threads") or [])
                if isinstance(entry, dict)
            ]
            filtered_fork_threads = [
                entry for entry in fork_threads if str(entry.get("thread_id") or "").strip() not in owned_thread_ids
            ]
            if filtered_fork_threads != fork_threads:
                task["fork_threads"] = filtered_fork_threads
                changed = True
            active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
            if active_thread_id and active_thread_id in owned_thread_ids:
                task["active_provider_thread_id"] = None
                changed = True
            if changed:
                task["updated_at"] = now_iso()
                task, _ = self._normalize_task(task)
            normalized_tasks.append(task)
        return normalized_tasks[:100]

    def _same_context_ref(self, left: Any, right: Any) -> bool:
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        return (
            str(left.get("pack_type") or "") == str(right.get("pack_type") or "")
            and str(left.get("path") or "") == str(right.get("path") or "")
        )

    def _find_task(self, tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
        if not task_id:
            return None
        for task in tasks:
            if str(task.get("task_id") or "") == task_id:
                return dict(task)
        return None

    def _find_task_for_thread(self, tasks: list[dict[str, Any]], thread_id: str) -> dict[str, Any] | None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return None
        for task in tasks:
            if not isinstance(task, dict):
                continue
            for collection_name in ("provider_threads", "fork_threads"):
                for item in list(task.get(collection_name) or []):
                    if isinstance(item, dict) and str(item.get("thread_id") or "").strip() == clean_thread_id:
                        return dict(task)
        return None

    def _state(self) -> dict[str, Any]:
        state = dict(read_json(self._path(), {"schema_version": TASK_STATE_SCHEMA_VERSION, "current_task_id": None, "tasks": []}))
        state.setdefault("schema_version", TASK_STATE_SCHEMA_VERSION)
        state.setdefault("tasks", [])
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        self._reject_secret_like(state)
        write_json(self._path(), state)

    def _path(self) -> Path:
        return self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME / "tasks.json"

    def _project(self) -> dict[str, Any]:
        project = self._projects.current_project
        if not project:
            raise ValueError("No project is open.")
        return dict(project)

    def _reject_secret_like(self, payload: dict[str, Any]) -> None:
        serialized = str(redact_sensitive(payload))
        if SECRET_RE.search(serialized):
            raise SecurityError("Secret-like content is not allowed in task records.")

    def _resolved_current_task_id(self, *, state: dict[str, Any], project: dict[str, Any] | None = None) -> str:
        project_payload = project if isinstance(project, dict) else self._projects.current_project or {}
        state_task_id = str(state.get("current_task_id") or "").strip()
        if state_task_id:
            return state_task_id
        return str((project_payload or {}).get("current_task_id") or "").strip()


def _canonical_model_key(model: Any) -> str:
    """Normalize display/provider-prefixed model ids for provider-thread reuse only."""
    text = str(model or "").strip().lower()
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _display_model_id(model: Any) -> str | None:
    text = str(model or "").strip()
    if not text:
        return None
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _canonical_effort_key(effort: Any) -> str:
    text = str(effort or "").strip().lower()
    if text == "max":
        return "xhigh"
    return text


def _display_effort(effort: Any, provider_id: Any = None) -> str | None:
    text = str(effort or "").strip()
    if not text:
        return None
    provider = str(provider_id or "").strip().lower()
    if provider.startswith("deepseek") and text.lower() in {"xhigh", "x-high"}:
        return "max"
    return text


def _display_thread_name(name: Any, provider_id: Any = None) -> str | None:
    text = str(name or "").strip()
    if not text:
        return None
    flattened = text.replace("\r", "\n")
    candidate_lines = [line.strip() for line in flattened.splitlines() if line.strip()]
    first_line = candidate_lines[0] if candidate_lines else ""
    first_line = SMOKE_TASK_PREFIX_PATTERN.sub("", first_line).strip()
    lowered_first_line = first_line.lower()
    for marker in AUTO_INJECTED_CONTEXT_NAME_MARKERS:
        if marker in lowered_first_line:
            prefix = first_line[:lowered_first_line.index(marker)].strip(" -:\t")
            first_line = prefix or ""
            break
    if not first_line:
        provider = str(provider_id or "").strip()
        return f"{provider.title() or 'Provider'} thread"
    if first_line.lower().startswith(("astrabridge minimal visual mode:", "lcr minimal visual mode:")):
        provider = str(provider_id or "").strip()
        return f"{provider.title() or 'Provider'} visual review"
    if len(first_line) > 96:
        return f"{first_line[:93].rstrip()}..."
    return first_line


def _display_task_title(title: Any) -> str:
    text = str(title or "").replace("\r", "\n")
    candidate_lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_line = candidate_lines[0] if candidate_lines else str(title or "").strip()
    first_line = SMOKE_TASK_PREFIX_PATTERN.sub("", first_line).strip()
    return first_line


def _provider_thread_entry_is_plausible(item: dict[str, Any]) -> bool:
    """Reject obvious provider/model mismatches left by older handoff bugs.

    Keep this intentionally conservative. OpenAI-compatible providers such as
    Yunwu legitimately expose OpenAI-named models, while a Kimi thread with a
    DeepSeek model cannot be replayed or reused safely.
    """
    provider = str(item.get("provider_id") or "").strip().lower()
    profile = str(item.get("profile_id") or "").strip().lower()
    raw_model = str(item.get("model") or "").strip().lower()
    model = _canonical_model_key(raw_model)
    if not model or (not provider and not profile):
        return True
    if provider.startswith("deepseek"):
        return model.startswith("deepseek")
    if provider in {"kimi", "moonshot"} or profile.startswith(("kimi", "moonshot")):
        return model.startswith(("kimi", "moonshot"))
    if provider in {"qwen", "dashscope"} or profile.startswith(("qwen", "dashscope")):
        return model.startswith("qwen")
    return True


def _provider_thread_route_key(item: dict[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    provider = str(item.get("provider_id") or "").strip().lower()
    model = _canonical_model_key(item.get("model"))
    if not provider and "/" in model:
        provider = model.split("/", 1)[0]
    permission_mode = str(item.get("permission_mode") or "").strip().lower()
    collaboration_mode = str(item.get("collaboration_mode") or "").strip().lower()
    execution_backend = str(item.get("execution_backend") or "").strip().lower() or "app_server"
    role = str(item.get("role") or "provider").strip().lower()
    return (
        provider,
        model,
        _canonical_effort_key(item.get("reasoning_effort")),
        permission_mode,
        collaboration_mode,
        execution_backend,
        role,
    )


def _lane_label(*, provider_id: Any = None, model: Any = None, name: Any = None) -> str:
    display_name = _display_thread_name(name, provider_id)
    if display_name:
        return str(redact_sensitive(display_name))[:160]
    provider = str(provider_id or "").strip()
    display_model = _display_model_id(model)
    if provider and display_model:
        return f"{provider} / {display_model}"
    if display_model:
        return display_model
    if provider:
        return provider
    return "Thread"


def _lane_view(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    thread_id = str(item.get("thread_id") or "").strip() or None
    provider_id = str(item.get("provider_id") or "").strip() or None
    model = _display_model_id(item.get("model"))
    return {
        "thread_id": thread_id,
        "profile_id": str(item.get("profile_id") or "").strip() or None,
        "provider_id": provider_id,
        "model": model,
        "reasoning_effort": _display_effort(item.get("reasoning_effort"), provider_id),
        "permission_mode": str(item.get("permission_mode") or "").strip() or None,
        "collaboration_mode": str(item.get("collaboration_mode") or "").strip() or None,
        "name": _display_thread_name(item.get("name"), provider_id),
        "label": _lane_label(provider_id=provider_id, model=model, name=item.get("name")),
        "missing_at": str(item.get("missing_at") or "").strip() or None,
        "missing_reason": str(item.get("missing_reason") or "").strip() or None,
        "created_at": str(item.get("created_at") or "").strip() or None,
        "updated_at": str(item.get("updated_at") or "").strip() or None,
    }


def _lane_view_from_handoff_event(event: dict[str, Any] | None, *, source: bool) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    prefix = "from_" if source else ""
    thread_key = f"{prefix}thread_id" if source else "to_thread_id"
    thread_id = str(event.get(thread_key) or "").strip()
    provider_id = str(event.get(f"{prefix}provider_id") or "").strip() or None
    model = _display_model_id(event.get(f"{prefix}model" if prefix else "model"))
    permission_mode = str(event.get(f"{prefix}permission_mode" if prefix else "permission_mode") or "").strip() or None
    reasoning_effort = _display_effort(
        event.get(f"{prefix}reasoning_effort" if prefix else "reasoning_effort"),
        provider_id,
    )
    profile_id = str(event.get(f"{prefix}profile_id" if prefix else "profile_id") or "").strip() or None
    label = _lane_label(provider_id=provider_id, model=model)
    if not any([thread_id, provider_id, model, profile_id, reasoning_effort]):
        return None
    return {
        "thread_id": thread_id or None,
        "profile_id": profile_id,
        "provider_id": provider_id,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "permission_mode": permission_mode,
        "collaboration_mode": None,
        "name": None,
        "label": label,
        "missing_at": None,
        "missing_reason": None,
        "created_at": str(event.get("created_at") or "").strip() or None,
        "updated_at": str(event.get("created_at") or "").strip() or None,
    }

